from pathlib import Path
from dataclasses import asdict
import argparse,json
import numpy as np
import nautilus.v2_models as models
from nautilus.simulator import Experiment,simulate,Mission,Faults,PlantConfig,Vehicle,effective_vehicle
from nautilus.diagnosis import _prepare,_predict,FitConfig
from nautilus.v2_experiments import Trial,forward
from types import SimpleNamespace


def instrument(episodes, budget=40):
    original=models.least_squares
    attempts=[]
    def wrapper(fun,x0,**kwargs):
        trace=[]
        def observed(x):
            value=fun(x)
            assert np.all(np.isfinite(value))
            trace.append({'x':np.asarray(x).tolist(),'sse':float(value@value),
                          'rows':len(value),'max_abs':float(np.max(np.abs(value)))})
            return value
        result=original(observed,x0,**kwargs)
        attempts.append({'initial':list(x0),'x':result.x.tolist(),'success':bool(result.success),
                         'status':int(result.status),'message':result.message,'nfev':result.nfev,'njev':result.njev,
                         'optimality':float(result.optimality),'cost':float(result.cost),'active_mask':result.active_mask.tolist(),
                         'jacobian_singular_values':np.linalg.svd(result.jac,compute_uv=False).tolist(),'trace':trace})
        return result
    models.least_squares=wrapper
    try:fit=models.fit_model(episodes,'actuator_lag',max_nfev=budget)
    finally:models.least_squares=original
    total=0
    physical=[];commands=[]
    faults,plant,control=models.configs('actuator_lag',fit.parameters['actuator_tau_s'])
    for episode in episodes:
        a,_=_prepare(episode['observations'],FitConfig(method='observer'))
        assert abs(a[0,0])<1e-9 and np.allclose(np.diff(a[:,0]),.05)
        total+=len(a)
        prediction=_predict(a,effective_vehicle(Vehicle(),plant),faults,'observer',{'actuator_tau_s':plant.actuator_tau_s,'thrust_deadzone_n':plant.thrust_deadzone_n})
        delta=prediction-a[:,1:4]
        delta[:,1]=np.arctan2(np.sin(delta[:,1]),np.cos(delta[:,1]))
        delta/=np.array([.035,.004,.003]);delta[1:]/=np.sqrt(2)
        physical.append(delta.ravel())
        commands.append(((models.commanded(a,control,episode['experiment'])-a[:,4:6])/.05).ravel())
    assert fit.episode_lengths==[len(_prepare(e['observations'],FitConfig(method='observer'))[0]) for e in episodes]
    residual=np.concatenate(physical+commands)
    assert np.isclose(residual@residual,fit.weighted_sse,rtol=1e-12)
    for attempt in attempts:
        assert len(attempt['trace'])>=attempt['nfev']
        assert all(t['rows']==5*total for t in attempt['trace'])
    return {'fit':asdict(fit),'attempts':attempts,'objective_rows':5*total,'budget':budget}


def episodes_from(record):
    history=record['record']['after']['history']
    events=[e for e in history if e['type']=='observation']
    initial={'observations':events[0]['observations'],'experiment':Experiment()}
    event=events[1];trial=Trial(**event['request'])
    return [initial,{'observations':event['observations'][:event['fit_rows']],'experiment':trial.experiment()}]


def run(source,output):
    destination=Path(output).resolve();root=Path(__file__).resolve().parent
    if destination==root or root in destination.parents:raise ValueError('Private output required')
    destination.mkdir(exist_ok=True,parents=True)
    cases=[]
    for path in sorted(Path(source).glob('[0-9]*.json')):
        record=json.loads(path.read_text());name=record['case']
        if name in ('port','starboard'):
            episodes=episodes_from(record)
            results={stage:instrument(eps,budget) for stage,eps,budget in [('initial',episodes[:1],40),('joint',episodes,40),('budget_probe',episodes,160)]}
            cases.append({'case':name,'scope':'Previously exposed development reproduction','results':results})
    for i,side in enumerate(('port','starboard')):
        faults=Faults(**{side+'_efficiency':.5})
        initial=simulate(faults=faults,mission=Mission(duration_s=.3,seed=1150000+i)).observations
        trial=Trial('differential_step',duration_s=8.,phase_s=1.,cruise_thrust_n=0.,differential_n=4.)
        observed=simulate(faults=faults,mission=Mission(duration_s=8.,seed=1150000+i),experiment=trial.experiment()).observations
        eps=[{'observations':initial,'experiment':Experiment()},{'observations':observed[:-1],'experiment':trial.experiment()}]
        cases.append({'case':'fresh_'+side,'scope':'Fresh development1150000 block',
                      'results':{'initial':instrument(eps[:1]),'joint':instrument(eps),'budget_probe':instrument(eps,160)}})
    result={'scope':'Characterization only; default max_nfev40 and all scoring rules unchanged','cases':cases}
    with (destination/'optimizer.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    for case in cases:
        for stage,r in case['results'].items():print(case['case'],stage,r['fit']['converged'],[(a['status'],a['nfev'],a['x'],a['optimality']) for a in r['attempts']],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.source,a.output)
