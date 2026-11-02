"""Deterministic V4 development catalog; unsupported stretch families explicit."""
from copy import deepcopy
from dataclasses import asdict,replace
import json,secrets,platform,os,scipy
from pathlib import Path
import numpy as np
from ..controller_context import canonical,fingerprint
from ..simulator import Faults,PlantConfig,Controller,Mission,simulate
from ..v2_models import REGISTRY,configs
from .models import PAIRS,compose
from .narratives import CONDITIONS,note
from .observations import wrap

COUNTS={'A':(10,8),'B':(10,8),'C':(15,10),'D':(15,10),'E':(12,8),'F':(8,6),'G':(6,0),'H':(10,6),'J':(8,4),'K':(6,0)}
SCORING={'primary':'Exact complete cause set on preclassified operationally distinguishable cases; all attempted unconditional separately. Parameter tolerance separate.',
 'resolvability':'Representable truth versus nominal and each one-component-removed noiseless trajectory; initial public window normalized five-channel RMS minimum>1; finite drop-component criterion, not global identifiability.',
 'gate':'Nominal controls valid; non-control physical disturbance must change 20s matched nominal public-y RMS by >.05m OR private x progress by >.2m; shortened-window cases pass declared limited-observation gate. Failed samples retained, never resampled.',
 'confidence':'No probabilities. Correct/unnecessary abstention uses this finite preclassification only, never investigator outcome.',
 'statistics':'Case units, Wilson marginal intervals, paired exact binomial discordance test and conservative Bonferroni paired-effect interval; no optional stopping.'}


def runtime():
    return {'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'threads':{k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')}}


def reserve(directory,*,full=False):
    p=Path(directory).resolve();root=Path(__file__).resolve().parents[2]
    if p==root or root in p.parents:raise ValueError('Private catalog directory required')
    p.mkdir(parents=True,exist_ok=True,mode=0o700);base=2**56+secrets.randbelow(2**40)*128
    plans=[];excluded=[]
    for group,counts in COUNTS.items():
        number=counts[0 if full else 1]
        if group in ('G','K'):
            excluded.append({'stratum':group,'requested':number,'reason':'Triple/time-structured research disabled; no faithful V4 validated inference contract.'});continue
        for j in range(number):
            i=len(plans);plans.append({'case_id':f'V4D{i+1:03d}','stratum':group,'variant':j,'seed':base+i,'difficulty':'hard' if group in ('E','F','H') else 'moderate','narrative_condition':CONDITIONS[i%4]})
    from .checkpoint import sources
    m={'schema_version':'nautilus.catalog.v4','purpose':'development-only; not untouched evaluation','plans':plans,'requested_count':100 if full else 60,'generated_count':len(plans),'excluded':excluded,'source_fingerprint':fingerprint(sources()),'runtime':runtime(),'rules':SCORING,'generation':{'seed_region':'Fresh block above2^56; disjoint from V1–V3','policy':'No resampling. Gate outcomes retained. Families with <75% gate success require redesign/new version before final freeze.'}}
    m['fingerprint']=fingerprint(m)
    from evaluate_muse import write_private
    write_private(p/'catalog-manifest.json',m);(p/'catalog-manifest.json').chmod(0o400);return m


