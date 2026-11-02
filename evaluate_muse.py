"""Frozen paired Muse evaluation. Private manifests/results never belong in Git."""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import secrets
import subprocess
import time
import numpy as np
import scipy
from nautilus.controller_context import canonical, fingerprint, build_controller_context, initialize_controller_context
from nautilus.investigator import DeterministicInvestigator
from nautilus.lab_safety import SafeBackend
from nautilus.laboratory import Laboratory
from nautilus.muse import MetaProvider, DEFAULT_MODEL, ENDPOINT
from nautilus.muse_investigator import PROMPT, Limits, function_tools, run as muse_run, public_source, validate_provenance
from nautilus.muse_context import project_result, restore_result
from nautilus.simulator import Faults, Controller, PlantConfig, Mission, Vehicle, validate as validate_physics, simulate, OBSERVATION_FIELDS
from nautilus.v2_models import REGISTRY, catalog, finding
from nautilus.v2_experiments import LIBRARY
from nautilus.v2_tools import capability_schema
from evaluate_active import wilson

ROOT=Path(__file__).resolve().parent
CANDIDATE='340d1c12e1f39252a84b4aaae59dd149b1d2b93b'
VERSION='nautilus.muse-evaluation.v1'
KINDS=('nominal','nominal','current_positive','current_negative','port','starboard',
       'bias_positive','bias_negative','current_bias','current_port','controller','joint_plant')
POLICIES=('fixed_reference','fixed_matched','muse')
MODEL_LIMITS=Limits(model_calls=12,actions=12,output_tokens_per_call=4096,output_tokens_total=32768,input_tokens_total=350000,retries=0)
LAB_LIMITS={'fit_budget':8,'optimization_budget':16,'experiment_budget':1,'time_budget_s':16.,'starts':2}
FAMILIES={'nominal':'nominal','lateral_current':'current','port_degradation':'thruster','starboard_degradation':'thruster',
 'heading_bias':'sensor','actuator_lag':'plant','thrust_deadzone':'plant','drag_surge':'plant','drag_sway':'plant',
 'drag_yaw':'plant','uniform_drag_scale':'plant','common_thrust_scale':'thruster',
 'heading_controller_gain':'controller','controller_lookahead':'controller'}
DISTRIBUTIONS={'current_abs':[.30,.65],'efficiency':[.30,.60],'heading_bias_abs':[.25,.50],
 'controller_heading_kp':[8.,20.],'joint_plant_tau':[.4,.8],'joint_plant_deadzone':[1.,3.]}
SCORING={'exact':'Current healthy-range physical finding equals the complete injected mechanism set; nominal maps to nominal.',
 'representable':'Singleton and nominal only; compounds and joint plant have no full singleton template.',
 'partial':'A scalar prediction matches one constituent of a multi-mechanism truth; never complete compound credit.',
 'family':'Exact family set equality; compound constituent-family coverage reported separately.',
 'unsupported_supported':'confidence supported and physical finding not in injected mechanisms; incomplete supported constituent claims counted separately.',
 'identifiability':'No independent reference; no identifiable subset or correct-abstention metric.',
 'discrimination':'Change in gap<=6 competitive-set size on >=2 identical hypothesis IDs fitted before and after an experiment; conditional numerical metric, not physical identifiability.',
 'denominators':'All attempted cases for reliability; representable attempted cases and representable voluntary completions separately for exact finding.',
 'interval':'95% Wilson descriptive marginal intervals; paired wins/losses/ties, no superiority claim.',
 'failures':'All started cases retained; host/provider failures are not voluntary scientific abstentions.'}
NOTE='Investigation session. Use only the supplied public evidence; private evaluator metadata is unavailable.'


def private_path(path):
    p=Path(path).resolve()
    if p==ROOT or ROOT in p.parents: raise ValueError('Private evaluation data must stay outside checkout')
    return p


def write_private(path,value):
    path=private_path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    data=canonical(value)+'\n'
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:f.write(data)


