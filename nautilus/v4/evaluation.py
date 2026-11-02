"""Serial source-frozen development runner with complete attempt retention."""
import argparse,csv,json,math,time
from dataclasses import replace
from pathlib import Path
import numpy as np
from scipy.stats import binomtest,beta
from ..controller_context import fingerprint,canonical
from ..simulator import Faults,PlantConfig,Controller
from ..v2_models import REGISTRY
from .catalog import reserve,generate,COUNTS,runtime
from .checkpoint import sources
from .approval import Policy as SafetyPolicy
from .laboratory import V4Laboratory
from .policies import Policy,STRATEGIES
from .observations import legacy
from .records import export
from evaluate_muse import write_private
from evaluate_active import wilson

FAMILIES={'lateral_current':'environment','longitudinal_current':'environment','port_degradation':'propulsion','starboard_degradation':'propulsion','heading_bias':'sensor','actuator_lag':'actuation','thrust_deadzone':'actuation','drag_yaw':'hydrodynamics','drag_sway':'hydrodynamics','heading_controller_gain':'controller_configuration','controller_lookahead':'controller_configuration','heading_damping_configuration':'controller_configuration','heading_clamp_configuration':'controller_configuration','cruise_configuration':'controller_configuration','nominal':'control'}
PARAMETER_TOLERANCES={'current_y':.1,'port_efficiency':.15,'starboard_efficiency':.15,'heading_bias_rad':.08,'actuator_tau_s':.2,'thrust_deadzone_n':.5,'drag_sway_scale':.3,'heading_kp':5.,'lookahead_m':2.}


def score(case,lab,origin):
    e=lab.ledger[-1];d=e['diagnosis'];voluntary=origin=='policy';abstain=voluntary and e['confidence']=='abstain'
    pred={c['mechanism'] for c in d.get('causes',[])}-{'nominal'};truth=set(case['truth'])-{'nominal'}
    nonabstain=voluntary and e['confidence']!='abstain';exact=bool(nonabstain and pred==truth)
    values={k:v for c in d.get('causes',[]) for k,v in c['parameters'].items()}
    tolerance=all(k in values and abs(values[k]-v)<=PARAMETER_TOLERANCES[k] for k,v in case['parameter_values'].items() if k in PARAMETER_TOLERANCES) if case['parameter_values'] and exact else None
    relevant=case['classification']=='operationally_distinguishable';intersection=pred&truth
    return {'valid_completion':voluntary,'host_termination':origin=='host','exact':exact,'primary_eligible':relevant,'partial':bool(nonabstain and intersection and pred!=truth),'extra_attribution':bool(nonabstain and pred-truth),'incomplete_attribution':bool(nonabstain and intersection and truth-pred),'incorrect_set':bool(nonabstain and pred!=truth),'family_exact':bool(nonabstain and {FAMILIES.get(n,n) for n in pred}=={FAMILIES.get(n,n) for n in truth}),'precision':len(intersection)/len(pred) if nonabstain and pred else None,'recall':len(intersection)/len(truth) if nonabstain and truth else None,'abstain':abstain,'correct_abstention_under_finite_criterion':bool(abstain and case['classification'] in ('operationally_indistinguishable','model_inadequate_or_out_of_registry')),'unnecessary_abstention_under_finite_criterion':bool(abstain and relevant),'parameter_tolerance':tolerance}


def run_policy(case,plan,strategy):
    settings={k:t(**case['settings'][k]) for k,t in (('faults',Faults),('plant',PlantConfig),('controller',Controller))};settings['seed']=plan['seed']
    l=V4Laboratory(legacy(case['observations']),policy=SafetyPolicy(),joint_enabled=True,settings=settings,fit_budget=8,optimization_budget=16,experiment_budget=1,time_budget_s=16.,starts=1,note=case['narrative']['text'])
    initial=fingerprint(l.ledger);policy=Policy(strategy,seed=plan['seed']);actions=[];start=time.monotonic();origin='host'
    for _ in range(12):
        payload=policy.choose(l);accepted=False
        try:l.call(payload);accepted=True
        except ValueError:pass
        actions.append({'name':payload['op'],'accepted':accepted})
        if l._closed:origin='policy';break
    if not l._closed:l.call({'op':'finalize','diagnosis':{'hypothesis':None,'evidence_refs':l.evidence_refs()},'confidence':'abstain','ambiguity_statement':'HOST-ENFORCED ABSTENTION: offline action budget exhausted.'})
    metrics={'origin':origin,'elapsed_s':time.monotonic()-start,'fits':l.fit_calls,'parameter_starts':l.optimization_attempts,'experiments':l.tests,'simulation_s':l.test_time_s,'excursions':sum(e['type']=='observation' and e.get('execution',{}).get('observed_excursion',False) for e in l.ledger),'fit_failures':sum(e['type']=='fit_failure' for e in l.ledger),'evidence_ref_valid':all(x in l.evidence_refs() for x in l.ledger[-1]['diagnosis']['evidence_refs'])}
    return l,{'scores':score(case,l,origin),'metrics':metrics,'actions':actions,'initial_hash':initial}


