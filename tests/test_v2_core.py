from dataclasses import asdict,replace
from types import SimpleNamespace
import json

import numpy as np
import pytest

from nautilus.simulator import (Faults,PlantConfig,Controller,Vehicle,Mission,Experiment,
                                simulate,effective_vehicle,HIDDEN_PLANT,OBSERVATION_FIELDS)
from nautilus.v2_models import REGISTRY,EXTENSIONS,configs,fit_model,validate_proposal
from nautilus.v2_experiments import Trial,LIBRARY,PrivateBackend,forward
from nautilus.v2_tools import InvestigationSession,parse_json


def episode(**kwargs):
    return {'observations':simulate(mission=Mission(duration_s=2),**kwargs).observations,
            'experiment':kwargs.get('experiment',Experiment())}


@pytest.mark.parametrize('name',EXTENSIONS)
def test_registry_physics_has_valid_nominal_and_rejects_invalid_ranges(name):
    spec=REGISTRY[name]
    faults,plant,controller=configs(name,spec.nominal)
    assert faults==Faults() and plant==PlantConfig() and controller==Controller()
    with pytest.raises(ValueError):configs(name,spec.bounds[1]+1)
    with pytest.raises(ValueError):validate_proposal(name,{'hidden_parameter':1},{})


def test_uniform_and_axis_drag_use_both_linear_and_quadratic_without_double_scaling():
    v=Vehicle();p=PlantConfig(drag_scale=1.03,drag_surge_scale=2,uniform_drag_scale=1.5)
    out=effective_vehicle(v,p)
    assert out.damping_surge==pytest.approx(v.damping_surge*1.03*3)
    assert out.quadratic_surge==v.quadratic_surge*3
    assert out.quadratic_sway==v.quadratic_sway*1.5
    f,_,_=configs('common_thrust_scale',.6)
    assert f.port_efficiency==f.starboard_efficiency==.6


@pytest.mark.parametrize('trial',LIBRARY)
def test_waveforms_are_bounded_and_reproducible(trial):
    a=simulate(mission=Mission(duration_s=trial.duration_s),experiment=trial.experiment())
    b=simulate(mission=Mission(duration_s=trial.duration_s),experiment=trial.experiment())
    assert a.observations==b.observations
    assert all(set(r)==set(OBSERVATION_FIELDS) for r in a.observations)
    assert max(abs(r[c]) for r in a.observations for c in ('port_command_n','starboard_command_n'))<=45


def test_zero_mean_differential_and_coast_down_are_actually_implemented():
    trial=Trial('differential_step',cruise_thrust_n=0,differential_n=3)
    rows=simulate(mission=Mission(duration_s=12),experiment=trial.experiment()).observations
    for r in rows:
        assert r['port_command_n']+r['starboard_command_n']==0
        if r['time_s']>=trial.phase_s:assert r['starboard_command_n']==3
    coast=Trial('coast_down',phase_s=5)
    rows=simulate(mission=Mission(duration_s=12),experiment=coast.experiment()).observations
    assert all(r['port_command_n']==r['starboard_command_n']==0 for r in rows if r['time_s']>=5)


def test_straight_noiseless_coast_cannot_observe_hidden_speed_difference():
    trial=Trial('coast_down',differential_n=0)
    predictions=[]
    for name,value in [('common_thrust_scale',.6),('uniform_drag_scale',1/.6)]:
        p=REGISTRY[name].parameter
        predictions.append(forward(SimpleNamespace(hypothesis=name,parameters={p:value}),trial))
    for rows in predictions:
        assert all(r['observed_y_m']==r['observed_heading_rad']==r['observed_yaw_rate_radps']==0 for r in rows)


def test_requested_command_telemetry_identifies_controller_gain():
    control=replace(Controller(),heading_kp=12)
    ep=episode(controller=control)
    fit=fit_model([ep],'heading_controller_gain',starts=1)
    nominal=fit_model([ep],'nominal')
    assert fit.converged
    assert fit.parameters['heading_kp']==pytest.approx(12,abs=1e-5)
    assert fit.command_wrms<1e-6 and nominal.command_wrms>2