def generate(plan):
    rng=np.random.default_rng(plan['seed']);g=plan['stratum'];j=plan['variant'];f,p,c=Faults(),PlantConfig(),Controller();truth=[];values={};representable=True
    singles=('lateral_current','port_degradation','starboard_degradation','heading_bias','actuator_lag','thrust_deadzone','drag_sway','heading_controller_gain')
    def set_single(name,value):
        nonlocal f,p,c
        f,p,c=configs(name,value);truth.append(name);values[REGISTRY[name].parameter]=value
    if g=='A':
        name=singles[j%len(singles)];spec=REGISTRY[name]
        value={'lateral_current':(-1 if j%2 else 1)*float(rng.uniform(.25,.6)),'port_degradation':float(rng.uniform(.35,.65)),'starboard_degradation':float(rng.uniform(.35,.65)),'heading_bias':(-1 if j%2 else 1)*float(rng.uniform(.2,.45)),'actuator_lag':.7,'thrust_deadzone':2.,'drag_sway':2.,'heading_controller_gain':12.}[name];set_single(name,value)
    elif g=='B':
        if j%2==0:truth=['nominal']
        else:f=Faults();p=PlantConfig(actuator_tau_s=.5,drag_yaw_scale=1.8);truth=['actuator_lag','drag_yaw'];representable=False
    elif g=='C':
        representable=False
        if j%4==0:f=replace(f,current_x=(-1 if j%2 else 1)*.45);truth=['longitudinal_current']
        elif j%4==1:c=replace(c,heading_kd=3.);truth=['heading_damping_configuration']
        elif j%4==2:c=replace(c,max_heading_rad=.12);truth=['heading_clamp_configuration']
        else:c=replace(c,cruise_thrust=4.);truth=['cruise_configuration']
    elif g in ('D','F'):
        name='joint__lateral_current__heading_bias' if g=='F' else list(PAIRS)[j%len(PAIRS)];components=PAIRS[name]['components'];vv=[]
        for n in components:
            v={'lateral_current':float(rng.uniform(.25,.55)),'port_degradation':.5,'starboard_degradation':.5,'heading_bias':.25 if g=='F' else .3,'actuator_lag':.7}[n];vv.append(v);values[REGISTRY[n].parameter]=v
        f,p,c=compose({'schema_version':'nautilus.physical-composition.v4','components':[{'mechanism':n,'value':v} for n,v in zip(components,vv)]});truth=list(components)
    elif g=='E':f=replace(f,current_y=float(rng.uniform(.2,.5)),current_x=.4);truth=['lateral_current','longitudinal_current'];representable=False
    elif g=='H':set_single('heading_bias',.3 if j%2 else -.3)
    elif g=='J':
        name='heading_controller_gain' if j%2==0 else 'controller_lookahead';set_single(name,8. if j%2==0 else 18.)
    else:raise ValueError('Unsupported catalog stratum')
    duration=(.4,.8,1.)[j%3] if g=='H' else 2.
    mission=Mission(duration_s=duration,seed=plan['seed']);rows=simulate(faults=f,plant=p,controller=c,mission=mission).observations
    # Curated broad-topic linkage can supply testimony: explicitly not leak-free causal proof.
    topic=0 if any('degradation' in n for n in truth) else 1 if 'heading_bias' in truth else 2
    narrative=note(plan['narrative_condition'],j,topic=topic if plan['narrative_condition']=='informative' else (topic+1)%3 if plan['narrative_condition']=='misleading' else None)
    audit_mission=replace(mission,duration_s=20.);actual=simulate(faults=f,plant=p,controller=c,mission=audit_mission);baseline=simulate(mission=audit_mission)
    def rms(result):return float(np.sqrt(np.mean([r['observed_y_m']**2 for r in result.observations])))
    tracking=abs(rms(actual)-rms(baseline));progress=abs(actual.truth[-1]['x_m']-baseline.truth[-1]['x_m'])
    masking=None
    if g=='F':
        solo=[]
        for n in truth:
            ff,pp,cc=configs(n,values[REGISTRY[n].parameter]);solo.append(rms(simulate(faults=ff,plant=pp,controller=cc,mission=audit_mission)))
        masking=rms(actual)<.8*max(solo)
    gate=(truth==['nominal'] or g=='H' or tracking>.05 or progress>.2) and (masking is not False)
    label='model_inadequate_or_out_of_registry' if not representable else 'control_or_nominal' if truth==['nominal'] else classification(f,p,c,truth,duration)
    return {'schema_version':'nautilus.case.v4','case_id':plan['case_id'],'stratum':g,'difficulty':plan['difficulty'],'seed':plan['seed'],'settings':{'faults':asdict(f),'plant':asdict(p),'controller':asdict(c)},'truth':truth,'parameter_values':values,'representable':representable,'classification':label,'observations':wrap(rows),'narrative':narrative,'gate':{'accepted':bool(gate),'masking_gate':masking,'reason':'declared_physical_gate_passed' if gate else 'insufficient_degradation_or_masking; retain sample, family needs review','tracking_delta_rms_m':tracking,'progress_delta_m':progress,'criterion':SCORING['gate']}}


def classification(f,p,c,truth,duration):
    from ..active_planner import separation
    # Evaluation-only known-parameter counterfactual perturbations, no fitted model success used.
    base={'faults':f,'plant':p,'controller':c};mission=Mission(duration_s=duration,seed=0,sensor_y_std_m=0.,sensor_heading_std_rad=0.,sensor_yaw_rate_std_radps=0.)
    actual=simulate(**base,mission=mission).observations;distances=[]
    for removed in truth:
        keep=[n for n in truth if n!=removed]
        if not keep:other=simulate(mission=mission).observations
        else:
            n=keep[0];spec=REGISTRY[n];default=configs(n,spec.nominal);fields={**asdict(f),**asdict(p),**asdict(c)};v=fields[spec.parameter];ff,pp,cc=configs(n,v);other=simulate(faults=ff,plant=pp,controller=cc,mission=mission).observations
        distances.append(separation({'actual':actual,'component_removed':other})['minimum'])
    return 'operationally_distinguishable' if distances and min(distances)>1. else 'operationally_indistinguishable'
