from dataclasses import replace
import json
import pytest
from nautilus.simulator import simulate, Mission, Faults, PlantConfig, Controller, OBSERVATION_FIELDS
from nautilus.lab_safety import SafeBackend, screen, guarded_trial
from nautilus.laboratory import Laboratory
from nautilus.investigator import investigate, DeterministicInvestigator
from nautilus.v2_experiments import Trial
from nautilus.protocol import digest


def rows(): return simulate(mission=Mission(duration_s=.3, seed=1110000)).observations


def test_independent_fit_and_abstention():
    lab = Laboratory(rows(), SafeBackend())
    report = lab.propose_hypothesis('nominal', {}, {}, 'Test one requested hypothesis')
    assert lab.fit_calls == 1 and len(lab.get_fit_report()['fits']) == 1
    assert report['method'] == 'singleton' and report['residual_diagnostics']
    result = lab.finalize({'hypothesis': None, 'evidence_refs': lab.evidence_refs()}, 'abstain', 'Insufficient evidence')
    assert result['confidence'] == 'abstain'
    with pytest.raises(ValueError): lab.request_experiment('thrust_step', {})


def test_state_copy_and_ledger_isolation():
    lab = Laboratory(rows(), SafeBackend(faults=Faults(current_y=.4)))
    state = lab.get_fit_report(); state['history'].clear()
    assert lab.ledger
    previous = None
    for event in lab.ledger:
        assert event['previous_hash'] == previous
        assert digest({k:v for k,v in event.items() if k!='event_hash'}) == event['event_hash']
        previous = event['event_hash']
    assert '_faults' not in json.dumps(lab.get_fit_report())
    assert 'private_results' not in json.dumps(lab.get_fit_report())
    assert set(state['history']) == set()


def test_unsafe_rejection_without_execution():
    backend = SafeBackend(mode='simulation_enforced')
    lab = Laboratory(rows(), backend)
    result = lab.request_experiment('heading_response', {'duration_s':16., 'heading_step_rad':.5})
    assert not result['accepted'] and lab.tests == 0 and not backend.private_results
    assert lab.ledger[-1]['type'] == 'safety'


def test_guard_keeps_integrating_residual_motion():
    trial = Trial('thrust_step', duration_s=4., phase_s=1., amplitude_n=0.)
    obs, meta, private = guarded_trial(trial, Faults(current_y=3.), PlantConfig(actuator_tau_s=1.2), Controller(), 1110001)
    assert meta['guard_time_s'] is not None
    assert obs[-1]['time_s'] >= meta['guard_time_s']+1.99
    assert meta['stopped_vehicle'] != True
    assert private['true_excursion']
    assert all(set(r)==set(OBSERVATION_FIELDS) for r in obs)


@pytest.mark.parametrize('strategy', ['fixed','random','greedy','passive','exhaustive'])
def test_common_investigator_path(strategy):
    lab = Laboratory(rows(), SafeBackend(), fit_budget=1, experiment_budget=0)
    result = investigate(lab, DeterministicInvestigator(strategy), max_actions=4)
    assert result['confidence'] in ('supported','abstain')
    assert lab.fit_calls == 1 and lab.tests == 0


def test_mock_investigator_and_invalid_action_limit():
    class Mock:
        def choose(self,state): return {'op':'execute_python','code':'1'}
    lab = Laboratory(rows(), SafeBackend())
    result = investigate(lab, Mock(), max_actions=2)
    assert result['confidence'] == 'abstain'
    assert sum(e['type']=='rejected' for e in lab.ledger)==2


def test_invalid_backend_and_budget():
    with pytest.raises(ValueError): Laboratory(rows(), lambda x:x)
    lab = Laboratory(rows(), SafeBackend(), fit_budget=1)
    lab.propose_hypothesis('nominal', {}, {}, 'test')
    with pytest.raises(ValueError): lab.propose_hypothesis('nominal', {}, {}, 'test')
    with pytest.raises(ValueError): lab.finalize({'hypothesis':None,'evidence_refs':['forged']},'abstain','test')


def test_mock_full_roundtrip_with_controlled_screen(monkeypatch):
    import nautilus.lab_safety as safety
    import nautilus.laboratory as laboratory
    accepted = lambda trial: {'accepted': True, 'qualification': 'Test-only controlled acceptance'}
    monkeypatch.setattr(safety, 'screen', accepted)
    monkeypatch.setattr(laboratory, 'screen', accepted)
    class Mock:
        def __init__(self): self.step = 0
        def choose(self, state):
            self.step += 1
            if self.step in (1,3):
                return {'op':'propose_hypothesis','template':'nominal','knobs':{},'bounds':{},'rationale':'Inspect public evidence'}
            if self.step == 2:
                return {'op':'request_experiment','name':'thrust_step','params':{'duration_s':4.,'phase_s':1.,'amplitude_n':0.}}
            assert len(state['evidence_refs']) == 2
            return {'op':'finalize','diagnosis':{'hypothesis':None,'evidence_refs':state['evidence_refs']},'confidence':'abstain','ambiguity_statement':'Evidence remains insufficient'}
    backend = SafeBackend(seed=1110100, mode='simulation_enforced')
    lab = Laboratory(rows(), backend)
    result = investigate(lab, Mock())
    assert result['confidence']=='abstain' and lab.tests==1
    assert lab.test_time_s==6 and lab.fit_calls==2
    assert 'true_excursion' not in json.dumps(lab.get_fit_report())
    previous = None
    for event in lab.ledger:
        assert event['previous_hash']==previous
        assert digest({k:v for k,v in event.items() if k!='event_hash'})==event['event_hash']
        previous=event['event_hash']


def test_failed_fit_and_inadequate_fit_allow_abstention(monkeypatch):
    import nautilus.laboratory as module
    def fail(*args, **kwargs): raise FloatingPointError('Test numerical failure')
    monkeypatch.setattr(module,'fit_model',fail)
    lab=Laboratory(rows(),SafeBackend())
    result=lab.propose_hypothesis('nominal',{}, {},'test')
    assert result['status']=='OPTIMIZATION_FAILURE' and lab.fit_calls==1
    assert lab.finalize({'hypothesis':None,'evidence_refs':lab.evidence_refs()},'abstain','Fitting failed')['confidence']=='abstain'


def test_no_safe_options_retains_no_execution():
    lab=Laboratory(rows(),SafeBackend(mode='simulation_enforced'))
    trial=Trial('thrust_step',duration_s=4.,phase_s=1.,amplitude_n=0.)
    assert not lab.request_experiment(trial.name,trial.params())['accepted']
    assert lab.tests==0 and lab.test_time_s==0
    assert lab.finalize({'hypothesis':None,'evidence_refs':lab.evidence_refs()},'abstain','No admissible test')['confidence']=='abstain'


def test_inadequate_evidence_is_distinct_from_investigator_stop():
    observations=rows()
    for row in observations: row['observed_y_m']=100.
    lab=Laboratory(observations,SafeBackend())
    lab.propose_hypothesis('nominal',{}, {},'Inspect inconsistent data')
    assert lab.get_fit_report()['numerical_summary']['status']=='MODEL_INADEQUATE'
    assert lab.finalize({'hypothesis':None,'evidence_refs':lab.evidence_refs()},'abstain','Model inadequate or reset assumptions violated')['confidence']=='abstain'
