from copy import deepcopy
from dataclasses import replace
import importlib.util
import inspect
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from nautilus.configuration_evaluation import DevelopmentScenario, evaluate_configuration
from nautilus.controller_context import canonical, fingerprint
from nautilus.host_evaluation import ConfigurationEvaluationHost, validate_post_record, validate_proposal
from nautilus.lab_safety import SafeBackend
from nautilus.laboratory import Laboratory
from nautilus.simulator import Controller, Faults, Mission, simulate
from nautilus.v2_tools import capability_schema


def laboratory():
    lab=Laboratory(simulate(mission=Mission(duration_s=.3)).observations,SafeBackend())
    lab.propose_hypothesis('nominal',{}, {},'Deterministic test investigator; no physical attribution claim.')
    return lab


def scenario():
    return DevelopmentScenario('host-development-test',faults=Faults(current_y=.2),mission=Mission(duration_s=3.,seed=859671))


def response(lab, *, abstain=False, value=3.):
    return {'final_decision':{'diagnosis':{'hypothesis':None if abstain else 'nominal','evidence_refs':lab.evidence_refs()},
            'confidence':'abstain' if abstain else 'tentative','ambiguity_statement':'Deterministic test final response; not a verified cause.'},
            'configuration_proposal':{'parameter':'lookahead_m','value':value,'rationale':'Test shorter lookahead under matched host conditions.',
                                      'evidence_refs':lab.evidence_refs(),'expected_effect':'Possibly change lateral tracking.'}}


def body(result):return json.loads(result.record['events'][0]['body_canonical'])


@pytest.mark.parametrize('parameter,value',[('lookahead_m',3.),('heading_kp',50.),('heading_kd',30.),('cruise_thrust',14.)])
def test_valid_bounded_proposal(parameter,value):
    proposal={'parameter':parameter,'value':value,'rationale':'Unit fixture','evidence_refs':['public']}
    assert validate_proposal(json.dumps(proposal),['public'])==proposal


@pytest.mark.parametrize('change',[{'parameter':'seed'},{'parameter':'max_heading_rad'},{'value':10000},{'value':float('nan')},{'value':float('inf')},{'value':True},{'value':'__import__("os").system("false")'},{'scenario_id':'secret'},{'plant':{}},{'source_patch':'print(1)'},{'safety_mode':'unchecked'},{'evidence_refs':['unknown']}])
def test_rejected_proposal_finalizes_but_never_evaluates(change):
    lab=laboratory();envelope=response(lab);envelope['configuration_proposal'].update(change)
    with patch('nautilus.host_evaluation.evaluate_configuration',side_effect=AssertionError('Must not execute')):
        result=ConfigurationEvaluationHost(scenario(),Controller(),authorized=True).finish(lab,envelope)
    assert lab._closed and body(result)['status']=='rejected_validation'
    assert body(result)['proposal'] is None and body(result)['comparison'] is None
    assert body(result)['budget']['attempted_evaluations']==0
    assert 'secret' not in json.dumps(result.record)


def test_duplicate_keys_and_envelope_scenario_selection_rejected_before_finalization():
    lab=laboratory();host=ConfigurationEvaluationHost(scenario(),Controller(),authorized=True)
    value=response(lab);value['scenario_id']='do-not-disclose'
    with pytest.raises(ValueError):host.finish(lab,value)
    assert not lab._closed
    with pytest.raises(ValueError):validate_proposal('{"parameter":"lookahead_m","parameter":"cruise_thrust","value":3,"rationale":"fixture","evidence_refs":["public"]}',['public'])
    assert not lab._closed


@pytest.mark.parametrize('policy,abstain,reason',[({},False,'not_authorized'),({'authorized':True},True,'abstention'),({'authorized':True,'evaluation_limit':0},False,'budget_exhausted'),({'authorized':True,'simulation_limit_s':1},False,'budget_exhausted'),({'authorized':True,'permitted_parameters':['heading_kp']},False,'parameter_not_permitted')])
def test_explicit_separate_host_policy(policy,abstain,reason):
    lab=laboratory();envelope=response(lab,abstain=abstain)
    with patch('nautilus.host_evaluation.evaluate_configuration',side_effect=AssertionError('Must not execute')):
        result=ConfigurationEvaluationHost(scenario(),Controller(),**policy).finish(lab,envelope)
    assert body(result)['status']=='proposed_not_executed' and body(result)['reason']==reason
    assert body(result)['scenario_id'] is None and body(result)['budget']['attempted_evaluations']==0


def test_completed_host_evaluation_matches_evaluator_and_preserves_finalized_ledger():
    lab=laboratory();envelope=response(lab);prior=deepcopy(lab.ledger);budgets=lab.get_fit_report()['remaining']
    host=ConfigurationEvaluationHost(scenario(),Controller(),authorized=True)
    result=host.finish(lab,envelope);finalized=deepcopy(lab.ledger)
    expected=evaluate_configuration(scenario(),Controller(),{'lookahead_m':3.})
    assert result.evaluation.summary()==expected.summary()==body(result)['comparison']
    assert finalized[:-1]==prior and finalized[-1]['type']=='finalized'
    assert body(result)['previous_hash']==finalized[-1]['event_hash']==result.record['ledger_anchor']
    assert body(result)['status']=='completed_improvement'
    assert lab.get_fit_report()['remaining']==budgets
    assert validate_post_record(result.record,lab.ledger)==result.record
    assert '859671' not in json.dumps(result.record)
    assert 'current_y' not in json.dumps(result.record)
    for name in ('baseline','candidate'):
        assert body(result)['run_references'][name]['run_id']==getattr(expected,name).run_id
    with pytest.raises(ValueError):host.finish(lab,envelope)
    with pytest.raises(ValueError):ConfigurationEvaluationHost(scenario(),Controller(),authorized=True).finish(lab,envelope)
    assert lab.ledger==finalized


