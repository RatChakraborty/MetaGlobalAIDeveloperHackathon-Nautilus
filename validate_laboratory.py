from pathlib import Path
from dataclasses import asdict
from copy import deepcopy
import argparse,json
from nautilus.simulator import simulate, Mission, Faults, PlantConfig, OBSERVATION_FIELDS
from nautilus.lab_safety import SafeBackend
from nautilus.laboratory import Laboratory
from nautilus.investigator import investigate
from nautilus.v2_experiments import Trial
from nautilus.protocol import digest

TEMPLATES=('nominal','lateral_current','port_degradation','starboard_degradation','heading_bias','actuator_lag','thrust_deadzone','drag_yaw')
PLANS=[('port',Faults(port_efficiency=.5),PlantConfig()),
       ('starboard',Faults(starboard_efficiency=.5),PlantConfig()),
       ('lag',Faults(),PlantConfig(actuator_tau_s=.7)),
       ('deadzone',Faults(),PlantConfig(thrust_deadzone_n=3.)),
       ('current',Faults(current_y=.5),PlantConfig()),
       ('lag_straight_control',Faults(),PlantConfig(actuator_tau_s=.7)),
       ('nominal',Faults(),PlantConfig())]


class ScriptedInvestigator:
    def __init__(self, trial):
        self.trial=trial
        self.actions=[]
        self.before=None
        self.after=None

    def choose(self,state):
        phase=len(state['evidence_refs'])
        fitted={f['hypothesis'] for f in state['fits']}
        for name in TEMPLATES:
            if name not in fitted:
                action={'op':'propose_hypothesis','template':name,'knobs':{},'bounds':{},'rationale':'Predeclared public-evidence comparison'}
                break
        else:
            if phase==1:
                self.before=deepcopy(state)
                action={'op':'request_experiment','name':self.trial.name,'params':self.trial.params()}
            else:
                self.after=deepcopy(state)
                selected=state['numerical_summary']['selected']
                action={'op':'finalize','diagnosis':{'hypothesis':selected,'evidence_refs':state['evidence_refs']},
                        'confidence':'tentative' if selected else 'abstain',
                        'ambiguity_statement':'Conditional on eight requested templates; score gaps are heuristic and discrepancy remains possible.'}
        self.actions.append(deepcopy(action))
        return action


def scientific(value):
    if isinstance(value,dict):return {k:scientific(v) for k,v in value.items() if k!='elapsed_s'}
    if isinstance(value,list):return [scientific(v) for v in value]
    return value


def audit(ledger):
    previous=None;refs=set()
    for i,event in enumerate(ledger):
        assert event['index']==i and event['previous_hash']==previous
        assert event['event_hash']==digest({k:v for k,v in event.items() if k!='event_hash'})
        previous=event['event_hash']
        if event['type']=='observation':
            assert all(set(r)==set(OBSERVATION_FIELDS) for r in event['observations'])
            refs.add(previous)
        if event['type']=='fit':assert set(event['report']['evidence_refs'])<=refs
        if event['type']=='finalized':assert set(event['diagnosis']['evidence_refs'])<=refs
    assert not any(k in json.dumps(ledger) for k in ('private_results','true_excursion','true_final_speed','injected_value'))


def one(index, faults, plant, trial):
    seed=1140000+index
    initial=simulate(faults=faults,plant=plant,mission=Mission(duration_s=.3,seed=seed)).observations
    backend=SafeBackend(faults=faults,plant=plant,seed=seed)
    lab=Laboratory(initial,backend)
    investigator=ScriptedInvestigator(trial)
    final=investigate(lab,investigator,max_actions=32)
    before,after=investigator.before,investigator.after
    assert lab.fit_calls==2*len(TEMPLATES) and lab.tests==1
    assert len(after['evidence_refs'])==2 and before['evidence_refs'][0]==after['evidence_refs'][0]
    observation=[e for e in lab.ledger if e['type']=='observation'][-1]
    assert observation['request']==asdict(trial)
    assert digest(observation['observations'])!=digest(initial)
    assert all(len(f['episode_lengths'])==2 for f in after['fits'])
    assert all(f['evidence_refs']==after['evidence_refs'] for f in after['fits'])
    assert [e['report']['hypothesis'] for e in lab.ledger if e['type']=='fit']==list(TEMPLATES)*2
    audit(lab.ledger)
    return {'before':before,'after':after,'actions':investigator.actions,'final':final,
            'private_execution':backend.private_results,'charged_time_s':lab.test_time_s}


def run(destination):
    output=Path(destination).resolve();root=Path(__file__).resolve().parent
    if output==root or root in output.parents:raise ValueError('Private output outside source required')
    output.mkdir(exist_ok=True,parents=True)
    plan={'seed_start':1140000,'cases':[name for name,_,_ in PLANS], 'templates':TEMPLATES,
          'initial_s':.3,'experiment_s':8,'repeats':2,'scope':'Development demonstrations; no held-out evaluation, truth-independent scripted actions.'}
    path=output/'plan.json'
    if not path.exists():path.write_text(json.dumps(plan,indent=2))
    else:assert json.loads(path.read_text())==json.loads(json.dumps(plan))
    for i,(name,faults,plant) in enumerate(PLANS):
        path=output/f'{i:02d}-{name}.json'
        if path.exists():continue
        trial=Trial('thrust_step',duration_s=8.,phase_s=1.,amplitude_n=12.) if name=='lag_straight_control' else Trial('differential_step',duration_s=8.,phase_s=1.,cruise_thrust_n=0.,differential_n=4.)
        a=one(i,faults,plant,trial);b=one(i,faults,plant,trial)
        assert scientific(a)==scientific(b)
        record={'case':name,'seed':1140000+i,'private_faults':asdict(faults),'private_plant':asdict(plant),
                'repeat_scientifically_identical':True,'record':a}
        with path.open('x') as f:json.dump(record,f,indent=2,allow_nan=False)
        print(name,a['before']['numerical_summary'],a['after']['numerical_summary'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);run(parser.parse_args().output)
