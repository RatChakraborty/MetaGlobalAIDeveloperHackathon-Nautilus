from dataclasses import replace
import json
import numpy as np
import pytest
from nautilus.lab_safety import SafeBackend, guarded_trial
from nautilus.laboratory import Laboratory
from nautilus.v2_experiments import Trial
from nautilus.simulator import simulate, Mission, Faults, PlantConfig, Controller, OBSERVATION_FIELDS


def initial(): return simulate(mission=Mission(duration_s=.3,seed=1130000)).observations


def test_risky_trial_executes_and_records_advice():
    trial=Trial('thrust_step',duration_s=4.,phase_s=1.,amplitude_n=0.)
    backend=SafeBackend(faults=Faults(current_y=3.),seed=1130001)
    lab=Laboratory(initial(),backend)
    result=lab.request_experiment(trial.name,trial.params())
    assert result['accepted'] and result['safety']['would_reject_enforced']
    assert result['safety']['warnings'] and result['safety']['mode']=='simulation_advisory'
    assert result['execution']['observed_excursion'] and not result['execution']['guard_intervened']
    assert result['execution']['stop_reason']=='duration_complete'
    assert result['observations'][-1]['time_s']==4.
    assert backend.private_results[0]['true_excursion']
    assert 'truth' not in result and 'private_results' not in json.dumps(lab.get_fit_report())
    assert lab.tests==1 and lab.test_time_s==4.
    assert any(e['type']=='safety' and e['screen']['warnings'] for e in lab.ledger)
    result2=SafeBackend(mode='simulation_enforced').execute(trial)
    assert not result2['accepted']


def test_monitoring_does_not_modify_waveform_or_trajectory():
    trial=Trial('differential_step',duration_s=4.,phase_s=1.,cruise_thrust_n=0.,differential_n=4.)
    faults=Faults(current_y=1.);plant=PlantConfig(actuator_tau_s=.6)
    obs,meta,_=guarded_trial(trial,faults,plant,Controller(),1130010,mode='simulation_advisory')
    reference=simulate(faults=faults,plant=plant,controller=replace(Controller(),cruise_thrust=0.),
                       mission=Mission(duration_s=4.,seed=1130010),
                       experiment=replace(trial.experiment(),max_abs_observed_y_m=None)).observations
    assert len(obs)==len(reference)
    for a,b in zip(obs,reference):
        np.testing.assert_allclose([a[k] for k in OBSERVATION_FIELDS],[b[k] for k in OBSERVATION_FIELDS],atol=1e-12,rtol=0)
    assert meta['would_guard_trigger_s'] is not None and not meta['guard_intervened']
    assert obs[-1]['starboard_command_n']==4.


@pytest.mark.parametrize('mode',['simulation_advisory','simulation_enforced'])
def test_validation_and_mode_are_environment_owned(mode):
    lab=Laboratory(initial(),SafeBackend(mode=mode),experiment_budget=0)
    with pytest.raises(ValueError):lab.request_experiment('thrust_step',{'amplitude_n':float('nan')})
    with pytest.raises(ValueError):lab.request_experiment('thrust_step',{'amplitude_n':100.})
    with pytest.raises(ValueError):lab.call({'op':'request_experiment','name':'thrust_step','params':{},'mode':'simulation_advisory'})
    with pytest.raises(ValueError):lab.request_experiment('thrust_step',{})
    assert lab.get_fit_report()['safety_constraints']['mode']==mode
    with pytest.raises(AttributeError):lab._backend.mode='other'
    with pytest.raises(ValueError):SafeBackend(mode='other')
    with pytest.raises(ValueError):SafeBackend(plant=PlantConfig(actuator_tau_s=-1),mode=mode)
