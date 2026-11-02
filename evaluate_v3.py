"""Fresh development-only V3 design and offline paired deterministic checks.

No API calls. Private manifests/results outside Git; never reuse Phase D holdouts.
"""
import argparse,json,secrets,hashlib,time
from pathlib import Path
from dataclasses import asdict
from copy import deepcopy
import numpy as np
from nautilus.simulator import Faults,PlantConfig,Controller,Mission,simulate
from nautilus.controller_context import canonical,fingerprint,initialize_controller_context,build_controller_context
from nautilus.muse_v3 import Flags,make_lab
from nautilus.active_planner import candidates,safety_audit
from nautilus.v2_models import REGISTRY,finding
from types import SimpleNamespace
from evaluate_muse import baseline_run,closed_metrics,score,write_private,ROOT

# Fixed design, before generation/outcomes. Magnitudes drawn once from these intervals.
DESIGN=(('nominal','nominal','subtle_positive','subtle_negative'),
 ('current_positive','current_negative','current_small_positive','current_small_negative'),
 ('port','starboard','port_subtle','starboard_subtle'),
 ('bias_positive','bias_negative','controller_gain','controller_lookahead'),
 ('current_port','current_starboard','current_bias_positive','current_bias_negative'),
 ('joint_plant','thrust_drag','lag_deadzone','near_confounded'))
GROUPS=('nominal_subtle','current','thruster','sensor_controller','compound','mismatch_ambiguity')
FACTORS={'A':Flags.legacy(),'B':Flags(True,True,False,True),
         'C':Flags(False,False,True,False),'D':Flags()}


def reserve(directory):
    p=Path(directory).resolve()
    if p==ROOT or ROOT in p.parents:raise ValueError('Private directory required')
    p.mkdir(parents=True,mode=0o700,exist_ok=True)
    seed=2**54+secrets.randbelow(2**40)*64
    plans=[{'case_id':f'V3D{i+1:02d}','seed':seed+i,'kind':kind,'stratum':group}
      for i,(group,kind) in enumerate((g,k) for g,kinds in zip(GROUPS,DESIGN) for k in kinds)]
    m={'schema_version':'nautilus.v3-development.v1','purpose':'development-only, not final holdout','plans':plans,
      'source_base':'3344254f2e23a379c45f8e1e97e80674ba11fe96','design':DESIGN,'feature_factors':{k:asdict(v) for k,v in FACTORS.items()},
      'pilot_ids':[plans[i]['case_id'] for i in (0,4,8,12,16,20)],'pilot_rule':'At most first predeclared case of each stratum, never selected by outcome.',
      'limits':{'fits':8,'starts':16,'experiments':1,'experiment_time_s':16,'actions':12},
      'scoring':'Complete mechanism-set equality; partial constituent and broad family separate. No identifiability oracle or correct-abstention score.',
      'rules':'All 24 retained; no qualification/resampling or Muse-selected cases. Fresh high disjoint seeds. Legacy advisory and enforced passive/feasible fixed policy checked offline. Critic effect evaluated only with role provenance, never inferred from safety change.'}
    m['fingerprint']=fingerprint(m);write_private(p/'development-manifest.json',m);(p/'development-manifest.json').chmod(0o400)
    return m


def generate(plan):
    rng=np.random.default_rng(plan['seed']);kind=plan['kind'];f=asdict(Faults());plant=asdict(PlantConfig());c=asdict(Controller());truth=[]
    def current(sign=1,small=False):f['current_y']=sign*float(rng.uniform(.03,.10) if small else rng.uniform(.25,.60));truth.append('lateral_current')
    def port(side='port',subtle=False):f[side+'_efficiency']=float(rng.uniform(.78,.9) if subtle else rng.uniform(.3,.65));truth.append(side+'_degradation')
    def bias(sign=1):f['heading_bias_rad']=sign*float(rng.uniform(.18,.45));truth.append('heading_bias')
    if kind=='nominal':truth=['nominal']
    elif kind.startswith('subtle_'):current(-1 if kind.endswith('negative') else 1,True)
    elif kind in ('current_positive','current_negative','current_small_positive','current_small_negative'):current(-1 if kind.endswith('negative') else 1,'small' in kind)
    elif kind in ('port','starboard','port_subtle','starboard_subtle'):port('port' if kind.startswith('port') else 'starboard','subtle' in kind)
    elif kind.startswith('bias_'):bias(-1 if kind.endswith('negative') else 1)
    elif kind=='controller_gain':c['heading_kp']=float(rng.uniform(8,20));truth=['heading_controller_gain']
    elif kind=='controller_lookahead':c['lookahead_m']=float(rng.uniform(12,18));truth=['controller_lookahead']
    elif kind in ('current_port','current_starboard'):current();port('port' if kind.endswith('port') else 'starboard')
    elif kind.startswith('current_bias_'):current(-1 if kind.endswith('negative') else 1);bias(-1 if kind.endswith('negative') else 1)
    elif kind in ('joint_plant','lag_deadzone'):
        plant['actuator_tau_s']=float(rng.uniform(.4,.9));plant['thrust_deadzone_n']=float(rng.uniform(1,3));truth=['actuator_lag','thrust_deadzone']
    elif kind=='thrust_drag':f['port_efficiency']=f['starboard_efficiency']=.65;plant['uniform_drag_scale']=1.6;truth=['common_thrust_scale','uniform_drag_scale']
    elif kind=='near_confounded':current(1,True);bias(-1)
    else:raise ValueError('Unknown V3 stratum')
    from evaluate_muse import FAMILIES
    return {'faults':f,'plant':plant,'controller':c,'mechanisms':truth,'families':sorted({FAMILIES[x] for x in truth}),'representable':len(truth)==1,'kind':kind,'stratum':plan['stratum']}


