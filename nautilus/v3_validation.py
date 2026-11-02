"""Strict allowlisted sidecar validation; original evidence schema stays unchanged."""
import json,math
from .controller_context import fingerprint
from .muse_investigator import validate_provenance,validate_call
from .muse_critic import validate_review
from .v2_experiments import parse_trial
from .active_planner import candidates,SCALES


def closed(v,keys):
    if type(v) is not dict or set(v)!=set(keys):raise ValueError('Unexpected V3 fields')


def clean(v):
    if type(v) is dict:
        for k,x in v.items():
            if any(w in k.lower() for w in ('private','oracle','ground_truth','injected','credential','authorization')) or k in ('faults','plant','truth','seed'):raise ValueError('Nonpublic V3 content')
            clean(x)
    elif type(v) is list:
        for x in v:clean(x)
    elif type(v) is float and not math.isfinite(v):raise ValueError('Nonfinite V3 content')


def validate(value,record,investigator):
    closed(value,('schema_version','body_canonical','hash'))
    if value['schema_version']!='nautilus.v3-provenance.v1' or type(value['body_canonical']) is not str or len(value['body_canonical'].encode())>2000000:raise ValueError('Invalid V3 envelope')
    b=json.loads(value['body_canonical'])
    if fingerprint(b)!=value['hash']:raise ValueError('Invalid V3 hash')
    closed(b,('schema_version','flags','model','reasoning_effort','investigator_provenance_hash','ledger_anchor','events','critic','planning_passes','planning_limit','critic_request_limit','critic_failure','total_elapsed_s','scientific_validation'))
    clean(b);p=validate_provenance(investigator,record)
    if b['schema_version']!='nautilus.v3-provenance-body.v1' or b['investigator_provenance_hash']!=investigator['hash'] or b['ledger_anchor']!=record['ledger'][-1]['hash'] or b['model']!=p['model']:raise ValueError('Unlinked V3 provenance')
    closed(b['flags'],('risk_aware_planning','enforced_experiment_safety','critic_enabled','prediction_audit_enabled'))
    if any(type(v) is not bool for v in b['flags'].values()):raise ValueError('Invalid V3 flags')
    if p['safety_mode']!=('simulation_enforced' if b['flags']['enforced_experiment_safety'] else 'simulation_advisory'):raise ValueError('Safety flag mismatch')
    if b['planning_limit']!=4 or type(b['planning_passes']) is not int or not 0<=b['planning_passes']<=4 or b['critic_request_limit']!=1 or type(b['critic_failure']) is not bool:raise ValueError('Invalid V3 limits')
    if type(b['total_elapsed_s']) not in (int,float) or b['total_elapsed_s']<0 or b['reasoning_effort'] not in (None,'low'):raise ValueError('Invalid V3 runtime')
    ledger={x['hash']:i for i,x in enumerate(record['ledger'])};allrefs={x['hash'] for x in record['ledger'] if json.loads(x['body_canonical'])['type']=='observation'}
    previous=None;last=0;kinds=[];reviews=[];pending=[];responses=[]
    if type(b['events']) is not list or len(b['events'])>40:raise ValueError('Unbounded V3 events')
    for i,event in enumerate(b['events']):
        closed(event,('body_canonical','hash'));ev=json.loads(event['body_canonical'])
        closed(ev,('index','kind','ledger_anchor','previous_hash','data'))
        if fingerprint(ev)!=event['hash'] or ev['index']!=i or ev['previous_hash']!=previous or ev['ledger_anchor'] not in ledger or ledger[ev['ledger_anchor']]<last:raise ValueError('Invalid V3 event chain')
        last=ledger[ev['ledger_anchor']];previous=event['hash'];kind=ev['kind'];d=ev['data'];kinds.append(kind)
        refs={x['hash'] for x in record['ledger'][:last+1] if json.loads(x['body_canonical'])['type']=='observation'}
        if kind=='numerical_plan':
            closed(d,('schema_version','evidence_refs','fit_names','fit_fingerprint','status','candidate_count','forward_simulations','scales','cost','recommended_ids','rows','qualification'))
            if d['schema_version']!='nautilus.experiment-plan.v3' or d['candidate_count']!=36 or len(d['rows'])!=36 or not set(d['evidence_refs'])<=refs or d['scales']!=SCALES or not 0<=d['forward_simulations']<=144:raise ValueError('Invalid V3 plan')
            accepted=[]
            for row,t in zip(d['rows'],candidates()):
                closed(row,('candidate_id','name','params','accepted','predictive_margin_m','discrimination','utility','forecast_available','forecast_error','within_budget'))
                if row['candidate_id']!=t.key or row['name']!=t.name or row['params']!=t.params() or type(row['accepted']) is not bool or type(row['forecast_available']) is not bool:raise ValueError('Wrong V3 candidate')
                if row['accepted']:accepted.append(row['candidate_id'])
                if (not row['accepted'] or not row['within_budget']) and row['utility'] is not None:raise ValueError('Unsafe V3 recommendation')
                closed(row['discrimination'],('pairs','minimum','mean'))
                for pair in row['discrimination']['pairs']:closed(pair,('left','right','normalized_rms'))
            if not set(d['recommended_ids'])<=set(accepted):raise ValueError('Unsafe V3 recommendation')
        elif kind=='pending_finalization':
            validate_call('finalize',json.dumps(d));pending.append(d)
            if not set(d['diagnosis']['evidence_refs'])<=refs:raise ValueError('Unknown pending reference')
        elif kind=='critic_review':
            reviews.append(d)
            allowed={'status','http_status','usage','latency_s','packet_bytes','packet_sha256','model','reasoning_effort','request_limit','output_limit','token_measurement','error','review','response_id','output_reserved','incomplete_reason'}
            if type(d) is not dict or set(d)-allowed or not {'status','review','usage','latency_s','error','request_limit','output_reserved'}<=set(d):raise ValueError('Invalid critic provenance')
            if d['request_limit']!=1 or d.get('packet_bytes',0)>15000 or d['output_reserved']>2048 or d['latency_s']<0:raise ValueError('Critic limit overrun')
            if set(d['usage'])-{'input_tokens','cached_input_tokens','output_tokens','reasoning_tokens','total_tokens'} or any(type(v) is not int or v<0 for v in d['usage'].values()):raise ValueError('Invalid critic usage')
            if d['status']=='validated':validate_review(d['review'],refs)
            elif d['status']!='failed' or d['review'] is not None:raise ValueError('Missing critic failure')
        elif kind=='investigator_response':
            closed(d,('review_hash','proposal','changed','qualification'));responses.append(d)
            if not reviews or reviews[-1]['status']!='validated' or fingerprint(reviews[-1]['review'])!=d['review_hash'] or 'critic:'+d['review_hash'] not in d['proposal']['ambiguity_statement']:raise ValueError('Unlinked critic response')
            validate_call('finalize',json.dumps(d['proposal']))
        elif kind=='prediction_before':
            closed(d,('candidate_id','name','params','evidence_refs','leading','alternative','channels','predictions','qualification'))
            if parse_trial(d['name'],d['params']).key!=d['candidate_id'] or not set(d['evidence_refs'])<=refs or d['channels']!=list(SCALES):raise ValueError('Invalid prediction')
            if set(d['predictions'])!={d['leading'],d['alternative']}:raise ValueError('Missing forecasts')
            for rows in d['predictions'].values():
                if not 2<=len(rows)<=321:raise ValueError('Unbounded forecast')
                for row in rows:closed(row,('time_s',*SCALES))
        elif kind=='prediction_comparison':
            closed(d,('candidate_id','observation_ref','testable','normalized_rms','outcome','rule'))
            if d['observation_ref'] not in refs or d['outcome'] not in ('support','contradiction','inconclusive') or 'prediction_before' not in kinds[:-1]:raise ValueError('Invalid comparison')
        else:raise ValueError('Unsupported V3 event')
    if kinds.count('numerical_plan')!=b['planning_passes'] or len(reviews)>1 or len(pending)!=len(reviews) or b['critic']!=(reviews[0] if reviews else None):raise ValueError('Critic/plan count mismatch')
    if not b['flags']['critic_enabled'] and reviews:raise ValueError('Unexpected critic')
    if b['critic_failure']!=(bool(reviews) and reviews[0]['status']=='failed'):raise ValueError('Missing critic failure')
    if b['flags']['critic_enabled'] and p['finalization_origin']=='model' and (len(reviews)!=1 or reviews[0]['status']!='validated' or not responses):raise ValueError('Unreviewed V3 finalization')
    return b
