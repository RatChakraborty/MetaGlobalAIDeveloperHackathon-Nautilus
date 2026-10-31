import argparse
import json
from pathlib import Path
from dataclasses import asdict
from nautilus.lab_safety import screen, guarded_trial
from nautilus.simulator import Faults, PlantConfig, Controller
from nautilus.v2_experiments import LIBRARY, Trial


def run(output):
    path=Path(output).resolve();root=Path(__file__).resolve().parent
    if path==root or root in path.parents: raise ValueError('Private output required')
    plans=[('nominal',Faults(),PlantConfig()),
           ('drag',Faults(),PlantConfig(uniform_drag_scale=3.)),
           ('lag',Faults(),PlantConfig(actuator_tau_s=1.2)),
           ('weak_port',Faults(port_efficiency=.3),PlantConfig()),
           ('strong_current',Faults(current_y=3.),PlantConfig(actuator_tau_s=1.2))]
    results=[]
    trial=Trial('thrust_step',duration_s=4.,phase_s=1.,amplitude_n=0.)
    for i,(name,faults,plant) in enumerate(plans):
        obs,metadata,private=guarded_trial(trial,faults,plant,Controller(),1120000+i)
        results.append({'case':name,'seed':1120000+i,'private_faults':asdict(faults),'private_plant':asdict(plant),
                        'execution':metadata,'private_outcome':private,'observations':obs,
                        'scope':'Evaluator-only guard stress test, not an authorized investigator dispatch'})
    result={'scope':'Fresh development, no held-out generation',
            'menu_screening':[{'trial':asdict(t),'screen':screen(t)} for t in LIBRARY],
            'guard_stress':results}
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print('Screen accepted:',sum(r['screen']['accepted'] for r in result['menu_screening']),'of',len(LIBRARY))
    for r in results:print(r['case'],r['execution']['stop_reason'],r['execution']['failure'],r['private_outcome']['true_excursion'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    run(parser.parse_args().output)