def paired(left,right):
    n=len(left)
    if len(right)!=n or n==0:return {'n':n,'p_exact':None}
    wins=sum(a and not b for a,b in zip(left,right));losses=sum(b and not a for a,b in zip(left,right));d=wins+losses
    # Conservative 95% interval: simultaneous 97.5% Clopper-Pearson intervals
    # on the two discordance probabilities via Bonferroni; difference bounds.
    def cp(k):return (0. if k==0 else float(beta.ppf(.0125,k,n-k+1)),1. if k==n else float(beta.ppf(.9875,k+1,n-k)))
    lo_w,hi_w=cp(wins);lo_l,hi_l=cp(losses)
    return {'n':n,'left_only':wins,'right_only':losses,'ties':n-d,'effect_difference':(wins-losses)/n,'effect_95_conservative_interval':[max(-1.,lo_w-hi_l),min(1.,hi_w-lo_l)],'p_exact':float(binomtest(wins,d,.5).pvalue) if d else 1.,'qualification':'Paired exact binomial/McNemar discordance test; conservative Bonferroni marginal-exact effect interval, not overlapping-Wilson logic.'}


def aggregate(rows,strategies,attempts):
    out={}
    for policy in strategies:
        good=[r for r in rows if policy in r['policies']];scores=[r['policies'][policy]['scores'] for r in good];eligible=[s for s in scores if s['primary_eligible']];metrics=[r['policies'][policy]['metrics'] for r in good]
        keys=('valid_completion','host_termination','exact','partial','extra_attribution','incomplete_attribution','incorrect_set','family_exact','abstain','correct_abstention_under_finite_criterion','unnecessary_abstention_under_finite_criterion')
        out[policy]={'attempted':attempts,'terminal_scored':len(good),'infrastructure_or_unscored':attempts-len(good),**{k:sum(s[k] for s in scores) for k in keys},'primary_eligible':len(eligible),'primary_exact':sum(s['exact'] for s in eligible),'primary_wilson95':wilson(sum(s['exact'] for s in eligible),len(eligible)),
          'unconditional_exact_wilson95':wilson(sum(s['exact'] for s in scores),attempts),'mean_cause_precision':float(np.mean([s['precision'] for s in scores if s['precision'] is not None])) if any(s['precision'] is not None for s in scores) else None,'mean_cause_recall':float(np.mean([s['recall'] for s in scores if s['recall'] is not None])) if any(s['recall'] is not None for s in scores) else None,'parameter_tolerance_assessed':sum(s['parameter_tolerance'] is not None for s in scores),'parameter_tolerance_passed':sum(s['parameter_tolerance'] is True for s in scores),
          **{k:sum(m[k] for m in metrics) for k in ('fits','parameter_starts','experiments','simulation_s','excursions','fit_failures','elapsed_s')},'by_stratum':{g:{'cases':sum(r['stratum']==g for r in good),'exact':sum(r['policies'][policy]['scores']['exact'] for r in good if r['stratum']==g)} for g in COUNTS if g not in ('G','K')},'by_difficulty':{d:{'cases':sum(r['difficulty']==d for r in good),'exact':sum(r['policies'][policy]['scores']['exact'] for r in good if r['difficulty']==d)} for d in ('moderate','hard')}}
    if len(strategies)==2:
        both=[r for r in rows if all(p in r['policies'] for p in strategies)]
        out['paired_all']=paired([r['policies'][strategies[0]]['scores']['exact'] for r in both],[r['policies'][strategies[1]]['scores']['exact'] for r in both])
        primary=[r for r in both if r['policies'][strategies[0]]['scores']['primary_eligible']]
        out['paired_primary']=paired([r['policies'][strategies[0]]['scores']['exact'] for r in primary],[r['policies'][strategies[1]]['scores']['exact'] for r in primary])
    return out


