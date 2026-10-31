from dataclasses import asdict, replace
import ast
import inspect
import json
from types import SimpleNamespace

import numpy as np
import pytest

import evaluate_active as evaluation
import nautilus.investigation as investigator
from nautilus.diagnosis import FitConfig, fit_evidence, fit_hypothesis
from nautilus.experiments import (EXPERIMENT_LIBRARY, ExperimentRequest,
                                   HiddenExperimentBackend, forecast)
from nautilus.investigation import investigate, choose, verify_ledger
from nautilus.protocol import PassiveProtocol, classify, digest, passive, diagnose_episodes
from nautilus.simulator import (Faults, HIDDEN_PLANT, Controller, Mission,
                                OBSERVATION_FIELDS, PlantConfig, simulate)


def fake(name, score, rms=1., converged=True):
    return SimpleNamespace(hypothesis=name, penalized_score=score,
                           weighted_rmse=rms, converged=converged)


@pytest.mark.parametrize("kind, fits", [
    ("identified", [fake('nominal',0),fake('lateral_current',7)]),
    ("ambiguous", [fake('nominal',0),fake('lateral_current',6)]),
    ("model_inadequate", [fake('nominal',0,3),fake('lateral_current',1,3)]),
    ("optimization_failure", [fake('nominal',0),fake('lateral_current',1,converged=False)]),
    ("optimization_failure", [fake('nominal',0)]),
    ("optimization_failure", [fake('nominal',0),fake('lateral_current',float('nan'))]),
])
def test_frozen_outcomes_do_not_pool_failure_with_ambiguity(kind,fits):
    p=PassiveProtocol(hypotheses=('nominal','lateral_current'))
    outcome=classify(fits,p)
    assert outcome.kind==kind
    assert (outcome.selected is not None)==(kind=='identified')


def test_inadequate_runner_is_not_competitive():
    p=PassiveProtocol(hypotheses=('nominal','lateral_current'))
    assert classify([fake('nominal',100),fake('lateral_current',99,3)],p).kind=='identified'


def test_configuration_and_source_freeze_are_tamper_evident():
    p=PassiveProtocol()
    assert p.fingerprint==PassiveProtocol().fingerprint
    assert p.fingerprint!=replace(p,gap=7).fingerprint
    manifest=evaluation.freeze()
    assert evaluation.validate_manifest(manifest)
    manifest['protocols']['primary']['gap']=7
    with pytest.raises(ValueError,match='modified'):
        evaluation.validate_manifest(manifest)
    manifest=evaluation.freeze()
    manifest['source_files']['nautilus/diagnosis.py']='wrong'
    manifest['fingerprint']=digest({k:v for k,v in manifest.items() if k!='fingerprint'})
    with pytest.raises(ValueError,match='Source differs'):
        evaluation.validate_manifest(manifest)


def test_pool_is_fixed_and_generation_deterministic_without_sampling_heldout():
    plans=evaluation.plans()
    assert len(plans)==160
    assert len({p['seed'] for p in plans})==160
    assert all(p['seed']>=200000 for p in plans)
    for label in evaluation.PRIMARY_LABELS:
        a,pa=evaluation.candidate(20002,label,'development-fixture')
        b,pb=evaluation.candidate(20002,label,'development-fixture')
        assert asdict(a)==asdict(b) and pa==pb
    assert evaluation.oracle_family(evaluation.candidate(20002,'controller','dev')[0]) is None
    assert evaluation.oracle_family(evaluation.candidate(20002,'current_bias','dev')[0]) is None


@pytest.mark.parametrize('thrust,duration',[(1,10),(26,10),(6,1),(6,31),(float('nan'),10)])
def test_experiment_bounds(thrust,duration):
    with pytest.raises(ValueError):ExperimentRequest(thrust,duration)


def test_execution_returns_only_public_new_observations_and_enforces_budget():
    backend=HiddenExperimentBackend(faults=Faults(),controller=Controller(),plant=HIDDEN_PLANT,seed=20010)
    one=backend.execute(EXPERIMENT_LIBRARY[0]);two=backend.execute(EXPERIMENT_LIBRARY[1])
    assert all(set(r)==set(OBSERVATION_FIELDS) for r in one+two)
    assert one[0]['time_s']==two[0]['time_s']==0
    assert digest(one)!=digest(two)
    assert one[0]['port_command_n']!=two[0]['port_command_n']
    with pytest.raises(ValueError):backend.execute(EXPERIMENT_LIBRARY[0])
    with pytest.raises(ValueError):backend.execute({'faults':{'heading_bias_rad':0}})


