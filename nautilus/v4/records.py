"""V4 sidecar allowlists. Replay data never becomes an operator authorization."""
from copy import deepcopy
import json
from pathlib import Path
from ..controller_context import canonical,fingerprint
from ..muse_investigator import public_source
from ..supervisor import public_source as validate_source
from ..v3_validation import clean,closed
from .approval import MODES

KINDS={
 'safety_policy':('policy','policy_id','trial','predictive_margin_m','screen'),
 'approval_request':('binding','state','audit'),'approval_decision':('binding','state','audit'),
 'execution':('policy','approval_request_id','observation_ref','execution','containment'),
 'joint_fit':('schema_version','hypothesis','components','parameter_order','starts','parameter_start_cost','local_sensitivity_matrix','singular_values','rank','condition','conditional_correlation','coupled_directions','residuals','bound_hits','score_rule','elapsed_s','evidence_refs'),
 'rejected_conclusion':('proposal','reason'),'host_assessment':('proposal','assessment'),
 'provider_dispatch':('role','transport_kind','request_number','max_output_tokens','request_bytes','previous_response_id'),'provider_response':('role','entry'),
 'pending_finalization':('proposal',),'critic_review':('entry',),'investigator_response':('review_hash','proposal')}


def sidecar(lab):
    b={'schema_version':'nautilus.v4-provenance-body.v1','session_id':lab.session_id,'policy':lab.policy.mode,'policy_id':lab.policy.identity,'joint_enabled':lab.joint_enabled,'ledger_anchor':lab.ledger[-1]['event_hash'],'events':deepcopy(lab.v4_events),'status':lab.state}
    return {'schema_version':'nautilus.v4-provenance.v1','body_canonical':canonical(b),'hash':fingerprint(b)}


def validate(value,record):
    validate_source(record)
    for envelope in record['ledger']:clean(json.loads(envelope['body_canonical']))
    closed(value,('schema_version','body_canonical','hash'))
    if value['schema_version']!='nautilus.v4-provenance.v1' or type(value['body_canonical']) is not str or len(value['body_canonical'].encode())>4_000_000:raise ValueError('Invalid V4 sidecar envelope')
    b=json.loads(value['body_canonical']);clean(b)
    if fingerprint(b)!=value['hash']:raise ValueError('V4 hash mismatch')
    closed(b,('schema_version','session_id','policy','policy_id','joint_enabled','ledger_anchor','events','status'))
    if b['schema_version']!='nautilus.v4-provenance-body.v1' or b['policy'] not in MODES or type(b['joint_enabled']) is not bool or b['ledger_anchor']!=record['ledger'][-1]['hash']:raise ValueError('Unlinked V4 policy/provenance')
    from .approval import Policy,TRANSITIONS
    if b['policy_id']!=Policy(b['policy']).identity:raise ValueError('V4 policy identity mismatch')
    if b['status'] not in ('RUNNING','AWAITING_OPERATOR','COMPLETED','FAILED'):raise ValueError('Invalid V4 lifecycle status')
    indices={e['hash']:i for i,e in enumerate(record['ledger'])};previous=None;last=0
    if type(b['events']) is not list or len(b['events'])>256:raise ValueError('Unbounded V4 events')
    for i,event in enumerate(b['events']):
        closed(event,('body_canonical','hash'));e=json.loads(event['body_canonical']);closed(e,('index','kind','ledger_anchor','previous_hash','data'))
        if fingerprint(e)!=event['hash'] or e['index']!=i or e['previous_hash']!=previous or e['ledger_anchor'] not in indices or indices[e['ledger_anchor']]<last or e['kind'] not in KINDS:raise ValueError('Broken V4 event chain')
        last=indices[e['ledger_anchor']];previous=event['hash'];d=e['data'];clean(d);closed(d,KINDS[e['kind']])
        refs={x['hash'] for x in record['ledger'][:last+1] if json.loads(x['body_canonical'])['type']=='observation'}
        if e['kind'].startswith('approval_'):
            binding=d['binding'];closed(binding,('schema_version','session_id','request_id','epoch','experiment','experiment_sha256','screen','screen_sha256','policy_id','budget','expires_at'))
            if binding['session_id']!=b['session_id'] or binding['policy_id']!=b['policy_id'] or d['state'] not in TRANSITIONS:raise ValueError('Invalid public approval record')
            if fingerprint(binding['experiment'])!=binding['experiment_sha256'] or fingerprint(binding['screen'])!=binding['screen_sha256']:raise ValueError('Approval content changed')
            from ..v2_experiments import parse_trial
            parse_trial(binding['experiment']['name'],binding['experiment']['params'])
            if type(d['audit']) is not list or not 1<=len(d['audit'])<=8:raise ValueError('Invalid approval audit')
            for a in d['audit']:closed(a,('state','reason','at'))
        elif e['kind']=='joint_fit':
            from .models import PAIRS
            if d['hypothesis'] not in PAIRS or d['components']!=PAIRS[d['hypothesis']]['components'] or not set(d['evidence_refs'])<=refs or d['starts'] not in (1,2) or d['parameter_start_cost']!=2*d['starts'] or d['rank'] not in (0,1,2):raise ValueError('Invalid joint-fit provenance')
            if not 2<=len(d['local_sensitivity_matrix'])<=10000 or any(type(row) is not list or len(row)!=2 for row in d['local_sensitivity_matrix']):raise ValueError('Invalid local sensitivity matrix')
        elif e['kind']=='execution' and d['observation_ref'] not in refs:raise ValueError('Unknown executed observation')
        elif e['kind']=='critic_review':
            from ..muse_critic import validate_review
            if d['entry'].get('status')=='validated':validate_review(d['entry']['review'],refs)
    return b


def export(lab,record_path,sidecar_path):
    from ..v3_validation import clean
    record=public_source(lab);extra=sidecar(lab);validate(extra,record);clean(record)
    root=Path(__file__).resolve().parents[2]
    for path,value in ((record_path,record),(sidecar_path,extra)):
        path=Path(path).resolve()
        if path==root or root in path.parents:raise ValueError('Generated records remain outside source tree')
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        import os
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as out:out.write(canonical(value)+'\n')
