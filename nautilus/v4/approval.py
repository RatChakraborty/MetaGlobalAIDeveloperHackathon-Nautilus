"""Local OS-account authority. No browser/model endpoint; durable single-use decisions.

Trust boundary: the operator owns a private 0700 directory. Any process already
running as that OS account is trusted; never give the model filesystem execution.
HMACs detect edits but do not by themselves authenticate a human. The only public
approval command additionally requires a foreground controlling terminal.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib,hmac,json,os,secrets,sqlite3,stat,time
from pathlib import Path
from ..controller_context import canonical,fingerprint
from ..v2_experiments import parse_trial

MODES=('simulation_enforced','simulation_operator_approved','simulation_advisory')
TRANSITIONS={'AWAITING_OPERATOR':{'APPROVED','DENIED','CANCELLED','EXPIRED'},
 'APPROVED':{'EXECUTING','CANCELLED','EXPIRED'},'EXECUTING':{'COMPLETED','FAILED'},
 'DENIED':set(),'CANCELLED':set(),'EXPIRED':set(),'COMPLETED':set(),'FAILED':set()}

@dataclass(frozen=True)
class Policy:
    mode:str='simulation_enforced'
    def __post_init__(self):
        if self.mode not in MODES:raise ValueError('Invalid simulation policy')
    @property
    def identity(self):return fingerprint({'version':'v4.safety.1','mode':self.mode,'offline_simulation_only':True})
    @property
    def tail(self):return 0. if self.mode=='simulation_advisory' else 2.

class AuthorizationDenied(ValueError):pass

class Authority:
    def __init__(self,directory,*,clock=time.time):
        self.directory=Path(directory).resolve();repo=Path(__file__).resolve().parents[2]
        if self.directory==repo or repo in self.directory.parents:raise ValueError('Authority must stay outside repository')
        self.directory.mkdir(parents=True,mode=0o700,exist_ok=True)
        st=self.directory.stat()
        if st.st_uid!=os.getuid() or stat.S_IMODE(st.st_mode)!=0o700:raise ValueError('Authority directory must be owned by this UID and mode0700')
        self.clock=clock;key=self.directory/'operator-authority.key'
        try:
            fd=os.open(key,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as out:out.write(secrets.token_bytes(32))
        except FileExistsError:pass
        if key.is_symlink() or key.stat().st_uid!=os.getuid() or stat.S_IMODE(key.stat().st_mode)!=0o600:raise ValueError('Unsafe authority key permissions')
        self._key=key.read_bytes()
        if len(self._key)!=32:raise ValueError('Invalid authority key')
        self.db=self.directory/'approvals.sqlite3'
        if self.db.is_symlink():raise ValueError('Unsafe approval database')
        with self._connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, binding TEXT NOT NULL, state TEXT NOT NULL, signature TEXT NOT NULL, audit TEXT NOT NULL)')
        self.db.chmod(0o600)

    def _connect(self):return sqlite3.connect(self.db,timeout=5.,isolation_level='IMMEDIATE')
    def seal(self,value):return hmac.new(self._key,canonical(value).encode(),hashlib.sha256).hexdigest()
    def verify(self,value,signature):
        if type(signature) is not str or not hmac.compare_digest(self.seal(value),signature):raise AuthorizationDenied('Untrusted state signature')

    def create(self,session,epoch,trial,screen,policy,budget,*,expires_s=900.):
        trial=parse_trial(trial.name,trial.params())
        if policy.mode!='simulation_operator_approved' or screen['accepted'] or not 1<=expires_s<=3600:raise ValueError('Invalid approval request')
        binding={'schema_version':'nautilus.approval-binding.v4','session_id':session,'request_id':secrets.token_hex(16),
          'epoch':epoch,'experiment':{'name':trial.name,'params':trial.params()},'experiment_sha256':fingerprint({'name':trial.name,'params':trial.params()}),
          'screen':deepcopy(screen),'screen_sha256':fingerprint(screen),'policy_id':policy.identity,'budget':deepcopy(budget),'expires_at':self.clock()+expires_s}
        state='AWAITING_OPERATOR';audit=[{'state':state,'reason':'predictive_rejection','at':self.clock()}]
        with self._connect() as conn:conn.execute('INSERT INTO requests VALUES (?,?,?,?,?)',(binding['request_id'],canonical(binding),state,self.seal({'binding':binding,'state':state,'audit':audit}),canonical(audit)))
        return self.get(binding['request_id'])

    def _read(self,conn,request_id):
        if type(request_id) is not str or len(request_id)!=32:raise AuthorizationDenied('Malformed request identity')
        row=conn.execute('SELECT binding,state,signature,audit FROM requests WHERE id=?',(request_id,)).fetchone()
        if row is None:raise AuthorizationDenied('Unknown approval request')
        binding,state,signature,audit=row;binding=json.loads(binding);audit=json.loads(audit)
        self.verify({'binding':binding,'state':state,'audit':audit},signature)
        return {'binding':binding,'state':state,'audit':audit}

    def _transition(self,conn,row,state,reason):
        if state not in TRANSITIONS[row['state']]:raise AuthorizationDenied('Illegal or duplicate approval transition')
        audit=row['audit']+[{'state':state,'reason':reason,'at':self.clock()}]
        conn.execute('UPDATE requests SET state=?,signature=?,audit=? WHERE id=?',(state,self.seal({'binding':row['binding'],'state':state,'audit':audit}),canonical(audit),row['binding']['request_id']))
        return {'binding':row['binding'],'state':state,'audit':audit}

    def get(self,request_id):
        with self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE');row=self._read(conn,request_id)
            if row['state'] in ('AWAITING_OPERATOR','APPROVED') and self.clock()>=row['binding']['expires_at']:row=self._transition(conn,row,'EXPIRED','expiration')
            return deepcopy(row)

    def _decide(self,request_id,decision,*,source):
        # Internal trusted CLI boundary. Tests use explicitly labeled simulated-human source.
        if decision not in ('approve','deny','cancel'):raise ValueError('Invalid operator decision')
        row=self.get(request_id)
        with self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE');row=self._read(conn,request_id)
            if self.clock()>=row['binding']['expires_at'] and row['state'] in ('AWAITING_OPERATOR','APPROVED'):
                return self._transition(conn,row,'EXPIRED','expiration')
            if row['state']!='AWAITING_OPERATOR' and not (row['state']=='APPROVED' and decision=='cancel'):raise AuthorizationDenied('Decision is stale or already resolved')
            return self._transition(conn,row,{'approve':'APPROVED','deny':'DENIED','cancel':'CANCELLED'}[decision],source)

    def decide_interactive(self,request_id):
        # Authenticate OS-account access + require actual foreground terminal interaction.
        fd=os.open('/dev/tty',os.O_RDWR)
        try:
            if not os.isatty(fd) or os.tcgetpgrp(fd)!=os.getpgrp():raise AuthorizationDenied('Foreground local operator terminal required')
            row=self.get(request_id)
            with os.fdopen(os.dup(fd),'w') as out:
                out.write(canonical(row)+'\nWARNING: approval is not safety certification; offline simulation only.\n')
                out.write('Type approve '+request_id+', deny '+request_id+' or cancel '+request_id+': ');out.flush()
            with os.fdopen(os.dup(fd)) as inp:answer=inp.readline(160).strip()
            parts=answer.split()
            if len(parts)!=2 or parts[1]!=request_id:raise AuthorizationDenied('Explicit matching request decision required')
            return self._decide(request_id,parts[0],source='foreground_local_cli_uid_'+str(os.getuid()))
        finally:os.close(fd)

    def check(self,request_id,session,epoch,trial,safety,policy,budget,*,consume=False):
        with self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE');row=self._read(conn,request_id);b=row['binding']
            expected={'session_id':session,'epoch':epoch,'experiment':{'name':trial.name,'params':trial.params()},'screen_sha256':fingerprint(safety),'policy_id':policy.identity,'budget':budget}
            if row['state']!='APPROVED' or self.clock()>=b['expires_at'] or any(b[k]!=v for k,v in expected.items()):raise AuthorizationDenied('Approval is absent, stale, expired, reused or mismatched')
            if consume:row=self._transition(conn,row,'EXECUTING','backend_single_use_consumption')
            return deepcopy(row)

    def finish(self,request_id,success):
        with self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE');row=self._read(conn,request_id)
            return self._transition(conn,row,'COMPLETED' if success else 'FAILED','actual_simulator_result' if success else 'execution_failed_or_interrupted')
