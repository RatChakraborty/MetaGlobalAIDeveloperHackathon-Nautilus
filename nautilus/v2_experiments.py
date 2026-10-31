"""Strict waveform requests and hidden execution with an observed envelope guard."""
from dataclasses import dataclass,asdict
import hashlib
import math

from .simulator import (Experiment,Mission,Vehicle,simulate)
from .v2_models import configs,REGISTRY,number


@dataclass(frozen=True)
class Trial:
    name: str
    duration_s: float=12.
    amplitude_n: float=8.
    differential_n: float=2.
    cruise_thrust_n: float=8.
    phase_s: float=3.
    heading_step_rad: float=.25

    def __post_init__(self):
        if self.name not in ('thrust_step','coast_down','differential_step','amplitude_ramp','heading_response','cable_follow'):
            raise ValueError('Unknown experiment')
        vals=(self.duration_s,self.amplitude_n,self.differential_n,self.cruise_thrust_n,self.phase_s,self.heading_step_rad)
        if (not all(number(v) for v in vals) or not 4<=self.duration_s<=16
                or not 0<=self.amplitude_n<=20 or not abs(self.differential_n)<=6
                or not 0<=self.cruise_thrust_n<=20 or not 0<self.phase_s<self.duration_s
                or abs(self.heading_step_rad)>.5
                or max(self.cruise_thrust_n,self.amplitude_n)+abs(self.differential_n)>25):
            raise ValueError('Invalid actuation/time/reset-mode envelope')
        if self.name=='cable_follow' and self.cruise_thrust_n<=0:
            raise ValueError('Cruise must be positive')

    def experiment(self):
        return Experiment(cruise_thrust_n=self.cruise_thrust_n,
                          duration_s=self.duration_s,maneuver=self.name,phase_s=self.phase_s,
                          amplitude_n=self.amplitude_n,differential_n=self.differential_n,
                          heading_step_rad=self.heading_step_rad,max_abs_observed_y_m=8.)

    @property
    def key(self):
        return hashlib.sha256(str((self.name,sorted(self.params().items()))).encode()).hexdigest()[:16]

    def params(self):
        return {k:getattr(self,k) for k in PARAMETERS[self.name]}


PARAMETERS={
 'cable_follow':('duration_s','cruise_thrust_n'),
 'thrust_step':('duration_s','amplitude_n','phase_s'),
 'coast_down':('duration_s','amplitude_n','differential_n','phase_s'),
 'differential_step':('duration_s','differential_n','cruise_thrust_n','phase_s'),
 'amplitude_ramp':('duration_s','amplitude_n','phase_s'),
 'heading_response':('duration_s','cruise_thrust_n','phase_s','heading_step_rad'),
}

LIBRARY=(Trial('differential_step',differential_n=4.,cruise_thrust_n=0.),
         Trial('coast_down',amplitude_n=15.,differential_n=1.,phase_s=5.),
         Trial('amplitude_ramp',amplitude_n=6.,phase_s=9.),
         Trial('heading_response',cruise_thrust_n=8.),
         Trial('differential_step',differential_n=1.,cruise_thrust_n=0.),
         Trial('thrust_step',amplitude_n=12.,differential_n=0.),
         Trial('coast_down',amplitude_n=15.,differential_n=0.,phase_s=5.))


def parse_trial(name,params):
    if type(name) is not str or name not in PARAMETERS:raise ValueError('Unknown experiment mode')
    fields=set(PARAMETERS[name])
    if type(params) is not dict or set(params)-fields:raise ValueError('Unknown experiment parameters')
    return Trial(name,**params)


def envelope(rows):
    maximum=max(abs(r['observed_y_m']) for r in rows)
    return {'max_abs_observed_y_m':maximum,'inspection_corridor_excursion':maximum>1.5,
            'observed_guard_triggered':maximum>8.,'physical_safety_proven':False}


def forward(fit,trial,*,dt_s=.05):
    spec=REGISTRY[fit.hypothesis]
    value=fit.parameters[spec.parameter] if spec.parameter else None
    faults,plant,control=configs(fit.hypothesis,value)
    mission=Mission(duration_s=trial.duration_s,dt_s=dt_s,sensor_y_std_m=0,
                    sensor_heading_std_rad=0,sensor_yaw_rate_std_radps=0,seed=0)
    return simulate(faults=faults,plant=plant,controller=control,mission=mission,
                    experiment=trial.experiment()).observations


class PrivateBackend:
    def __init__(self,*,faults,plant,controller,seed,dt_s=.05,count=3,time_s=48.):
        if not 0<dt_s<=.2 or type(count) is not int or not 0<=count<=3 or not number(time_s) or not 0<=time_s<=48:
            raise ValueError('Invalid backend budget')
        self._faults,self._plant,self._controller=faults,plant,controller
        self._seed,self._dt=seed,dt_s
        self._count,self._time=count,time_s
        self._seen=set()

    def execute(self,trial):
        if not isinstance(trial,Trial):raise ValueError('Only validated trials accepted')
        if self._count<=0 or trial.duration_s>self._time or trial.key in self._seen:raise ValueError('Trial budget exhausted or repeated')
        self._count-=1;self._time-=trial.duration_s;self._seen.add(trial.key)
        seed=int.from_bytes(hashlib.sha256(f'{self._seed}:{trial.key}'.encode()).digest()[:8],'big')
        rows=simulate(faults=self._faults,plant=self._plant,controller=self._controller,
                      mission=Mission(duration_s=trial.duration_s,dt_s=self._dt,seed=seed),
                      experiment=trial.experiment()).observations
        return {'observations':rows,'experiment':trial.experiment(),'envelope':envelope(rows)}
