"""Bounded public-fit forecasts, not observations or calibrated information gain."""
from functools import lru_cache
from copy import deepcopy
from itertools import combinations
from types import SimpleNamespace
import math
import numpy as np
from .controller_context import fingerprint
from .v2_experiments import parse_trial, forward
from .v2_models import REGISTRY, validate_proposal
from .lab_safety import screen, uncertainty_cases

# Predeclared finite grid: six existing families x two durations x three levels.
GRID = {'durations_s':(4.,6.), 'levels_n':(0.,2.,4.), 'phase_fraction':.5,
        'heading_rad':.1, 'differential_fraction':.25}
SCALES = {'observed_y_m':.035, 'observed_heading_rad':.004,
          'observed_yaw_rate_radps':.003, 'port_command_n':.05, 'starboard_command_n':.05}
QUALIFICATION = ('Counterfactual noiseless reset predictions under singleton fitted models; not new evidence, '
                 'information gain, a cause probability, or a safety proof. No surge-speed/x channel. '
                 'Current/thrust/bias confounding, model mismatch, saturated bounds, residual correlation and '
                 'incomplete hypothesis coverage remain. Exclude stale/nonconverged/bound-saturated fits or WRMS>2, then retain at most four score-gap<=6 competitors. Safety uses the unchanged full stress ensemble.')


def candidates():
    rows=[]
    for duration in GRID['durations_s']:
        for level in GRID['levels_n']:
            phase=duration*GRID['phase_fraction']
            settings={
              'thrust_step':dict(amplitude_n=level,phase_s=phase),
              'coast_down':dict(amplitude_n=level,differential_n=level*.25,phase_s=phase),
              'differential_step':dict(differential_n=level*.25,cruise_thrust_n=level,phase_s=phase),
              'amplitude_ramp':dict(amplitude_n=level,phase_s=phase),
              'heading_response':dict(cruise_thrust_n=level,phase_s=phase,heading_step_rad=.1),
              'cable_follow':dict(cruise_thrust_n=max(.25,level))}
            for name,params in settings.items():rows.append(parse_trial(name,dict(duration_s=duration,**params)))
    assert len(rows)==36 and len({t.key for t in rows})==36
    return tuple(rows)


def safety_audit():
    rows=[]
    for t in candidates():
        s=screen(t);margin=s['limit_m']-s['ensemble_max_y_m']-s['noise_allowance_m']
        rows.append({'candidate_id':t.key,'name':t.name,'params':t.params(),'duration_s':t.duration_s,
          'actuation_n':max(abs(v) for k,v in t.params().items() if k.endswith('_n'))+abs(t.params().get('differential_n',0.)),
          'accepted':s['accepted'],'predictive_margin_m':margin,
          'reason':'within_sampled_envelope' if s['accepted'] else 'predictive_envelope', 'screen':s})
    return {'schema_version':'nautilus.safety-feasibility.v3','grid':GRID,'generated':len(rows),
      'accepted':sum(r['accepted'] for r in rows),'rejected':sum(not r['accepted'] for r in rows),
      'ensemble_size':len(uncertainty_cases()),'rows':rows,'qualification':QUALIFICATION}


def current_fits(report):
    refs=report['evidence_refs'];fits=[]
    for fit in report['fits']:
        if fit.get('evidence_refs')!=refs or not fit.get('converged') or fit.get('method')!='singleton':continue
        if fit.get('bound_hits') or max(fit.get('physical_wrms',float('inf')),fit.get('command_wrms',float('inf')))>2.:continue
        name=fit['hypothesis'];spec,_=validate_proposal(name,fit['parameters'])
        if set(fit['parameters'])!=({spec.parameter} if spec.parameter else set()):continue
        if not math.isfinite(fit['penalized_score']):continue
        fits.append(fit)
    if fits:
        best=min(f['penalized_score'] for f in fits)
        fits=[f for f in fits if f['penalized_score']<=best+6]
    return sorted(fits,key=lambda f:(f['penalized_score'],f['hypothesis']))[:4]


def trajectories(fits,trial):
    """Pure forward models: accepts fit records only, never a laboratory/backend."""
    return {f['hypothesis']:forward(SimpleNamespace(**f),trial) for f in fits}


def separation(rows):
    pairs=[]
    for left,right in combinations(sorted(rows),2):
        a,b=rows[left],rows[right]
        if len(a)!=len(b) or any(abs(x['time_s']-y['time_s'])>1e-9 for x,y in zip(a,b)):
            raise ValueError('Unaligned forecast times')
        delta=np.array([[(x[k]-y[k])/scale for k,scale in SCALES.items()] for x,y in zip(a,b)])
        delta[:,1]=np.arctan2(np.sin(delta[:,1]*SCALES['observed_heading_rad']),np.cos(delta[:,1]*SCALES['observed_heading_rad']))/SCALES['observed_heading_rad']
        d=float(np.sqrt(np.mean(delta**2)))
        if not math.isfinite(d):raise ValueError('Nonfinite separation')
        pairs.append({'left':left,'right':right,'normalized_rms':d})
    return {'pairs':pairs,'minimum':min((p['normalized_rms'] for p in pairs),default=None),
            'mean':float(np.mean([p['normalized_rms'] for p in pairs])) if pairs else None}


@lru_cache(maxsize=1)
def _trusted_audit():
    return safety_audit()


def plan(report):
    # Current evidence only; no access to lab._backend, episodes, private parameters.
    fits=current_fits(report);audit=deepcopy(_trusted_audit())
    expected=[t.key for t in candidates()]
    if [r['candidate_id'] for r in audit['rows']]!=expected:raise ValueError('Wrong finite grid')
    rows=[];forecasts=0
    for t,s in zip(candidates(),audit['rows']):
        # Forecast even rejected trials for transparent audit, never recommend them.
        error=None
        try:
            predicted=trajectories(fits,t) if len(fits)>=2 else {}
            forecasts+=len(predicted)
            d=separation(predicted)
        except (ValueError,FloatingPointError,OverflowError):
            d=separation({});error='unavailable_forward_model'
        within_budget=report['remaining']['experiments']>0 and t.duration_s+2.<=report['remaining']['time_s']
        available=d['minimum'] is not None and d['minimum']>1e-9
        utility=d['minimum']-.01*t.duration_s if available and s['accepted'] and within_budget else None
        rows.append({'candidate_id':t.key,'name':t.name,'params':t.params(),'accepted':s['accepted'],
          'predictive_margin_m':s['predictive_margin_m'],'discrimination':d,
          'utility':utility,'forecast_available':available,'forecast_error':error,'within_budget':within_budget})
    ranked=sorted((r for r in rows if r['utility'] is not None),key=lambda r:(-r['utility'],r['candidate_id']))
    return {'schema_version':'nautilus.experiment-plan.v3','evidence_refs':report['evidence_refs'],
      'fit_names':[f['hypothesis'] for f in fits],'fit_fingerprint':fingerprint(fits),
      'status':'ranked' if ranked else 'no_safe_informative_candidate' if not any(r['accepted'] for r in rows) else 'insufficient_current_competing_fits',
      'candidate_count':len(rows),'forward_simulations':forecasts,'scales':SCALES,'cost':'minimum separation minus .01 * duration_s; safety hard constraint',
      'recommended_ids':[r['candidate_id'] for r in ranked[:3]],'rows':rows,'qualification':QUALIFICATION}