def run(directory,strategies=('passive','sequential_residual'),*,limit=60):
    p=Path(directory).resolve();m=json.loads((p/'catalog-manifest.json').read_text())
    if fingerprint({k:v for k,v in m.items() if k!='fingerprint'})!=m['fingerprint'] or m['source_fingerprint']!=fingerprint(sources()) or m['runtime']!=runtime():raise ValueError('Catalog source or manifest changed; no silent resume')
    if not 1<=limit<=len(m['plans']) or len(set(strategies))!=len(strategies) or any(s not in STRATEGIES for s in strategies):raise ValueError('Invalid bounded evaluation plan')
    config={'strategies':list(strategies),'fit_budget':8,'parameter_start_budget':16,'starts':1,'actions':12,'policy':'simulation_enforced','notes':'present; policies explicitly text-blind','limit':limit,'source_fingerprint':m['source_fingerprint'],'manifest_fingerprint':m['fingerprint']}
    planfile=p/'run-plan.json'
    if planfile.exists():
        if json.loads(planfile.read_text())!=config:raise ValueError('Offline run configuration changed')
    else:write_private(planfile,config)
    rows=[]
    for plan in m['plans'][:limit]:
        completed=p/(plan['case_id']+'.completed.json');started=p/(plan['case_id']+'.started.json')
        if completed.exists():
            r=json.loads(completed.read_text());h=r.pop('result_hash')
            if fingerprint(r)!=h or r['case_id']!=plan['case_id']:raise ValueError('Corrupt completed case')
            r['result_hash']=h;rows.append(r);continue
        if started.exists():raise ValueError('Uncertain/failed prior case; never automatically repeat')
        write_private(started,{'case_id':plan['case_id'],'source_fingerprint':m['source_fingerprint']})
        try:
            case=generate(plan);write_private(p/(plan['case_id']+'.case.json'),case);policies={};initial=[]
            for policy in strategies:
                lab,result=run_policy(case,plan,policy);initial.append(result['initial_hash']);policies[policy]=result
                out=p/plan['case_id']/policy;export(lab,out/'public-investigation.json',out/'v4-provenance.json');write_private(out/'result.json',result)
            if len(set(initial))!=1:raise ValueError('Unequal paired initial evidence')
            r={'case_id':plan['case_id'],'stratum':case['stratum'],'difficulty':case['difficulty'],'classification':case['classification'],'gate':case['gate'],'policies':policies}
            r['result_hash']=fingerprint(r);write_private(completed,r);rows.append(r)
            print(canonical({'offline_completed_pairs':len(rows),'planned':limit}),flush=True)
        except BaseException as error:
            # No raw exception/payload output; retain all partial private files and halt.
            write_private(p/(plan['case_id']+'.infrastructure-error.json'),{'case_id':plan['case_id'],'category':type(error).__name__,'automatic_retry':False});raise
    summary={'schema_version':'nautilus.evaluation-summary.v4','development_only':True,'planned':limit,'attempted':len(list(p.glob('*.started.json'))),'completed':len(rows),'policies':list(strategies),'metrics':aggregate(rows,strategies,len(list(p.glob('*.started.json')))),'generation_gates':{'accepted':sum(r['gate']['accepted'] for r in rows),'rejected_retained':sum(not r['gate']['accepted'] for r in rows),'by_stratum':{g:{'total':sum(r['stratum']==g for r in rows),'accepted':sum(r['stratum']==g and r['gate']['accepted'] for r in rows)} for g in COUNTS if g not in ('G','K')}},'api_requests':0,'source_fingerprint':m['source_fingerprint'],'manifest_fingerprint':m['fingerprint']}
    if (p/'sanitized-summary.json').exists():
        if json.loads((p/'sanitized-summary.json').read_text())!=summary:raise ValueError('Aggregate summary changed')
        return summary
    write_private(p/'sanitized-summary.json',summary)
    with (p/'aggregate.csv').open('x',newline='') as out:
        writer=csv.writer(out);writer.writerow(['policy','attempted','exact','primary_eligible','primary_exact','abstain','experiments','excursions'])
        for name in strategies:writer.writerow([name]+[summary['metrics'][name][k] for k in ('attempted','exact','primary_eligible','primary_exact','abstain','experiments','excursions')])
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('reserve','run'));parser.add_argument('--directory',required=True);parser.add_argument('--limit',type=int,default=60);args=parser.parse_args()
    result=reserve(args.directory) if args.action=='reserve' else run(args.directory,limit=args.limit)
    print(canonical({'reserved':result['generated_count'],'manifest_fingerprint':result['fingerprint']} if args.action=='reserve' else result))