def create(case,plan,flags):
    rows=simulate(faults=Faults(**case['faults']),plant=PlantConfig(**case['plant']),controller=Controller(**case['controller']),mission=Mission(duration_s=2.,seed=plan['seed'])).observations
    lab=make_lab(rows,flags=flags,backend_settings={'faults':Faults(**case['faults']),'plant':PlantConfig(**case['plant']),'controller':Controller(**case['controller']),'seed':plan['seed']},fit_budget=8,optimization_budget=16,experiment_budget=1,time_budget_s=16.,starts=2)
    initialize_controller_context(lab,build_controller_context());return lab


def passive_or_safe_fixed(lab,audit):
    start=time.monotonic();actions=[]
    feasible=[r for r in audit['rows'] if r['accepted']]
    if feasible:
        t=feasible[0];lab.call({'op':'request_experiment','name':t['name'],'params':t['params']});actions.append({'payload':{'op':'request_experiment'},'accepted':True})
    for name in list(REGISTRY)[:8]:
        lab.call({'op':'propose_hypothesis','template':name,'knobs':{},'bounds':{},'rationale':'Frozen V3 offline fixed registry order.'});actions.append({'payload':{'op':'propose_hypothesis'},'accepted':True})
    from nautilus.investigator import DeterministicInvestigator
    policy=DeterministicInvestigator('passive')
    payload=policy.choose(lab.get_fit_report())
    if payload['op']!='finalize':raise ValueError('Expected exhausted-fit finalization')
    lab.call(payload)
    actions.append({'payload':{'op':'finalize'},'accepted':True})
    from nautilus.muse_investigator import public_source
    return {'origin':'policy','actions':actions,'elapsed_s':time.monotonic()-start,'public_record':public_source(lab)}


def offline(directory):
    p=Path(directory).resolve();m=json.loads((p/'development-manifest.json').read_text())
    if fingerprint({k:v for k,v in m.items() if k!='fingerprint'})!=m['fingerprint']:raise ValueError('Changed design')
    if (p/'offline.started.json').exists():raise ValueError('No automatic rerun of offline development batch')
    write_private(p/'offline.started.json',{'manifest_fingerprint':m['fingerprint']})
    audit=safety_audit();write_private(p/'safety-audit.json',audit);results=[]
    for plan in m['plans']:
        case=generate(plan);a=create(case,plan,FACTORS['A']);b=create(case,plan,FACTORS['B']);assert fingerprint(a.ledger)==fingerprint(b.ledger)
        legacy=baseline_run(a,'fixed_matched');safe=passive_or_safe_fixed(b,audit)
        metrics={'legacy_fixed':closed_metrics(a,legacy,'fixed_matched'),'safety_fixed':closed_metrics(b,safe,'fixed_matched')}
        scores={k:score(case,v) for k,v in metrics.items()}
        result={'case_id':plan['case_id'],'case':case,'metrics':metrics,'scores':scores,'legacy':legacy,'safety':safe}
        write_private(p/(plan['case_id']+'.offline.json'),result);results.append(result)
        print(canonical({'completed_offline_pairs':len(results)}),flush=True)
    summary={'cases':24,'development_only':True,'manifest_fingerprint':m['fingerprint'],'feasibility':{k:audit[k] for k in ('generated','accepted','rejected','ensemble_size')},
      'policies':{k:{'exact':sum(r['scores'][k]['exact'] for r in results),'representable_cases':sum(r['case']['representable'] for r in results),
        'partial_constituents':sum(r['scores'][k]['partial_constituent'] for r in results),'abstentions':sum(r['scores'][k]['scientific_abstention'] for r in results),
        'experiments':sum(r['metrics'][k]['experiments'] for r in results),'excursions':sum(r['metrics'][k]['observed_excursions'] for r in results),
        'fits':sum(r['metrics'][k]['fit_calls'] for r in results),'starts':sum(r['metrics'][k]['optimization_starts'] for r in results)} for k in ('legacy_fixed','safety_fixed')},
      'limitation':'Safety fixed is a passive-or-safe first-grid policy, not Muse. No critic or planner efficacy can be inferred from these offline numerical baselines.'}
    write_private(p/'offline-summary.json',summary);return summary


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('action',choices=('reserve','offline'));ap.add_argument('--directory',required=True);args=ap.parse_args()
    result=reserve(args.directory) if args.action=='reserve' else offline(args.directory)
    print(canonical({'manifest_fingerprint':result['fingerprint']} if args.action=='reserve' else result))
