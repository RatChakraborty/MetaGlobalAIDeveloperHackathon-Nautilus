
from dataclasses import dataclass, asdict, replace
import math
import time

import numpy as np
from scipy.optimize import least_squares

from .diagnosis import HYPOTHESES, FitConfig, _prepare, _predict
from .simulator import (Vehicle, Faults, PlantConfig, Controller, Experiment,
                        effective_vehicle, experiment_command, OBSERVATION_FIELDS)


@dataclass(frozen=True)
class Template:
    identifier: str
    parameter: str | None
    units: str
    nominal: float | None
    bounds: tuple | None
    mechanism: str
    confounders: tuple
    healthy_range: tuple | None = None
    required_observations: tuple = OBSERVATION_FIELDS
    supported_experiments: tuple = ('cable_follow','thrust_step','coast_down',
                                    'differential_step','amplitude_ramp','heading_response')


REGISTRY = {h: Template(h,s[0] if s else None,
                       'm/s' if h=='lateral_current' else 'rad' if h=='heading_bias' else '1',
                       getattr(Faults(),s[0]) if s else None, tuple(s[1:]) if s else None,
                       'Original supported physical model', ('unmodeled dynamics',))
            for h,s in HYPOTHESES.items()}
for row in (
    ('actuator_lag','actuator_tau_s','s',0.,(0.,1.2),'First-order actuator response',('dead zone','controller response')),
    ('thrust_deadzone','thrust_deadzone_n','N',0.,(0.,6.),'Signed command dead zone',('common thrust loss',)),
    ('drag_surge','drag_surge_scale','1',1.,(.5,3.),'Surge linear and quadratic drag multiplier',('common thrust loss',)),
    ('drag_sway','drag_sway_scale','1',1.,(.5,3.),'Sway linear and quadratic drag multiplier',('lateral current',)),
    ('drag_yaw','drag_yaw_scale','1',1.,(.5,3.),'Yaw linear and quadratic drag multiplier',('actuator lag','thrust scale')),
    ('heading_controller_gain','heading_kp','N*m/rad',39.,(5.,80.),'Requested heading moment gain',('lookahead',)),
    ('controller_lookahead','lookahead_m','m',7.,(2.,20.),'Cable-following geometric lookahead',('heading gain',)),
    ('common_thrust_scale','common_thrust_scale','1',1.,(.2,1.),'Equal multiplicative efficiency on both thrusters',('uniform hull drag','dead zone')),
    ('uniform_drag_scale','uniform_drag_scale','1',1.,(1.,3.),'All linear and quadratic drag coefficients scaled',('common thrust loss',)),
):
    REGISTRY[row[0]]=Template(*row)

EXTENSIONS=tuple(h for h in REGISTRY if h not in HYPOTHESES)


HEALTHY={'actuator_lag':(0.,.25),'thrust_deadzone':(0.,.5),
         'drag_surge':(.9,1.1),'drag_sway':(.9,1.1),'drag_yaw':(.9,1.1),
         'heading_controller_gain':(35.,43.),'controller_lookahead':(6.,8.),
         'common_thrust_scale':(.9,1.),'uniform_drag_scale':(1.,1.1)}
for name,spec in list(REGISTRY.items()):
    REGISTRY[name]=replace(spec,healthy_range=HEALTHY.get(name,(spec.nominal,spec.nominal) if spec.parameter else None))


def finding(fit):
    spec=REGISTRY[fit.hypothesis]
    if not spec.parameter:return 'nominal'
    value=fit.parameters[spec.parameter]
    return 'nominal' if spec.healthy_range[0]<=value<=spec.healthy_range[1] else fit.hypothesis


def number(value):
    return type(value) in (int,float) and math.isfinite(value)


def validate_proposal(name, knobs=None, bounds=None):
    if type(name) is not str or name not in REGISTRY:
        raise ValueError('Unknown hypothesis template')
    spec=REGISTRY[name];knobs={} if knobs is None else knobs;bounds={} if bounds is None else bounds
    expected={spec.parameter} if spec.parameter else set()
    if type(knobs) is not dict or type(bounds) is not dict or set(knobs)-expected or set(bounds)-expected:
        raise ValueError('Unsupported parameter names or combinations')
    limits=spec.bounds
    if bounds:
        supplied=bounds[spec.parameter]
        if (type(supplied) not in (list,tuple) or len(supplied)!=2
                or not all(number(v) for v in supplied)
                or not spec.bounds[0] <= supplied[0] < supplied[1] <= spec.bounds[1]):
            raise ValueError('Bounds must be a nonempty subset of registry bounds')
        limits=tuple(supplied)
    if knobs and (not number(knobs[spec.parameter]) or not limits[0]<=knobs[spec.parameter]<=limits[1]):
        raise ValueError('Initial parameter outside allowed bounds')
    return spec,limits


def configs(name, value=None):
    spec=REGISTRY[name]
    if spec.parameter and (not number(value) or not spec.bounds[0]<=value<=spec.bounds[1]):
        raise ValueError('Model parameter outside registry envelope')
    faults,plant,control=Faults(),PlantConfig(),Controller()
    if name in HYPOTHESES and spec.parameter:
        faults=replace(faults,**{spec.parameter:value})
    elif name=='common_thrust_scale':
        faults=replace(faults,port_efficiency=value,starboard_efficiency=value)
    elif name in ('heading_controller_gain','controller_lookahead'):
        control=replace(control,**{spec.parameter:value})
    elif name!='nominal':
        plant=replace(plant,**{spec.parameter:value})
    return faults,plant,control


