
from dataclasses import asdict,replace
from pathlib import Path
import argparse,json,time
import numpy as np

from nautilus.simulator import (Faults,Controller,PlantConfig,HIDDEN_PLANT,Mission,
                                Experiment,simulate,effective_vehicle,Vehicle)
from nautilus.diagnosis import _prepare,_predict,FitConfig
from nautilus.v2_models import fit_model,configs
from nautilus.v2_experiments import LIBRARY,Trial,forward,envelope

ROOT=Path(__file__).resolve().parent
SCALES=np.array([.035,.004,.003])
CHANNELS=('observed_y_m','observed_heading_rad','observed_yaw_rate_radps')


def gap(a,b):
    n=min(len(a),len(b))
    assert np.allclose([r['time_s'] for r in a[:n]],[r['time_s'] for r in b[:n]])
    delta=np.array([[x[c]-y[c] for c in CHANNELS] for x,y in zip(a[:n],b[:n])])
    delta[:,1]=np.arctan2(np.sin(delta[:,1]),np.cos(delta[:,1]))
    return float(np.sqrt(np.mean((delta/SCALES)**2)))


def public_prediction(a,name,value):
    f,p,c=configs(name,value)
    return _predict(a,effective_vehicle(Vehicle(),p),f,'observer',
                    {'actuator_tau_s':p.actuator_tau_s,'thrust_deadzone_n':p.thrust_deadzone_n})


def sensitivity(a,eta):

    def predict(e,d):
        f=Faults(port_efficiency=e,starboard_efficiency=e)
        v=effective_vehicle(Vehicle(),PlantConfig(uniform_drag_scale=d))
        return _predict(a,v,f,'observer')
    columns=[]
    for i in (0,1):
        h=1e-3;left=[eta,1.];right=[eta,1.]
        left[i]-=h;right[i]+=h
        delta=(predict(*right)-predict(*left))/(2*h)
        delta[:,1]=np.arctan2(np.sin(delta[:,1]*2*h),np.cos(delta[:,1]*2*h))/(2*h)
        columns.append((delta/SCALES).ravel()*([.8,2.][i]))
    norms=[float(np.linalg.norm(c)) for c in columns]
    cosine=float(columns[0]@columns[1]/(norms[0]*norms[1])) if min(norms)>1e-10 else None
    return {'parameters':['common_thrust_scale','uniform_drag_scale'],
            'steps':[1e-3,1e-3],'parameter_scaling':[.8,2.],
            'scaled_sensitivity_norms':norms,'cosine':cosine,
            'warning':'Local conditional public-observation sensitivity; not posterior uncertainty.'}


def generated(name,value,seed,experiment=Experiment(),duration=30.):
    f,p,c=configs(name,value)


    p=replace(p,actuator_tau_s=p.actuator_tau_s or HIDDEN_PLANT.actuator_tau_s,
              thrust_deadzone_n=p.thrust_deadzone_n or HIDDEN_PLANT.thrust_deadzone_n,
              drag_scale=HIDDEN_PLANT.drag_scale)
    return simulate(faults=f,plant=p,controller=c,
                    mission=Mission(duration_s=duration,seed=seed),experiment=experiment).observations


def run():
    started=time.perf_counter();groups={};matrices={}
    for group,names,values in (
        ('common_drag',('common_thrust_scale','uniform_drag_scale'),[(e,1/e) for e in (.5,.6,.7,.8,.9)]),
        ('lag_deadzone',('actuator_lag','thrust_deadzone'),list(zip((.3,.5,.7,.9,1.1),(1.,2.,3.,4.,5.))))):
        records=[]
        for i,(v1,v2) in enumerate(values):
            for repeat in range(2):
                for side,(name,value) in enumerate(zip(names,(v1,v2))):
                    seed=(600000 if group=='common_drag' else 601000)+i*4+repeat*2+side
                    rows=generated(name,value,seed)
                    ep={'observations':rows,'experiment':Experiment()}
                    fits=[fit_model([ep],h) for h in names]
                    a,_=_prepare(rows,FitConfig(method='observer'))
                    predictions=[public_prediction(a,f.hypothesis,next(iter(f.parameters.values()))) for f in fits]
                    d=predictions[0]-predictions[1];d[:,1]=np.arctan2(np.sin(d[:,1]),np.cos(d[:,1]))
                    distance=float(np.sqrt(np.mean((d/SCALES)**2)))
                    competitive=all(f.converged and f.weighted_rmse<=2 for f in fits) and abs(fits[0].penalized_score-fits[1].penalized_score)<=6
                    records.append({'seed':seed,'injected_family':name,'value':value,
                                    'fits':[asdict(f) for f in fits],
                                    'public_conditional_separation':distance,'competitive':competitive,
                                    'sensitivity':sensitivity(a,v1) if group=='common_drag' else None})
                    print(group,seed,name,'competitive',competitive,'separation',round(distance,4),flush=True)
        matrix=[]

        v1,v2=values[2]
        for trial in LIBRARY:
            rows=[generated(n,v,602000+len(matrix),trial.experiment(),trial.duration_s)
                  for n,v in zip(names,(v1,v2))]
            fits=[fit_model([{'observations':generated(n,v,602100), 'experiment':Experiment()}],n)
                  for n,v in zip(names,(v1,v2))]
            predicted=gap(forward(fits[0],trial),forward(fits[1],trial))
            empirical=gap(*rows)
            matrix.append({'request':asdict(trial),'predicted_noise_separation':predicted,
                           'empirical_noise_separation':empirical,
                           'envelopes':[envelope(x) for x in rows],
                           'simulated_cost_s':trial.duration_s})
        qualifies=(sum(r['competitive'] for r in records)>=12
                   and float(np.median([r['public_conditional_separation'] for r in records]))<=1
                   and max(x['empirical_noise_separation'] for x in matrix)>2)
        groups[group]={'records':records,'competitive_count':sum(r['competitive'] for r in records),
                       'median_public_separation':float(np.median([r['public_conditional_separation'] for r in records])),
                       'qualified_ambiguity_family':qualifies}
        matrices[group]=matrix


    amplitude=[]
    for amp in (.5,1.,3.,6.):
        trial=Trial('differential_step',differential_n=amp,cruise_thrust_n=0.)
        curves=[]
        for plant in (PlantConfig(actuator_tau_s=.6),PlantConfig(thrust_deadzone_n=2.)):
            rows=simulate(plant=plant,experiment=trial.experiment(),
                          mission=Mission(duration_s=12,seed=603000,
                                          sensor_y_std_m=0,sensor_heading_std_rad=0,sensor_yaw_rate_std_radps=0)).observations
            curves.append([r['observed_yaw_rate_radps']/amp for r in rows])
        amplitude.append({'amplitude_n':amp,'normalized_public_gyro_curves':curves})
    control=[]
    for name,value in (('heading_controller_gain',12.),('controller_lookahead',14.)):
        rows=generated(name,value,604000)
        ep={'observations':rows,'experiment':Experiment()}
        control.append({'family':name,'registry_fit':asdict(fit_model([ep],name)),
                        'nominal_fit':asdict(fit_model([ep],'nominal')),
                        'note':'Digital command consistency distinguishes controller changes from actuator faults.'})
    return {'split':'new_development_only','groups':groups,'separation_matrices':matrices,
            'amplitude_response':amplitude,'controller_checks':control,'elapsed_s':time.perf_counter()-started,
            'observations':'Six original public fields; NO forward speed/x channel.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if ROOT==a.output.resolve() or ROOT in a.output.resolve().parents:p.error('Private outputs must be outside source')
    if a.output.exists():p.error('Refusing overwrite')
    result=run();a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
