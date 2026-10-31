from pathlib import Path
from dataclasses import asdict
import argparse,json,time
from nautilus.lab_safety import SafeBackend
from nautilus.v2_experiments import LIBRARY
from nautilus.v2_models import fit_model
from nautilus.simulator import Faults,PlantConfig


def run(output):
    p=Path(output).resolve();root=Path(__file__).resolve().parent
    if p==root or root in p.parents:raise ValueError('Private output outside source required')
    results=[]
    plans=[('nominal',t,Faults(),PlantConfig()) for t in LIBRARY]
    plans += [('strong_current',LIBRARY[0],Faults(current_y=1.),PlantConfig()),
              ('lag',LIBRARY[1],Faults(),PlantConfig(actuator_tau_s=1.2)),
              ('deadzone',LIBRARY[2],Faults(),PlantConfig(thrust_deadzone_n=3.))]
    for i,(name,trial,faults,plant) in enumerate(plans):
        for mode in ('simulation_advisory','simulation_enforced'):
            backend=SafeBackend(faults=faults,plant=plant,seed=1131000+i,mode=mode)
            start=time.perf_counter();r=backend.execute(trial)
            row={'case':name,'seed':1131000+i,'mode':mode,'trial':asdict(trial),'result':r,'elapsed_s':time.perf_counter()-start}
            if r['accepted']:
                prefix=[o for o in r['observations'] if o['time_s']<r['execution']['fit_end_exclusive_s']-1e-9]
                try:row['nominal_fit']=asdict(fit_model([{'observations':prefix,'experiment':trial.experiment()}],'nominal'))
                except (ValueError,FloatingPointError,OverflowError) as exc:row['fit_failure']=str(exc)
                row['private_evaluation']=backend.private_results
            results.append(row)
            print(name,trial.name,mode,r['accepted'],r.get('execution',{}).get('observed_excursion'),flush=True)
    p.parent.mkdir(exist_ok=True,parents=True)
    with p.open('x') as f:json.dump({'scope':'Development only, no held-out generation','results':results},f,indent=2,allow_nan=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);run(parser.parse_args().output)
