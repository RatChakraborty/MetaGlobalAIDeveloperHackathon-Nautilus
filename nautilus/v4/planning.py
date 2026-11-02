"""Pair-aware extension of the fixed V3 menu; same hard screen and qualifications."""
from types import SimpleNamespace
from ..active_planner import candidates,separation,_trusted_audit,SCALES
from ..v2_experiments import forward
from ..v2_models import REGISTRY
from ..simulator import simulate,Mission
from .models import PAIRS,compose


def forecast(fit,trial):
    if fit['hypothesis'] not in PAIRS:return forward(SimpleNamespace(**fit),trial)
    pair=PAIRS[fit['hypothesis']];f,p,c=compose({'schema_version':'nautilus.physical-composition.v4','components':[{'mechanism':n,'value':fit['parameters'][REGISTRY[n].parameter]} for n in pair['components']]})
    return simulate(faults=f,plant=p,controller=c,mission=Mission(duration_s=trial.duration_s,dt_s=.05,sensor_y_std_m=0.,sensor_heading_std_rad=0.,sensor_yaw_rate_std_radps=0.,seed=0),experiment=trial.experiment()).observations


def ranking(lab):
    r=lab.get_fit_report();fits=[f for f in r['fits'] if f['converged'] and f['evidence_refs']==lab.evidence_refs() and not f.get('bound_hits') and max(f['physical_wrms'],f['command_wrms'])<=2.]
    fits=sorted(fits,key=lambda f:f['penalized_score'])[:4];rows=[];audit=_trusted_audit()
    for trial,safety in zip(candidates(),audit['rows']):
        predictions={f['hypothesis']:forecast(f,trial) for f in fits} if len(fits)>1 else {}
        try:d=separation(predictions)
        except ValueError:d=separation({})
        rows.append({'candidate_id':trial.key,'name':trial.name,'params':trial.params(),'accepted':safety['accepted'],'predictive_margin_m':safety['predictive_margin_m'],'within_budget':r['remaining']['experiments']>0 and trial.duration_s+lab.policy.tail<=r['remaining']['time_s'],'minimum_separation':d['minimum'],'mean_separation':d['mean']})
    return {'schema_version':'nautilus.plan.v4','evidence_refs':lab.evidence_refs(),'rows':rows,'qualification':'Noiseless fit-conditioned separation, not validated information gain. Strict rejection is hard. Operator approval is a separate human action, never a numerical recommendation or model override.'}
