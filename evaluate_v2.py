"""Reduced, development-gated v2 evaluation. Private outputs are external only.

dev -> freeze -> run (--batch supports validated checkpoint resume).
No v1 benchmark answers are read. No held-out case is generated before freeze.
"""
from dataclasses import asdict,replace
from pathlib import Path
from collections import Counter
import argparse,hashlib,json,math,os,platform,random,time

import numpy as np
import scipy

from nautilus.simulator import (simulate,metrics,Faults,Controller,PlantConfig,
                                HIDDEN_PLANT,Mission,Experiment,OBSERVATION_FIELDS)
from nautilus.protocol import PassiveProtocol,passive,summary,digest
from nautilus.diagnosis import HYPOTHESES
from nautilus.v2_models import REGISTRY,EXTENSIONS,fit_model,finding,catalog
from nautilus.v2_experiments import LIBRARY,PrivateBackend
from nautilus.v2_tools import InvestigationSession,verdict,predicted_separation,public_fit,capability_schema
from nautilus.v2_context import presentations,keyword_prior,corpus_manifest

ROOT=Path(__file__).resolve().parent
UPSTREAM='eb2d4df93e318a2ee50ff465f9e921e9122c9d2d'
PLAN_FAMILIES=list(EXTENSIONS)+['actuator_lag','thrust_deadzone','actuator_lag']+[
    'lateral_current','port_degradation','starboard_degradation','heading_bias',
    'nominal','nominal','mismatch_control','mismatch_control']
ACTIVE_INDICES=tuple(range(20))
NOTE_INDICES=tuple(range(20))
DISTRIBUTIONS={'actuator_lag':[.3,1.1],'thrust_deadzone':[1.,5.],
               'drag_surge':[1.4,2.5],'drag_sway':[1.4,2.5],'drag_yaw':[1.4,2.5],
               'heading_controller_gain':[8.,20.],'controller_lookahead':[11.,18.],
               'common_thrust_scale':[.5,.9],'uniform_drag_scale':[1.2,2.],
               'lateral_current':[.3,.65],'port_degradation':[.3,.6],
               'starboard_degradation':[.3,.6],'heading_bias':[.3,.5]}


def write(path,value):
    path=Path(path).resolve()
    if ROOT==path or ROOT in path.parents:raise ValueError('Private data must be outside source repository')
    path.parent.mkdir(parents=True,exist_ok=True)
    serialized=json.dumps(value,indent=2,allow_nan=False)
    with path.open('x') as f:f.write(serialized+'\n')