def test_shared_fit_does_not_double_count_complexity_or_join_reset_states():
    rows=simulate(faults=Faults(heading_bias_rad=.3),mission=Mission(duration_s=.5)).observations
    config=FitConfig(method='observer',starts=1)
    a=fit_hypothesis(rows,'heading_bias',config=config)
    b=fit_evidence([rows,rows],'heading_bias',config=config)
    assert b.parameters['heading_bias_rad']==pytest.approx(a.parameters['heading_bias_rad'],abs=1e-7)
    assert b.weighted_sse==pytest.approx(2*a.weighted_sse,rel=1e-7)
    assert b.penalized_score==pytest.approx(b.weighted_sse+np.log(6*len(rows)))
    assert b.episode_lengths==[len(rows),len(rows)]
    with pytest.raises(ValueError):fit_evidence([],'heading_bias')


def test_public_orchestration_does_not_import_or_read_oracle_state():
    tree=ast.parse(inspect.getsource(investigator))
    names={a.name for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) for a in n.names}
    assert not names & {'Faults','Scenario','simulate','HIDDEN_PLANT'}
    assert not {n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)} & {'truth','_faults','_plant'}


def test_new_evidence_resolves_short_log_and_revises_initial_favorite():
    p=PassiveProtocol(duration_s=.1,starts=1)
    rows=simulate(faults=Faults(current_y=.45),plant=HIDDEN_PLANT,
                  mission=Mission(duration_s=.1,sensor_y_std_m=0,
                                  sensor_heading_std_rad=0,sensor_yaw_rate_std_radps=0)).observations
    initial=passive(rows,p)
    assert initial.kind=='ambiguous' and initial.competitive[0]=='nominal'
    factory=lambda:HiddenExperimentBackend(faults=Faults(current_y=.45),controller=Controller(),
                                           plant=HIDDEN_PLANT,seed=23000)
    a=investigate(rows,p,factory().execute,initial_outcome=initial)
    b=investigate(rows,p,factory().execute,initial_outcome=initial)
    assert a['decision']=='lateral_current'
    assert a['tests'] in (1,2)
    assert a==b
    assert verify_ledger(a['ledger'])
    assert any(e['type']=='experiment_observed' for e in a['ledger'])
    for event in a['ledger']:
        if event['type']=='experiment_observed':
            assert len(event['observations'])>len(rows)
            assert event['diagnosis']['fits'][0]['episode_lengths'][0] >= len(rows)
    a['ledger'][0]['observations'][0]['observed_y_m']+=1
    assert not verify_ledger(a['ledger'])


def test_finite_experiments_can_leave_competing_models_ambiguous():
    p=PassiveProtocol(duration_s=.1,starts=1,
                      hypotheses=('port_degradation','starboard_degradation'))
    rows=simulate(mission=Mission(duration_s=.1,sensor_y_std_m=0,
                                  sensor_heading_std_rad=0,sensor_yaw_rate_std_radps=0)).observations
    initial=passive(rows,p)
    assert initial.kind=='ambiguous'
    backend=HiddenExperimentBackend(faults=Faults(),controller=Controller(),
                                     plant=PlantConfig(),seed=23001)
    result=investigate(rows,p,backend.execute,library=(ExperimentRequest(6,2),),
                       budget=1,initial_outcome=initial)
    assert result['outcome']['kind']=='ambiguous'
    assert result['decision'] is None and result['tests']==1


def test_constraints_or_execution_errors_never_become_identifications():
    p=PassiveProtocol(duration_s=.1,starts=1)
    rows=simulate(mission=Mission(duration_s=.1)).observations
    initial=passive(rows,p)
    def error(_):raise ValueError('Service rejected request')
    result=investigate(rows,p,error,initial_outcome=initial)
    assert result['decision'] is None
    assert result['error']
    with pytest.raises(ValueError):investigate(rows,p,error,time_budget_s=float('nan'))


def test_oracle_outputs_must_be_external_and_append_only(tmp_path):
    with pytest.raises(ValueError):evaluation.private_write(evaluation.ROOT/'private.json',{})
    output=tmp_path/'run.json'
    evaluation.private_write(output,{'saved':True})
    with pytest.raises(FileExistsError):evaluation.private_write(output,{})
    assert json.loads(output.read_text())=={'saved':True}


def test_full_pool_accounting_does_not_hide_confident_errors():
    records=[{'operational':'mission_failure','supported':True,'eligible_ambiguity':False,
              'passive':{'kind':'identified'},'correct_identification':value,'active':None}
             for value in (True,False)]
    counts=evaluation.accounting(records)
    assert counts['generated']==counts['operational_failures']==2
    assert counts['identified_correctly']==counts['confidently_wrong']==1
    assert counts['eligible_ambiguous_failures']==0
    assert counts['ambiguity_rate_supported_failures']==0