def sources():
    paths=sorted((ROOT/'nautilus').glob('*.py'))+[ROOT/'evaluate_muse.py',ROOT/'evaluate_active.py',ROOT/'MUSE_EVALUATION_PROTOCOL.md',ROOT/'frontend/export_records.py',ROOT/'frontend/src/records.ts',ROOT/'frontend/src/controller.ts',ROOT/'frontend/src/muse-provenance.ts']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def runtime():
    return {'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'platform':platform.platform(),
      'threads':{k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')}}


def make_manifest(*,seed_base=None,shuffle_seed=None):
    """Reserve seeds only: no physical case is generated here."""
    for path in sorted((ROOT/'nautilus').glob('*.py')):
        expected=subprocess.check_output(['git','show',CANDIDATE+':'+str(path.relative_to(ROOT))],cwd=ROOT)
        if path.read_bytes()!=expected:raise ValueError('Candidate implementation changed')
    if seed_base is None:seed_base=2**52+secrets.randbelow(2**40)*64
    if shuffle_seed is None:shuffle_seed=secrets.randbits(64)
    if type(seed_base) is not int or seed_base<2**40:raise ValueError('Disjoint private seed block required')
    order=np.random.default_rng(shuffle_seed).permutation(len(KINDS)).tolist()
    plans=[{'case_id':f'E{i+1:02d}','seed':seed_base+i,'kind':KINDS[k]} for i,k in enumerate(order)]
    m={'schema_version':VERSION,'purpose':'offline-fixture' if seed_base<2**52 else 'prospective-holdout','candidate_commit':CANDIDATE,
       'evaluator_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
       'sources':sources(),'runtime':runtime(),'prompt':PROMPT,'prompt_hash':fingerprint(PROMPT),
       'tools':function_tools(),'tool_hash':fingerprint(function_tools()),'capabilities':capability_schema(),
       'registry':catalog(),'experiments':[asdict(t) for t in LIBRARY],
       'controller_context':build_controller_context(),'sensor_schema':list(OBSERVATION_FIELDS),
       'model':DEFAULT_MODEL,'endpoint':ENDPOINT,'reasoning_effort':'low','model_limits':asdict(MODEL_LIMITS),
       'laboratory_limits':LAB_LIMITS,'safety_mode':'simulation_advisory','initial_duration_s':2.,'note':NOTE,
       'baseline_policies':list(POLICIES[:-1]),'baseline_action_limit':12,
       'baseline_registry_order':list(REGISTRY),'baseline_fixed_trial':asdict(LIBRARY[0]),
       'baseline_matched_rule':'Existing fixed policy numerical selection; fixed library[0] experiment first, then existing registry-order fits and finalize.',
       'plans':plans,'private_shuffle_seed':shuffle_seed,'distributions':DISTRIBUTIONS,'scoring':SCORING,'family_map':FAMILIES,
       'campaign':{'case_limit':12,'measured_input_limit':4200000,'reserved_output_limit':393216,'estimated_target_usd':15.,'pricing':'unverified'},
       'seed_audit':{'historical_upper_reserved':2000000,'offline_evaluator_fixture_seeds':[2**40+404000,2**40+404011],'source_history':'V1/V2 exposed per DRAFT_RELIABILITY_PROTOCOL_V3; never reused',
         'new_reservation':'Private entropy-selected high block; distinct from source/development literals and observed manifest metadata.',
         'limitation':'Prospective holdout relative to audited checkout/workspace; no assertion about inaccessible external experiments.'},
       'selection':'All 12 without qualification/resampling; fixed balanced mix shuffled before generation.',
       'analysis':'Case-level paired descriptive comparison; no tuning, correct-abstention score or benchmark selection from outcomes. Stop campaign after a provider failure or technical defect; preserve partial results.'}
    m=deepcopy(m)
    m['fingerprint']=fingerprint(m)
    return m


def validate_manifest(m):
    if fingerprint({k:v for k,v in m.items() if k!='fingerprint'})!=m.get('fingerprint'):raise ValueError('Manifest modified')
    if m['schema_version']!=VERSION or m['sources']!=sources() or m['runtime']!=runtime():raise ValueError('Frozen source/runtime changed')
    if m['prompt']!=PROMPT or m['tool_hash']!=fingerprint(function_tools()):raise ValueError('Frozen model contract changed')
    plans=m['plans']
    if len(plans)!=12 or len({p['seed'] for p in plans})!=12 or len({p['case_id'] for p in plans})!=12 or Counter(p['kind'] for p in plans)!=Counter(KINDS):raise ValueError('Invalid frozen case plan')
    if any(p['seed']<2**40 for p in plans):raise ValueError('Seed overlap with audited historical region')
    if m['model_limits']!=asdict(MODEL_LIMITS) or m['laboratory_limits']!=LAB_LIMITS or m['distributions']!=DISTRIBUTIONS or m['scoring']!=SCORING:raise ValueError('Frozen rules changed')


def freeze(directory):
    directory=private_path(directory);directory.mkdir(mode=0o700,parents=True,exist_ok=False)
    m=make_manifest();p=directory/'manifest.json';write_private(p,m);os.chmod(p,0o400)
    file_hash=hashlib.sha256(p.read_bytes()).hexdigest()
    write_private(directory/'manifest-sha256.json',{'file_sha256':file_hash,'body_fingerprint':m['fingerprint']})
    return {'file_sha256':file_hash,'body_fingerprint':m['fingerprint']}


def generate(plan):
    """Trusted generation only; no filtering on mission, residuals or predictions."""
    rng=np.random.default_rng(plan['seed']);k=plan['kind'];f=Faults();plant=PlantConfig();control=Controller();mechanisms=[]
    if k.startswith('current_') or k=='current_port':
        sign=-1 if k=='current_negative' else 1
        f=replace(f,current_y=float(sign*rng.uniform(*DISTRIBUTIONS['current_abs'])));mechanisms.append('lateral_current')
    if k in ('port','starboard','current_port'):
        side='starboard' if k=='starboard' else 'port'
        f=replace(f,**{side+'_efficiency':float(rng.uniform(*DISTRIBUTIONS['efficiency']))});mechanisms.append(side+'_degradation')
    if k in ('bias_positive','bias_negative','current_bias'):
        sign=1 if k=='bias_positive' else -1
        f=replace(f,heading_bias_rad=float(sign*rng.uniform(*DISTRIBUTIONS['heading_bias_abs'])));mechanisms.append('heading_bias')
    if k=='controller':
        control=replace(control,heading_kp=float(rng.uniform(*DISTRIBUTIONS['controller_heading_kp'])));mechanisms.append('heading_controller_gain')
    if k=='joint_plant':
        plant=replace(plant,actuator_tau_s=float(rng.uniform(*DISTRIBUTIONS['joint_plant_tau'])),thrust_deadzone_n=float(rng.uniform(*DISTRIBUTIONS['joint_plant_deadzone'])));mechanisms.extend(['actuator_lag','thrust_deadzone'])
    if k=='nominal':mechanisms=['nominal']
    if not mechanisms:raise ValueError('Unsupported predeclared stratum')
    return {'faults':asdict(f),'plant':asdict(plant),'controller':asdict(control),
            'mechanisms':mechanisms,'families':sorted({FAMILIES[x] for x in mechanisms}),
            'representable':len(mechanisms)==1}


def create_lab(case,plan):
    faults=Faults(**case['faults']);plant=PlantConfig(**case['plant']);controller=Controller(**case['controller'])
    rows=simulate(faults=faults,plant=plant,controller=controller,mission=Mission(duration_s=2.,seed=plan['seed'])).observations
    lab=Laboratory(rows,SafeBackend(faults=faults,plant=plant,controller=controller,seed=plan['seed'],mode='simulation_advisory'),note=NOTE,**LAB_LIMITS)
    initialize_controller_context(lab,build_controller_context()) # declared, never private actual settings
    return lab


class MatchedFixed(DeterministicInvestigator):
    def __init__(self):super().__init__('fixed');self.first=True
    def choose(self,state):
        if self.first:
            self.first=False;trial=LIBRARY[0];self.attempted.add(trial.key)
            return {'op':'request_experiment','name':trial.name,'params':trial.params()}
        return super().choose(state)


class AuditedProvider:
    """Retain bounded structured calls only, never provider reasoning or headers."""
    def __init__(self,provider):
        self.base=provider;self.model=provider.model;self.provider=provider.provider
        self.reasoning_effort=getattr(provider,'reasoning_effort',None);self.calls=[]
        if callable(getattr(provider,'request_size',None)):self.request_size=provider.request_size
    def generate(self,**kwargs):
        reply=self.base.generate(**kwargs)
        self.calls.append({'response_id':reply.response_id,'status':reply.status,
            'calls':[{'name':c['name'],'call_id':c['call_id'],'arguments':c['arguments']} for c in reply.calls]})
        return reply


def baseline_run(lab,name):
    policy=MatchedFixed() if name=='fixed_matched' else DeterministicInvestigator('fixed')
    actions=[];origin='host';started=time.monotonic()
    for _ in range(12):
        payload=policy.choose(lab.get_fit_report());ok=False
        try:lab.call(payload);ok=True
        except ValueError:pass
        actions.append({'payload':payload,'accepted':ok})
        if lab._closed:origin='policy';break
    if not lab._closed:
        lab.call({'op':'finalize','diagnosis':{'hypothesis':None,'evidence_refs':lab.evidence_refs()},'confidence':'abstain','ambiguity_statement':'HOST-ENFORCED ABSTENTION: baseline action limit'})
    return {'public_record':public_source(lab),'actions':actions,'origin':origin,'elapsed_s':time.monotonic()-started}


def closed_metrics(lab,result,policy):
    if not lab._closed:raise ValueError('Scoring an open laboratory is prohibited')
    record=result['public_record'];events=[json.loads(e['body_canonical']) for e in record['ledger']]
    final=events[-1]
    if final['type']!='finalized':raise ValueError('Missing final evidence event')
    refs=lab.evidence_refs();assert all(x in refs for x in final['diagnosis']['evidence_refs'])
    before={};after={};post=False
    for e in events:
        if e['type']=='observation' and e.get('request'):post=True
        if e['type']=='fit':(after if post else before)[e['report']['hypothesis']]=e['report']
    common=set(before)&set(after);discrimination=None
    if len(common)>=2:
        def competitive(reports):
            values={h:reports[h]['penalized_score'] for h in common if reports[h]['converged']}
            return {h for h,v in values.items() if v<=min(values.values())+6} if values else set()
        pre,postset=competitive(before),competitive(after)
        discrimination={'common_models':len(common),'before':len(pre),'after':len(postset),'reduction':len(pre)-len(postset)}
    reports=[e['report'] for e in events if e['type']=='fit'];diagnosis=final['diagnosis']['hypothesis'];physical=None
    if diagnosis is not None:
        current=next((f for f in lab.get_fit_report()['fits'] if f['hypothesis']==diagnosis),None)
        if current is None:raise ValueError('Stale diagnosis')
        from types import SimpleNamespace
        physical=finding(SimpleNamespace(**current))
    provenance=result.get('provenance');b=validate_provenance(provenance,record) if provenance else None
    proposed=sum(c['name']=='request_experiment' for turn in result.get('structured_calls',[]) for c in turn['calls']) if b else sum(a['payload'].get('op')=='request_experiment' for a in result['actions'])
    screened=sum(e['type']=='safety' for e in events)
    return {'origin':b['finalization_origin'] if b else result['origin'],'reason':b['termination_reason'] if b else 'policy_finalized' if result['origin']=='policy' else 'action_limit',
      'confidence':final['confidence'],'hypothesis':diagnosis,'physical_finding':physical,'final_decision':final,
      'evidence_refs_valid':True,'fit_calls':lab.fit_calls,'optimization_starts':lab.optimization_attempts,
      'fit_converged':sum(f['converged'] for f in reports),'fit_failures':sum(e['type']=='fit_failure' for e in events),
      'saturated_fits':sum(bool(f.get('bound_hits')) for f in reports),'distinct_hypotheses':len({f['hypothesis'] for f in reports}),
      'proposed_experiments':proposed,'screened_experiment_proposals':screened,'unassessed_experiment_proposals':max(0,proposed-screened),
      'returned_tool_calls':sum(x['function_calls'] for x in b['model_requests']) if b else len(result['actions']),
      'experiments':lab.tests,'simulation_s':lab.test_time_s,'discrimination':discrimination,
      'predictive_warnings':sum(e['type']=='safety' and e['screen'].get('would_reject_enforced',False) for e in events),
      'observed_excursions':sum(e['type']=='observation' and e.get('execution',{}).get('observed_excursion',False) for e in events),
      'guard_interventions':sum(e['type']=='observation' and e.get('execution',{}).get('guard_intervened',False) for e in events),
      'model_requests':len(b['model_requests']) if b else 0,'usage':{k:sum(r['usage'].get(k,0) for r in b['model_requests']) if b else 0 for k in ('input_tokens','cached_input_tokens','output_tokens','reasoning_tokens','total_tokens')},
      'reserved_output':b['output_tokens_reserved'] if b else 0,'latency_s':b['elapsed_s'] if b else result['elapsed_s'],
      'unreported_usage_requests':sum(not {'input_tokens','output_tokens'}<=set(r['usage']) for r in b['model_requests']) if b else 0,
      'provider_errors':b['errors'] if b else [],'action_attempts':len(b['actions']) if b else len(result['actions']),
      'accepted_actions':sum(a['accepted'] for a in b['actions']) if b else sum(a['accepted'] for a in result['actions'])}


def score(case,metrics):
    complete=metrics['origin'] in ('model','policy')
    pred=metrics['physical_finding'];truth=set(case['mechanisms']);family=FAMILIES.get(pred)
    exact=pred is not None and truth=={pred}
    constituent=pred in truth and len(truth)>1
    return {'raw_exact':bool(complete and metrics['hypothesis'] is not None and truth=={metrics['hypothesis']}),'voluntary_complete':complete,'representable':case['representable'],'exact':bool(complete and exact),
      'partial_constituent':bool(complete and constituent),'family_exact':bool(complete and family is not None and set(case['families'])=={family}),
      'partial_family':bool(complete and family in case['families'] and len(case['families'])>1),
      'truth_inconsistent_supported':bool(complete and metrics['confidence']=='supported' and pred not in truth),
      'supported_incomplete':bool(complete and metrics['confidence']=='supported' and constituent),
      'tentative':bool(complete and metrics['confidence']=='tentative'),'scientific_abstention':bool(complete and metrics['confidence']=='abstain'),
      'out_of_registry':not case['representable']}


def exporter():
    spec=importlib.util.spec_from_file_location('muse_eval_export',ROOT/'frontend/export_records.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def validate_and_export(directory,lab,result):
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    module=exporter();source=directory/'public-source.json'
    write_private(source,{'history':lab.ledger})
    public=module.public_record(source)
    if public['ledger']!=result['public_record']['ledger']:raise ValueError('Export changed evidence')
    module.reject_private(public);write_private(directory/'public-investigation.json',public)
    if 'provenance' in result:validate_provenance(result['provenance'],public)


def aggregate(records):
    out={}
    for policy in POLICIES:
        pairs=[(r['metrics'][policy],r['scores'][policy]) for r in records]
        n=len(pairs);representable=[s for _,s in pairs if s['representable']];completed=[s for _,s in pairs if s['voluntary_complete']];valid_repr=[s for s in completed if s['representable']]
        exact=sum(s['exact'] for s in representable)
        totals={key:sum(s[key] for _,s in pairs) for key in ('raw_exact','exact','partial_constituent','family_exact','partial_family','truth_inconsistent_supported','supported_incomplete','tentative','scientific_abstention')}
        out[policy]={'attempted':n,'voluntary_completions':len(completed),'host_terminations':n-len(completed),
          **totals,'representable_attempted':len(representable),'representable_completed':len(valid_repr),
          'exact_representable_95_wilson':wilson(exact,len(representable)),
          'conditional_exact_rate':sum(s['exact'] for s in valid_repr)/len(valid_repr) if valid_repr else None,
          'representable_diagnoses':sum(not s['scientific_abstention'] for s in valid_repr),
          'selective_exact_rate':sum(s['exact'] for s in valid_repr)/sum(not s['scientific_abstention'] for s in valid_repr) if any(not s['scientific_abstention'] for s in valid_repr) else None,
          'requests':sum(m['model_requests'] for m,_ in pairs),'usage':{key:sum(m['usage'][key] for m,_ in pairs) for key in ('input_tokens','cached_input_tokens','output_tokens','reasoning_tokens','total_tokens')},
          'reserved_output':sum(m['reserved_output'] for m,_ in pairs),'latency_s':sum(m['latency_s'] for m,_ in pairs),
          **{key:sum(m[key] for m,_ in pairs) for key in ('fit_calls','optimization_starts','proposed_experiments','screened_experiment_proposals','unassessed_experiment_proposals','returned_tool_calls','unreported_usage_requests','experiments','simulation_s','predictive_warnings','observed_excursions','guard_interventions','fit_converged','fit_failures','saturated_fits','accepted_actions','action_attempts')},
          'provider_failure_cases':sum(bool(m['provider_errors']) for m,_ in pairs),
          'numerical_ambiguity':sum(m['final_decision'].get('numerical_summary',{}).get('kind')=='ambiguous' for m,_ in pairs),
          'out_of_registry_cases':sum(s['out_of_registry'] for _,s in pairs),
          'discrimination_available':sum(m['discrimination'] is not None for m,_ in pairs),
          'discrimination_narrowed':sum(m['discrimination'] is not None and m['discrimination']['reduction']>0 for m,_ in pairs)}
    out['paired']={key:sum((int(r['scores']['muse'][key])-int(r['scores']['fixed_matched'][key])) for r in records) for key in ('exact','family_exact','scientific_abstention')}
    out['paired_exact_discordance']={'muse_only':sum(r['scores']['muse']['exact'] and not r['scores']['fixed_matched']['exact'] for r in records),
      'fixed_only':sum(r['scores']['fixed_matched']['exact'] and not r['scores']['muse']['exact'] for r in records)}
    return out


def completed_records(directory,m):
    records=[]
    for plan in m['plans']:
        path=directory/(plan['case_id']+'.completed.json')
        if path.exists():
            r=json.loads(path.read_text());h=r.pop('result_hash')
            if fingerprint(r)!=h or r['manifest_fingerprint']!=m['fingerprint'] or r['case_id']!=plan['case_id']:raise ValueError('Corrupt checkpoint')
            r['result_hash']=h;records.append(r)
    return records


def run_campaign(directory,*,provider_factory=None,batch=12):
    directory=private_path(directory);m=json.loads((directory/'manifest.json').read_text());validate_manifest(m)
    expected=json.loads((directory/'manifest-sha256.json').read_text())
    if hashlib.sha256((directory/'manifest.json').read_bytes()).hexdigest()!=expected['file_sha256']:raise ValueError('Frozen manifest file changed')
    if provider_factory is None:
        if m.get('purpose')!='prospective-holdout' or any(p['seed']<2**52 for p in m['plans']):raise ValueError('Offline fixture cannot authorize real inference')
        provider_factory=lambda:MetaProvider(model=DEFAULT_MODEL,reasoning_effort='low')
    # Preflight every frozen stratum before the first live request, without scoring.
    for plan in m['plans']:
        case=generate(plan)
        validate_physics(Vehicle(),Faults(**case['faults']),Controller(**case['controller']),Mission(),PlantConfig(**case['plant']))
    completed=completed_records(directory,m);ran=0
    if any(r['metrics']['muse']['reason']=='provider_error' for r in completed):raise ValueError('Campaign stopped after provider failure; no automatic resume')
    for plan in m['plans']:
        if any(r['case_id']==plan['case_id'] for r in completed):continue
        marker=directory/(plan['case_id']+'.started.json')
        if marker.exists():raise ValueError('Interrupted case: do not automatically rerun or continue a defective protocol')
        input_used=sum(r['metrics']['muse']['usage']['input_tokens'] for r in completed)
        output_used=sum(r['metrics']['muse']['reserved_output'] for r in completed)
        if len(completed)>=12 or input_used>=4200000 or output_used+32768>393216:break
        if ran>=batch:break
        write_private(marker,{'case_id':plan['case_id'],'manifest_fingerprint':m['fingerprint'],'state':'started'})
        case_started=time.monotonic()
        case=generate(plan);labs={name:create_lab(case,plan) for name in POLICIES}
        initial=[fingerprint(l.ledger) for l in labs.values()]
        if len(set(initial))!=1:raise ValueError('Paired initial evidence differs')
        results={};metrics={}
        for policy in POLICIES[:-1]:
            results[policy]=baseline_run(labs[policy],policy)
            validate_and_export(directory/plan['case_id']/policy,labs[policy],results[policy])
            metrics[policy]=closed_metrics(labs[policy],results[policy],policy)
        audited=AuditedProvider(provider_factory())
        limits=replace(MODEL_LIMITS,input_tokens_total=min(350000,4200000-input_used))
        results['muse']=muse_run(labs['muse'],audited,limits=limits)
        results['muse']['structured_calls']=audited.calls
        validate_and_export(directory/plan['case_id']/'muse',labs['muse'],results['muse'])
        metrics['muse']=closed_metrics(labs['muse'],results['muse'],'muse')
        # All inference is closed before any truth-based score is computed.
        scores={policy:score(case,metrics[policy]) for policy in POLICIES}
        r={'case_id':plan['case_id'],'manifest_fingerprint':m['fingerprint'],'private_case':case,
           'metrics':metrics,'scores':scores,'initial_evidence_hash':initial[0],'case_elapsed_s':time.monotonic()-case_started}
        for policy in POLICIES:write_private(directory/plan['case_id']/(policy+'.json'),results[policy])
        r['result_hash']=fingerprint(r);write_private(directory/(plan['case_id']+'.completed.json'),r)
        completed.append(r);ran+=1
        # Operational progress only: no labels, predictions or scores while cases remain.
        print(canonical({'case_id':plan['case_id'],'terminal_cases':len(completed),'model_requests':metrics['muse']['model_requests'],
                         'input_tokens':metrics['muse']['usage']['input_tokens'],'output_tokens':metrics['muse']['usage']['output_tokens']}),flush=True)
        if metrics['muse']['reason']=='provider_error':break # predeclared campaign stop; never retry failed access
    return {'planned':12,'attempted':len(list(directory.glob('E*.started.json'))),'terminal_pairs':len(completed),'summary':aggregate(completed)}


def sanitized_report(directory):
    directory=private_path(directory);m=json.loads((directory/'manifest.json').read_text());validate_manifest(m)
    records=completed_records(directory,m);summary=aggregate(records)
    attempted=len(list(directory.glob('E*.started.json')))
    representable_attempted=sum((directory/(p['case_id']+'.started.json')).exists() and p['kind'] not in ('current_bias','current_port','joint_plant') for p in m['plans'])
    for policy in POLICIES:
        info=summary[policy];info['scored_terminal_pairs']=len(records);info['attempted']=attempted
        info['unscored_started']=attempted-len(records);info['end_to_end_completion_rate']=info['voluntary_completions']/attempted if attempted else None
        info['representable_attempted']=representable_attempted
        info['exact_representable_95_wilson']=wilson(info['exact'],representable_attempted)
    summary['paired_terminal_pairs']=len(records)
    public={'schema_version':'nautilus.muse-evaluation-summary.v1','manifest_fingerprint':m['fingerprint'],
      'manifest_file_sha256':json.loads((directory/'manifest-sha256.json').read_text())['file_sha256'],
      'model':m['model'],'endpoint':m['endpoint'],'reasoning_effort':m['reasoning_effort'],
      'model_limits':m['model_limits'],'laboratory_limits':m['laboratory_limits'],'safety_mode':m['safety_mode'],
      'budget_policy':m['campaign'],'estimated_cost_usd':None,
      'candidate_commit':CANDIDATE,'evaluator_commit':m['evaluator_commit'],'sources':m['sources'],'runtime':m['runtime'],
      'planned':12,'attempted':attempted,'terminal_pairs':len(records),'campaign_case_time_s':sum(r.get('case_elapsed_s',0) for r in records),'summary':summary,
      'cases':[{'case_id':r['case_id'],'policies':{p:{'origin':r['metrics'][p]['origin'],'confidence':r['metrics'][p]['confidence'],
            'exact':r['scores'][p]['exact'],'partial_constituent':r['scores'][p]['partial_constituent'],
            'model_requests':r['metrics'][p]['model_requests'],'reason':r['metrics'][p]['reason'],
            'usage':r['metrics'][p]['usage'],'latency_s':r['metrics'][p]['latency_s'],'fits':r['metrics'][p]['fit_calls'],
            'experiments':r['metrics'][p]['experiments'],'observed_excursions':r['metrics'][p]['observed_excursions']} for p in POLICIES}} for r in records],
      'strata':{name:{p:{'cases':len(rows),'exact':sum(r['scores'][p]['exact'] for r in rows),'completed':sum(r['scores'][p]['voluntary_complete'] for r in rows),'partial_constituent':sum(r['scores'][p]['partial_constituent'] for r in rows),'abstained':sum(r['scores'][p]['scientific_abstention'] for r in rows)} for p in POLICIES}
                for name,rows in [(name,[r for r in records if group(r['private_case'])==name]) for name in ('nominal','current','thruster','sensor','compound','mismatch')]},
      'limitations':['Twelve balanced simulated cases, not population prevalence.','No independent identifiability oracle or correct-abstention score.',
        'Resource-matched fixed experiment-first variant is distinct from original fixed reference.','New high-entropy seeds; inaccessible external usage cannot be audited.',
        'No verified tariff: monetary amount unavailable; $15 target not enforceable, token/request fallback used.']}
    return public


def group(case):
    if len(case['mechanisms'])>1:return 'mismatch' if set(case['families'])=={'plant'} else 'compound'
    return 'mismatch' if case['families']==['controller'] else case['families'][0]


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['freeze','run','summary'])
    parser.add_argument('--directory',required=True);parser.add_argument('--authorize-api',action='store_true');parser.add_argument('--batch',type=int,default=12)
    args=parser.parse_args()
    if args.action=='freeze':print(canonical(freeze(args.directory)))
    elif args.action=='run':
        if not args.authorize_api:parser.error('Explicit campaign authorization required')
        if not 1<=args.batch<=12:parser.error('Bounded batch required')
        result=run_campaign(args.directory,batch=args.batch)
        print(canonical({k:v for k,v in result.items() if k!='summary'}))
    else:
        result=sanitized_report(args.directory);write_private(Path(args.directory)/'sanitized-summary.json',result)
        print('Sanitized summary saved; review separately from private records.')