def commanded(a, control, experiment):


    if experiment.cruise_thrust_n is not None:
        control=replace(control,cruise_thrust=experiment.cruise_thrust_n)
    return np.array([experiment_command(r[0],r[1],r[2],r[3],Vehicle(),control,experiment)[:2] for r in a])


@dataclass
class ModelFit:
    hypothesis: str
    parameters: dict
    bounds: dict
    converged: bool
    status: str
    weighted_sse: float
    weighted_rmse: float
    penalized_score: float
    physical_wrms: float
    command_wrms: float
    evaluations: int
    optimization_attempts: int
    elapsed_s: float
    warnings: list
    episode_lengths: list
    sensitivity_scaled_norm: float | None


def fit_model(episodes,name,*,knobs=None,bounds=None,starts=2,max_nfev=40,dt_s=.05):

    spec,limits=validate_proposal(name,knobs,bounds)
    if type(starts) is not int or not 1<=starts<=3 or type(max_nfev) is not int or max_nfev<1:
        raise ValueError('Invalid optimization budget')
    if not episodes:raise ValueError('No public evidence')
    prepared=[]
    for episode in episodes:
        if set(episode)!={'observations','experiment'} or not isinstance(episode['experiment'],Experiment):
            raise ValueError('Expected public reset episode and declared experiment')
        a,notes=_prepare(episode['observations'],FitConfig(dt_s=dt_s,method='observer'))
        prepared.append((a,episode['experiment']))
    evaluations=0;started=time.perf_counter()
    fixed_commands=None
    if name not in ('heading_controller_gain','controller_lookahead'):
        fixed_commands=[commanded(a,Controller(),ex) for a,ex in prepared]
    def residual(p,parts=False):
        nonlocal evaluations
        evaluations+=1
        f,plant,c=configs(name,float(p[0]) if spec.parameter else None)
        v=effective_vehicle(Vehicle(),plant)
        actuator={'actuator_tau_s':plant.actuator_tau_s,'thrust_deadzone_n':plant.thrust_deadzone_n}
        physical=[];commands=[]
        for i,(a,ex) in enumerate(prepared):
            predicted=_predict(a,v,f,'observer',actuator)
            delta=predicted-a[:,1:4]
            delta[:,1]=np.arctan2(np.sin(delta[:,1]),np.cos(delta[:,1]))
            delta/=np.array([.035,.004,.003]);delta[1:]/=math.sqrt(2)
            physical.append(delta.ravel())
            cmd=fixed_commands[i] if fixed_commands is not None else commanded(a,c,ex)
            commands.append(((cmd-a[:,4:6])/.05).ravel())
        phy=np.concatenate(physical);cmd=np.concatenate(commands)
        return (phy,cmd) if parts else np.concatenate([phy,cmd])
    warnings=[];sensitivity=None
    if spec.parameter:
        guesses=[knobs[spec.parameter]] if knobs else np.linspace(limits[0]+.1*(limits[1]-limits[0]),limits[1]-.1*(limits[1]-limits[0]),starts)
        solutions=[least_squares(residual,[g],bounds=([limits[0]],[limits[1]]),max_nfev=max_nfev,x_scale='jac') for g in guesses]
        valid=[s for s in solutions if s.success]
        solution=min(valid or solutions,key=lambda s:s.cost)
        p=solution.x;converged=bool(solution.success);status=solution.message
        sensitivity=float(np.linalg.norm(solution.jac)*(limits[1]-limits[0]))
        if sensitivity<1:warnings.append('Weak local public-observation sensitivity; parameter recovery unsupported.')
        if min(p[0]-limits[0],limits[1]-p[0])<1e-4*(limits[1]-limits[0]):warnings.append('Parameter at registry bound.')
        parameters={spec.parameter:float(p[0])};fit_bounds={spec.parameter:limits};attempts=len(guesses)
    else:
        p=[];parameters={};fit_bounds={};converged=True;status='No free parameters';attempts=0
    phy,cmd=residual(p,True)
    sse=float(phy@phy+cmd@cmd)
    pw=float(np.sqrt(np.mean(phy**2)));cw=float(np.sqrt(np.mean(cmd**2)))
    if not converged:warnings.append('Optimizer failed; not evidence for ambiguity or identification.')
    warnings+=['Public-only measured-state innovations; no speed/x channel.',
               'Scores and local sensitivities are not calibrated posterior uncertainty.',
               'Known zero reset and supplied public command history required.']
    return ModelFit(name,parameters,fit_bounds,converged,str(status),sse,max(pw,cw),
                    sse+len(parameters)*math.log(len(phy)+len(cmd)),pw,cw,evaluations,attempts,
                    time.perf_counter()-started,warnings,[len(a) for a,_ in prepared],sensitivity)


def catalog():
    return {name:{**asdict(t),'fit':'bounded multistart shared-episode least_squares',
                  'convergence':'scipy success and finite score','complexity':'k*log(5*N)',
                  'weak_identifiability':'scaled local Jacobian norm <1; no covariance claim'}
            for name,t in REGISTRY.items()}