def test_no_improvement_is_reported_without_search():
    lab=laboratory();result=ConfigurationEvaluationHost(scenario(),Controller(),authorized=True).finish(lab,response(lab,value=7.))
    assert body(result)['status']=='completed_no_improvement'
    assert body(result)['comparison']['metric_differences']['rms_cross_track_m']==0.
    assert body(result)['budget']['attempted_evaluations']==1


def test_missing_proposal_and_evaluation_failure_have_distinct_outcomes():
    lab=laboratory();r=response(lab);r['configuration_proposal']=None
    result=ConfigurationEvaluationHost(scenario(),Controller(),authorized=True).finish(lab,r)
    assert body(result)['status']=='not_proposed'
    lab=laboratory();r=response(lab);del r['configuration_proposal']
    assert body(ConfigurationEvaluationHost(scenario(),Controller()).finish(lab,r))['status']=='not_proposed'
    lab=laboratory()
    with patch('nautilus.host_evaluation.evaluate_configuration',side_effect=RuntimeError('PRIVATE_VALUE_991987')):
        result=ConfigurationEvaluationHost(scenario(),Controller(),authorized=True).finish(lab,response(lab))
    assert body(result)['status']=='evaluation_failed' and body(result)['comparison'] is None
    assert body(result)['budget']['attempted_evaluations']==1 and body(result)['budget']['actual_simulation_s'] is None
    assert 'PRIVATE_VALUE' not in json.dumps(result.record)


def test_failed_finalization_cannot_evaluate_and_four_tools_unchanged():
    lab=laboratory();request=response(lab);request['final_decision']['diagnosis']['hypothesis']='unfitted'
    schema=deepcopy(capability_schema())
    assert list(inspect.signature(Laboratory.finalize).parameters)==['self','diagnosis','confidence','ambiguity_statement']
    with patch('nautilus.host_evaluation.evaluate_configuration',side_effect=AssertionError('Must not execute')):
        with pytest.raises(ValueError):ConfigurationEvaluationHost(scenario(),Controller(),authorized=True).finish(lab,request)
    assert not lab._closed and len(schema['oneOf'])==4 and capability_schema()==schema
    with pytest.raises(ValueError):lab.call({'op':'evaluate_configuration'})


@pytest.mark.parametrize('tamper',['anchor','hash','metrics','reference','status'])
def test_post_record_linkage_and_measurements_cannot_be_tampered(tamper):
    lab=laboratory();result=ConfigurationEvaluationHost(scenario(),Controller(),authorized=True).finish(lab,response(lab))
    value=deepcopy(result.record)
    if tamper=='anchor':value['ledger_anchor']='0'*64
    elif tamper=='hash':value['events'][0]['hash']='0'*64
    else:
        b=json.loads(value['events'][0]['body_canonical'])
        if tamper=='metrics':b['comparison']['metric_differences']['rms_cross_track_m']=123.
        if tamper=='reference':b['run_references']['candidate']['run_id']='0'*64
        if tamper=='status':b['status']='completed_no_improvement'
        value['events'][0]={'hash':fingerprint(b),'body_canonical':canonical(b)}
    with pytest.raises(ValueError):validate_post_record(value,lab.ledger)


def test_host_export_is_separate_from_investigator_evidence(tmp_path):
    spec=importlib.util.spec_from_file_location('host_export',Path(__file__).parents[1]/'frontend/export_records.py')
    export=importlib.util.module_from_spec(spec);spec.loader.exec_module(export)
    lab=laboratory();result=ConfigurationEvaluationHost(scenario(),Controller(),authorized=True).finish(lab,response(lab))
    source=tmp_path/'final.json';source.write_text(json.dumps({'history':lab.ledger,'private':{'answer':'NEVER'}}))
    original=source.read_bytes();directory=tmp_path/'replay';export.export_host_evaluation(result,source,directory)
    assert source.read_bytes()==original
    public=json.loads((directory/'investigation.json').read_text())
    assert 'rms_cross_track_m' not in json.dumps(public) and 'NEVER' not in json.dumps(public)
    assert public['ledger'][-1]['hash']==result.record['ledger_anchor']
    assert public['recorded_conclusion']['diagnosis']==lab.ledger[-1]['diagnosis']
    post=json.loads((directory/'configuration-evaluation.json').read_text());assert post==result.record
    candidate=json.loads((directory/'candidate.visualization.json').read_text())
    assert candidate['run_id']==body(result)['run_references']['candidate']['run_id']
    assert candidate['samples']==[{k:r[k] for k in ('time_s','x_m','y_m','heading_rad')} for r in result.evaluation.candidate.result.truth]