def test_registry_score_counts_shared_parameters_once_and_keeps_adequacy_channels_separate():
    ep=episode()
    a=fit_model([ep],'actuator_lag',starts=1)
    b=fit_model([ep,ep],'actuator_lag',starts=1)
    assert b.penalized_score-b.weighted_sse==pytest.approx(np.log(5*2*len(ep['observations'])))
    assert b.weighted_rmse==max(b.physical_wrms,b.command_wrms)
    assert b.optimization_attempts==1
    assert set(asdict(b))>={'parameters','status','warnings','sensitivity_scaled_norm'}


@pytest.mark.parametrize('payload',[
    {'op':'exec','code':'print(1)'},
    {'op':'get_fit_report','hidden':True},
    {'op':'propose_hypothesis','template':'__import__','knobs':{},'bounds':{},'rationale':''},
    {'op':'request_experiment','name':'coast_down','params':{'plant':{'drag_scale':2}}},
    '{"op":"get_fit_report","op":"finalize"}',
    '{"op":"get_fit_report","value":NaN}',
])
def test_json_capabilities_reject_unknown_code_and_nonfinite_inputs(payload):
    session=InvestigationSession(episode()['observations'],lambda _:None)
    with pytest.raises(ValueError):session.call(payload)
    assert session.fit_calls==session.tests==0
    assert session.ledger[-1]['type']=='rejected'


def test_fit_budget_failure_counts_and_stale_evidence_cannot_finalize():
    ep=episode()
    backend=PrivateBackend(faults=Faults(),plant=HIDDEN_PLANT,controller=Controller(),seed=605000)
    s=InvestigationSession(ep['observations'],backend.execute,fit_budget=1,optimization_budget=2)
    s.propose_hypothesis('nominal',{}, {},'check')
    with pytest.raises(ValueError):s.propose_hypothesis('actuator_lag',{}, {},'check')
    assert s.fit_calls==1
    result=s.request_experiment('differential_step',{'duration_s':4.,'phase_s':1.,'cruise_thrust_n':0.})
    assert result['fit_reports_stale']
    assert not s.get_fit_report()['fits']
    with pytest.raises(ValueError):s.finalize({'hypothesis':'nominal','evidence_refs':s.evidence_refs()},'supported','limits')
    with pytest.raises(ValueError):s.finalize({'hypothesis':None,'evidence_refs':['forged']},'abstain','limits')
    with pytest.raises(ValueError):s.finalize({'hypothesis':None,'evidence_refs':s.evidence_refs()},.95,'limits')
    assert s.finalize({'hypothesis':None,'evidence_refs':s.evidence_refs()},'abstain','Need more measurements')['confidence']=='abstain'


def test_missing_channels_are_rejected_not_imputed():
    ep=episode();del ep['observations'][0]['port_command_n']
    with pytest.raises(ValueError,match='public'):fit_model([ep],'actuator_lag')


def test_bounds_and_dynamic_objects_rejected():
    with pytest.raises(ValueError):validate_proposal('actuator_lag',{}, {'actuator_tau_s':[-1,2]})
    with pytest.raises(ValueError):validate_proposal('actuator_lag',{'actuator_tau_s':True},{})
    with pytest.raises(TypeError):parse_json({'op':'get_fit_report','fn':lambda:None})
    with pytest.raises(ValueError):Trial('differential_step',differential_n=7)


def test_comparison_menu_cannot_be_expanded_by_json_caller():
    s=InvestigationSession(episode()['observations'],lambda _:None,allowed_trials=LIBRARY)
    with pytest.raises(ValueError,match='protocol menu'):
        s.call({'op':'request_experiment','name':'differential_step',
                'params':{'duration_s':4.,'phase_s':1.}})
    assert s.tests==0
    assert s.get_fit_report()['remaining']['experiments']==3