def sources():
    paths=sorted((ROOT/'nautilus').glob('*.py'))+[ROOT/'evaluate_v2.py',ROOT/'develop_v2.py',ROOT/'ACTIVE_PROTOCOL_V2.md']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def runtime():
    return {'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,
            'threads':{k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')}}


def freeze(development):
    if development['groups']['common_drag']['qualified_ambiguity_family']:
        raise ValueError('This reduced protocol declares common/drag ambiguity excluded; review scope explicitly')
    if not development['groups']['lag_deadzone']['qualified_ambiguity_family']:
        raise ValueError('Tier1 lag/dead-zone development gate failed; no held-out generation permitted')
    m={'upstream':UPSTREAM,'sources':sources(),'runtime':runtime(),
       'development_fingerprint':digest(development),
       'plans':[{'case_id':f'v2-{i:03d}','index':i,'seed':900000+i,
                 'family':h,'stratum':'A' if i<12 else 'C' if i<16 else 'D',
                 'active_assessment':i in ACTIVE_INDICES} for i,h in enumerate(PLAN_FAMILIES)],
       'distributions':DISTRIBUTIONS,'sensor_schema':OBSERVATION_FIELDS,
       'window_s':30.,'cadence_s':.05,'mission_s':100.,'registry':catalog(),
       'scoring':{'physical_scales':[.035,.004,.003],'command_consistency_tolerance_n':.05,
                  'rank':'innovation SSE + digital consistency SSE + k*log(5*N)',
                  'adequacy':'max(physical WRMS, command WRMS)<=2','competitive_gap':6.,
                  'convergence':'Every fitted candidate must converge; failures are separate.'},
       'fit':{'starts':2,'max_nfev':40,'max_fit_calls':64,'max_optimization_attempts':128},
       'experiments':[asdict(r) for r in LIBRARY],
       'active':{'count_budget':2,'time_budget_s':32.,'strategies':['fixed','random','greedy'],
                 'predeclared_indices':ACTIVE_INDICES,
                 'scope':'All20 physical cases; no mechanism is excluded from active assessment based on development policy success.',
                 'mandatory_first_test':'All cases, including confident/error/inadequate and controls; no truth-based trigger.',
                 'stop':'After first test, stop only on unique adequate raw model identification; otherwise use second test.',
                 'greedy':'Mean pairwise forecast separation of all converged adequate fits; all converged fallback.',
                 'random_seed_start':1000000,'fixed_order':'Library order, broad differential step then excited coast-down.'},
       'notes':{'paired_physical_indices':NOTE_INDICES,'corpus':corpus_manifest(),
                'four_conditions_share_exact_physical_trace':True,'active_policies_note_condition':'absent',
                'context_scope':'Keyword preference mechanism over identical exhaustive fits; not an experiment policy.'},
       'inclusions':{'physical_extensions':list(EXTENSIONS),'ambiguity_family':'lag vs dead zone development qualified'},
       'exclusions':{'common_drag_ambiguity':'Failed0/20 competitiveness; not forced by changing magnitudes.',
                     'compounds':'Deferred; joint templates not qualified in this reduced milestone.',
                     'stratum_E':'Deferred entirely; missing command/sensor channels rejected, never imputed.',
                     'Tier2':'Deferred: cost-aware policy, Fisher ellipses, latent stress faults.',
                     'Tier3':'No time-varying currents, onset uncertainty, compass-heading effects, repairs, Muse or GUI.'},
       'resolvability':'Finite evidence sets actually acquired by the three frozen policies, not exhaustive library search. Retain unresolved/inconclusive cases.',
       'sampling':'20 physical cases: A12,C4,D4. No resampling or replacement. 20 paired note cases are presentations, not80 independent physical cases.',
       'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    m['fingerprint']=digest(m)
    return m


def validate(m):
    if digest({k:v for k,v in m.items() if k!='fingerprint'})!=m['fingerprint']:raise ValueError('Manifest modified')
    if m['sources']!=sources() or m['runtime']!=runtime():raise ValueError('Frozen source/runtime changed')


def generate(plan):
    rng=np.random.default_rng(plan['seed']);h=plan['family']
    faults,plant,control=Faults(),HIDDEN_PLANT,Controller()
    value=None
    if h in DISTRIBUTIONS:
        value=float(rng.uniform(*DISTRIBUTIONS[h]))
        if h in ('lateral_current','heading_bias'):value*=float(rng.choice([-1,1]))
        param=REGISTRY[h].parameter
        if h in ('lateral_current','port_degradation','starboard_degradation','heading_bias'):
            faults=replace(faults,**{param:value})
        elif h=='common_thrust_scale':faults=replace(faults,port_efficiency=value,starboard_efficiency=value)
        elif h in ('heading_controller_gain','controller_lookahead'):control=replace(control,**{param:value})
        else:plant=replace(plant,**{param:value})
    elif h=='mismatch_control':
        plant=PlantConfig(float(rng.uniform(.05,.25)),float(rng.uniform(.1,.5)),float(rng.uniform(.95,1.05)))
    elif h!='nominal':raise ValueError('Unknown planned family')
    true='nominal' if h=='mismatch_control' else h
    return faults,plant,control,true,value


def all_fits(episodes,cache):
    episodes=sorted(episodes,key=lambda e:digest({'observations':e['observations'],'experiment':asdict(e['experiment'])}))
    key=digest([{'observations':e['observations'],'experiment':asdict(e['experiment'])} for e in episodes])
    if key not in cache:
        cache[key]=[fit_model(episodes,name) for name in REGISTRY]
    return cache[key]


def policy(initial,initial_fits,backend,name,seed,cache):
    def provider(episodes,template,**kwargs):


        if kwargs.get('knobs') or kwargs.get('bounds'):return fit_model(episodes,template,**kwargs)
        return next(f for f in all_fits(episodes,cache) if f.hypothesis==template)
    session=InvestigationSession(initial,backend.execute,initial_fits=initial_fits,
                                 experiment_budget=2,time_budget_s=32.,fit_provider=provider,
                                 allowed_trials=LIBRARY)
    remaining=list(LIBRARY);rng=random.Random(seed);actions=[]
    for step in range(2):
        fits=list(session._fits.values())
        if step and verdict(fits)['kind']=='identified':break
        if name=='fixed':trial=remaining[0]
        elif name=='random':trial=rng.choice(remaining)
        elif name=='greedy':
            adequate=[f for f in fits if f.converged and f.weighted_rmse<=2]
            candidates=adequate if len(adequate)>=2 else [f for f in fits if f.converged]
            scores={r.key:predicted_separation(candidates,r) for r in remaining}
            trial=max(remaining,key=lambda r:scores[r.key])
        else:raise ValueError('Unknown strategy')
        result=session.call({'op':'request_experiment','name':trial.name,'params':trial.params()})
        actions.append({'request':asdict(trial),'envelope':result['envelope'],
                        'predicted_scores':scores if name=='greedy' else None})
        remaining.remove(trial)
        for h in REGISTRY:
            session.call({'op':'propose_hypothesis','template':h,'knobs':{},'bounds':{},
                          'rationale':'Refit the same allowed models to all acquired public evidence.'})
    fitset=list(session._fits.values());out=verdict(fitset)
    selected=next((f for f in fitset if f.hypothesis==out['selected']),None)
    finalized=session.call({'op':'finalize',
        'diagnosis':{'hypothesis':out['selected'],'evidence_refs':session.evidence_refs()},
        'confidence':'supported' if out['kind']=='identified' else 'abstain',
        'ambiguity_statement':'Conditional on tested singleton models and finite trial budget; mismatch, missing mechanisms and parameter uncertainty remain.'})
    return {'numerical_outcome':out,'physical_finding':finding(selected) if selected else None,
            'fit_reports':[public_fit(f) for f in fitset], 'actions':actions,
            'budgets':session.get_fit_report()['budgets'],'ledger':session.ledger,'finalized':finalized}


def one(plan,split='heldout',active=True):
    started=time.perf_counter();faults,plant,control,true,value=generate(plan)
    mission=Mission(duration_s=100.,seed=plan['seed'])
    result=simulate(faults=faults,plant=plant,controller=control,mission=mission)
    matched=simulate(plant=HIDDEN_PLANT if plan['family']!='mismatch_control' else plant,mission=mission)
    actual,normal=metrics(result,mission),metrics(matched,mission)
    operational=('mission_failure' if not actual['mission_success'] else 'performance_degradation'
                 if actual['rms_cross_track_m']-normal['rms_cross_track_m']>=.25 or actual['max_abs_cross_track_m']-normal['max_abs_cross_track_m']>=.5 or actual['elapsed_s']-normal['elapsed_s']>=5 else 'unqualified')
    initial=[r for r in result.observations if r['time_s']<=30.+1e-9]
    original=passive(initial,PassiveProtocol())
    cache={};fits=all_fits([{'observations':initial,'experiment':Experiment()}],cache)
    expanded=verdict(fits)
    chosen=next((f for f in fits if f.hypothesis==expanded['selected']),None)
    restricted=verdict([f for f in fits if f.hypothesis in HYPOTHESES])
    restricted_chosen=next((f for f in fits if f.hypothesis==restricted['selected']),None)
    presentations_out={}
    if plan['index'] in NOTE_INDICES:
        for condition,text in presentations(plan['index'],true,split).items():
            biased=keyword_prior(fits,text);selected=next((f for f in fits if f.hypothesis==biased['decision']['selected']),None)
            presentations_out[condition]={'text':text,'reliability_label_private':condition,
                                           'physical_trace_hash':digest(initial),'result':biased,
                                           'physical_finding':finding(selected) if selected else None}
    policies={}
    if active:
        for name in ('fixed','random','greedy'):
            backend=PrivateBackend(faults=faults,plant=plant,controller=control,seed=plan['seed'],count=2,time_s=32.)
            p=policy(initial,fits,backend,name,1000000+plan['index'],cache)
            p['correct']=p['physical_finding']==true
            p['confidently_wrong']=p['physical_finding'] is not None and not p['correct']
            policies[name]=p
    recovered=any(p['correct'] for p in policies.values())
    if recovered:resolution='resolvable'
    elif any(p['numerical_outcome']['kind'] in ('optimization_failure','model_inadequate') for p in policies.values()):resolution='undetermined'
    elif any(set(p['numerical_outcome']['competitive'])<set(expanded['competitive']) and true in p['numerical_outcome']['competitive'] for p in policies.values()):resolution='partially_resolvable'
    else:resolution='not_resolved_by_evaluated_protocol'
    if not active:resolution='not_assessed'
    param=REGISTRY[true].parameter if true in REGISTRY else None
    truefit=next((f for f in fits if f.hypothesis==true),None)
    for p in policies.values():
        f=next((f for f in p['fit_reports'] if f['hypothesis']==true),None)
        p['true_family_parameter_error_private']=(abs(f['parameters'][param]-value) if f and param else None)
    return {**plan,'true_family_private':true,'injected_value_private':value,
            'generation_status':'generated',
            'faults_private':asdict(faults),'plant_private':asdict(plant),'controller_private':asdict(control),
            'operational':operational,'metrics_private':actual,'matched_nominal_metrics_private':normal,
            'original_passive':summary(original),'expanded':expanded,
            'restricted_v2':restricted,'restricted_v2_finding':finding(restricted_chosen) if restricted_chosen else None,
            'expanded_finding':finding(chosen) if chosen else None,'expanded_fits':[asdict(f) for f in fits],
            'true_family_parameter_error_private':abs(truefit.parameters[param]-value) if truefit and param else None,
            'notes_private':presentations_out,'policies':policies,'resolvability':resolution,
            'unique_public_evidence_fit_sets':len(cache),'elapsed_s':time.perf_counter()-started}


def aggregate(records):
    report={'physical_cases':len(records),'operational':dict(Counter(r['operational'] for r in records)),
            'generation_status':dict(Counter(r.get('generation_status','generated') for r in records)),
            'original_outcomes':dict(Counter(r['original_passive']['kind'] for r in records)),
            'expanded_outcomes':dict(Counter(r['expanded']['kind'] for r in records)),
            'expanded_correct':sum(r['expanded_finding']==r['true_family_private'] for r in records),
            'expanded_wrong':sum(r['expanded_finding'] is not None and r['expanded_finding']!=r['true_family_private'] for r in records),
            'original_correct':sum(r['original_passive']['selected']==r['true_family_private'] for r in records),
            'restricted_v2_correct':sum(r['restricted_v2_finding']==r['true_family_private'] for r in records),
            'restricted_v2_outcomes':dict(Counter(r['restricted_v2']['kind'] for r in records)),
            'expanded_fit_calls':sum(len(r['expanded_fits']) for r in records),
            'expanded_optimization_attempts':sum(f['optimization_attempts'] for r in records for f in r['expanded_fits']),
            'resolvability':dict(Counter(r['resolvability'] for r in records)),'policies':{},'notes':{}}
    for name in ('fixed','random','greedy'):
        trials=[r['policies'][name] for r in records if name in r['policies']]
        report['policies'][name]={'cases':len(trials),'correct':sum(t['correct'] for t in trials),
            'planned_cases':len(records),'not_assessed_due_failure':len(records)-len(trials),
            'confidently_wrong':sum(t['confidently_wrong'] for t in trials),
            'abstained':sum(t['physical_finding'] is None for t in trials),
            'experiments':sum(t['budgets']['experiments'] for t in trials),
            'time_s':sum(t['budgets']['charged_time_s'] for t in trials),
            'logical_fit_calls':sum(t['budgets']['fit_calls'] for t in trials),
            'logical_optimization_attempts':sum(t['budgets']['optimization_attempts'] for t in trials),
            'observed_guard_stops':sum(a['envelope']['observed_guard_triggered'] for t in trials for a in t['actions']),
            'corridor_excursions':sum(a['envelope']['inspection_corridor_excursion'] for t in trials for a in t['actions'])}
        report['policies'][name]['correct_interval_95_wilson']=wilson(sum(t['correct'] for t in trials),len(records))
        report['policies'][name]['outcomes']=dict(Counter(t['numerical_outcome']['kind'] for t in trials))
    for condition in ('correct','misleading','irrelevant','absent'):
        rows=[(r,r['notes_private'][condition]) for r in records if condition in r['notes_private']]
        report['notes'][condition]={'paired_cases':len(rows),
            'correct':sum(v['physical_finding']==r['true_family_private'] for r,v in rows),
            'wrong':sum(v['physical_finding'] is not None and v['physical_finding']!=r['true_family_private'] for r,v in rows),
            'abstained':sum(v['physical_finding'] is None for r,v in rows)}
    return report


def wilson(k,n):
    if not n:return None
    z=1.959963984540054;den=1+z*z/n;p=k/n
    mid=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0.,mid-half),min(1.,mid+half)]


def run(manifest,destination,batch):
    validate(manifest);destination=Path(destination).resolve()
    if ROOT==destination or ROOT in destination.parents:raise ValueError('Private output outside source required')
    destination.mkdir(parents=True,exist_ok=True)
    if (destination/'manifest.json').exists():
        if digest(json.loads((destination/'manifest.json').read_text()))!=digest(manifest):raise ValueError('Checkpoint belongs to another protocol')
    else:write(destination/'manifest.json',manifest)
    done=0
    for plan in manifest['plans']:
        path=destination/(plan['case_id']+'.json')
        if path.exists():
            r=json.loads(path.read_text());body={k:v for k,v in r.items() if k!='result_hash'}
            if digest(body)!=r['result_hash'] or r['manifest_fingerprint']!=manifest['fingerprint']:raise ValueError('Corrupt checkpoint')
            continue
        try:
            record=one(plan,active=plan['active_assessment'])
        except (ValueError,FloatingPointError,OverflowError,np.linalg.LinAlgError) as exc:


            failed={'kind':'optimization_failure','selected':None,'competitive':[],
                    'reasons':['Generation/fitting/policy execution did not complete; cost unknown.']}
            record={**plan,'generation_status':'failed_execution','operational':'undetermined',
                    'true_family_private':'nominal' if plan['family']=='mismatch_control' else plan['family'],
                    'original_passive':failed,'restricted_v2':failed,'restricted_v2_finding':None,
                    'expanded':failed,'expanded_finding':None,'expanded_fits':[],
                    'notes_private':{},'policies':{},'resolvability':'undetermined',
                    'execution_error':f'{type(exc).__name__}: {exc}'}
        record['manifest_fingerprint']=manifest['fingerprint'];record['result_hash']=digest(record)
        write(path,record);done+=1
        print(plan['case_id'],plan['family'],record['operational'],record['expanded'],record['resolvability'],flush=True)
        if done>=batch:break
    records=[json.loads((destination/(p['case_id']+'.json')).read_text()) for p in manifest['plans'] if (destination/(p['case_id']+'.json')).exists()]
    if len(records)==len(manifest['plans']):
        result={'manifest_fingerprint':manifest['fingerprint'],'summary':aggregate(records),
                'strata':{s:aggregate([r for r in records if r['stratum']==s]) for s in ('A','C','D')}}
        if not (destination/'summary.json').exists():write(destination/'summary.json',result)
        print(json.dumps(result,indent=2),flush=True)
    else:print('Checkpointed',len(records),'of',len(manifest['plans']),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('dev','freeze','run'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--development',type=Path)
    p.add_argument('--manifest',type=Path);p.add_argument('--batch',type=int,default=2)
    a=p.parse_args()
    if a.action=='freeze':
        if not a.development:p.error('freeze requires completed development sensitivity report')
        write(a.output,freeze(json.loads(a.development.read_text())))
    elif a.action=='run':
        if not a.manifest or a.batch<1:p.error('run requires manifest and positive batch')
        run(json.loads(a.manifest.read_text()),a.output,a.batch)
    else:


        records=[]
        for i,h in enumerate(('actuator_lag','thrust_deadzone','drag_surge','heading_controller_gain')):
            result=one({'case_id':f'development-{i}','index':i,'seed':606000+i,'family':h,'stratum':'development'},split='development')
            records.append(result);print('Development',h,result['expanded'],result['resolvability'],flush=True)
        write(a.output,{'split':'new_development_only','records':records,'summary':aggregate(records)})
