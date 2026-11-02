"""Signed private JSON checkpoints. Never pickle; never store provider credentials."""
from dataclasses import asdict
import hashlib,json,os,tempfile
from pathlib import Path
from ..controller_context import fingerprint
from ..simulator import Faults,PlantConfig,Controller,Experiment
from ..v2_models import ModelFit
from .approval import Policy,Authority
from .laboratory import V4Laboratory


def sources():
    root=Path(__file__).resolve().parents[2]
    paths=list((root/'nautilus/v4').glob('*.py'))+[root/'nautilus'/n for n in ('simulator.py','lab_safety.py','laboratory.py','v2_models.py','diagnosis.py','controller_context.py')]
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def save(lab,path,host=None):
    if type(lab.authority) is not Authority:raise ValueError('Private authority required for checkpoint')
    path=Path(path).resolve()
    if path.parent!=lab.authority.directory:raise ValueError('Checkpoint must be in authority directory')
    b=lab.execution_backend
    data={'schema_version':'nautilus.private-session.v4','sources':sources(),'session_id':lab.session_id,'policy':lab.policy.mode,'joint_enabled':lab.joint_enabled,
      'settings':{'faults':asdict(b.faults),'plant':asdict(b.plant),'controller':asdict(b.controller),'seed':b.seed},
      'limits':{'fit_budget':lab._fit_limit,'optimization_budget':lab._optimization_limit,'experiment_budget':lab._experiment_limit,'time_budget_s':lab._time_limit,'starts':lab._starts},
      'ledger':lab.ledger,'episodes':[{'observations':e['observations'],'experiment':asdict(e['experiment'])} for e in lab.episodes],
      'fits':{n:asdict(f) for n,f in lab._fits.items()},'reports':lab._reports,'joint_details':lab.joint_details,
      'counts':{'fits':lab.fit_calls,'starts':lab.optimization_attempts,'experiments':lab.tests,'time':lab.test_time_s},
      'seen':sorted(lab._seen),'closed':lab._closed,'state':lab.state,'pending':lab.pending,'v4_events':lab.v4_events,
      'backend':{'count':b.count,'time':b.time,'used':sorted(b.used)},'host':host}
    envelope={'data':data,'signature':lab.authority.seal(data)}
    fd,name=tempfile.mkstemp(prefix='.session-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as out:json.dump(envelope,out,allow_nan=False);out.flush();os.fsync(out.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def load(authority,path):
    path=Path(path).resolve()
    if path.parent!=authority.directory or path.is_symlink():raise ValueError('Untrusted checkpoint location')
    if path.stat().st_size>20_000_000:raise ValueError('Checkpoint size limit')
    envelope=json.loads(path.read_text());authority.verify(envelope['data'],envelope['signature']);d=envelope['data']
    if d['schema_version']!='nautilus.private-session.v4' or d['sources']!=sources():raise ValueError('Checkpoint source revision changed; no automatic replay')
    previous=None
    for i,e in enumerate(d['ledger']):
        body={k:v for k,v in e.items() if k!='event_hash'}
        if e['index']!=i or e['previous_hash']!=previous or fingerprint(body)!=e['event_hash']:raise ValueError('Broken checkpoint ledger')
        previous=e['event_hash']
    settings={k:c(**d['settings'][k]) for k,c in (('faults',Faults),('plant',PlantConfig),('controller',Controller))};settings['seed']=d['settings']['seed']
    lab=V4Laboratory(d['ledger'][0]['observations'],policy=Policy(d['policy']),authority=authority,session_id=d['session_id'],settings=settings,joint_enabled=d['joint_enabled'],**d['limits'])
    lab.ledger=d['ledger'];lab.episodes=[{'observations':e['observations'],'experiment':Experiment(**e['experiment'])} for e in d['episodes']]
    lab._fits={n:ModelFit(**f) for n,f in d['fits'].items()};lab._reports=d['reports'];lab.joint_details=d['joint_details'];lab._seen=set(d['seen'])
    lab.fit_calls=d['counts']['fits'];lab.optimization_attempts=d['counts']['starts'];lab.tests=d['counts']['experiments'];lab.test_time_s=d['counts']['time']
    lab._closed=d['closed'];lab.state=d['state'];lab.pending=d['pending'];lab.v4_events=d['v4_events']
    lab.execution_backend.count=d['backend']['count'];lab.execution_backend.time=d['backend']['time'];lab.execution_backend.used=set(d['backend']['used'])
    return lab,d['host']
