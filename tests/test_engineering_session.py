from copy import deepcopy
import json

import pytest

from api.v1.simulations import run_simulation
from api.v1.studio import dispatch
from nautilus.controller_context import fingerprint, canonical
from nautilus.engineering_session import validate_context, handoff_from_context
from nautilus.policy_ir import baseline_policy
from nautilus.policy_source import to_source
from nautilus.studio_muse import Session, ToolError, call
from nautilus_api.jobs import run_investigation
from nautilus_api.schema import scenario


@pytest.fixture(scope='module')
def evidence():
    faults, mission, request = scenario({'scenario': {'current_y': .15}, 'duration_s': 4., 'seed': 74213})
    return run_investigation(faults, mission, request), request


def test_public_context_is_reproducible_and_has_no_generation_answers(evidence):
    result, request = evidence
    value = result['engineering_context']; body = validate_context(value)
    assert validate_context(value) == body
    from nautilus.investigation import verify_ledger
    assert verify_ledger(json.loads(result['public_ledger_canonical']))
    assert body['episodes'][0]['trace_hash'] == fingerprint(result['observations'])
    assert len(body['episodes'][0]['observations']) <= 32
    assert set(body['episodes'][0]['observations'][0]) == {'time_s','observed_y_m','observed_heading_rad','observed_yaw_rate_radps','port_command_n','starboard_command_n'}
    assert not any(key in value['body_canonical'] for key in ['"plant"', '"faults"', '"scenario"', '"seed"', '"truth"'])
    assert handoff_from_context(value)['reproducibility']['run_id'] == body['session_id']
    changed = deepcopy(value); changed['body_canonical'] += ' '
    with pytest.raises(ValueError): validate_context(changed)
    changed = json.loads(value['body_canonical']); changed['episodes'][0]['observations'][0]['x_m'] = 3
    with pytest.raises(ValueError): validate_context({'body_canonical':canonical(changed),'hash':fingerprint(changed)})


def test_full_source_execution_trial_robustness_and_host_gates_share_identity(evidence):
    result, request = evidence
    binding = {'engineering_context': result['engineering_context'], 'scenario_request': request}
    policy = baseline_policy(); source = to_source(policy)
    body = {'source':source, 'name':'acceptance-controller','params':{'integral_ki':6.,'integral_limit':1.5}, **binding}
    validated = dispatch({'action':'validate', **body})
    trial = dispatch({'action':'trial', **body})
    held = dispatch({'action':'robustness', **body})
    assert validated['valid']
    from nautilus.studio import policy_fingerprint
    assert policy_fingerprint(json.loads(trial['policy_canonical']))==trial['fingerprint']
    baseline=dispatch({'action':'baseline'})
    assert policy_fingerprint(json.loads(baseline['policy_canonical']))==baseline['fingerprint']
    assert validated['fingerprint'] == trial['fingerprint'] == held['fingerprint']
    assert trial['session_id'] == held['host_decision']['session_id'] == validate_context(binding['engineering_context'])['session_id']
    assert trial['evidence_hash'] == held['host_decision']['evidence_hash'] == binding['engineering_context']['hash']
    assert any(row['scenario_id']=='investigated_run' for row in trial['rows'])
    assert len(held['rows']) == 3 and held['host_decision']['same_candidate']
    should_recommend = trial['outcome']['label'] == held['outcome']['label'] == 'Recommended'
    assert (held['host_decision']['decision']=='recommend') == should_recommend
    wrong = deepcopy(body); wrong['scenario_request']['seed'] += 1
    with pytest.raises(ValueError, match='reproduce'): dispatch({'action':'trial', **wrong})


def test_mock_engineer_must_inspect_actual_evidence_and_can_cite_its_ids(evidence):
    result, request = evidence
    s = Session(engineering_context=result['engineering_context'], scenario_request=request)
    refs = validate_context(result['engineering_context'])['episodes']
    proposal = dict(candidate_id='bounded',rationale='Test bounded integral compensation under matched simulation.',params={'integral_ki':6.},evidence_refs=[refs[0]['evidence_ref']])
    with pytest.raises(ToolError, match='inspect'): call(s,'propose_controller_revision',proposal)
    public = call(s,'inspect_diagnosis_evidence',{})
    assert public['source']=='investigation_handoff'
    assert 'scenario_request' not in json.dumps(public)
    accepted = call(s,'propose_controller_revision',proposal)
    assert accepted['fingerprint']
    with pytest.raises(ToolError): call(s,'finalize_controller_recommendation',{'decision':'recommend','candidate_id':'bounded','rationale':'Cannot skip execution.'})
    s.robustness['closed'] = {}
    with pytest.raises(ToolError, match='closed'):call(s,'propose_controller_revision',{**proposal,'candidate_id':'after-held-out'})


def test_simulation_also_produces_an_automatic_public_handoff():
    faults,mission,request=scenario({'scenario':{},'duration_s':2.,'seed':74214})
    run=run_simulation(faults,mission,request)
    body=validate_context(run['engineering_context'])
    assert body['actor']=='deterministic_baseline'
    assert body['episodes'][0]['trace_hash']==fingerprint(run['observations'])


def test_fresh_active_investigation_flows_into_mock_engineering_without_manual_files(monkeypatch):
    from nautilus.studio_muse import run_session
    faults,mission,request=scenario({'scenario':{'current_y':-.06},'duration_s':45.,'seed':74221})
    investigation=run_investigation(faults,mission,request)
    context=investigation['engineering_context'];body=validate_context(context)
    assert investigation['investigation']['tests'] > 0
    assert len(body['episodes']) > 1
    assert len({e['trace_hash'] for e in body['episodes']}) == len(body['episodes'])
    assert any(a['experiment'] is not None for a in body['actions'])
    import nautilus.studio as studio
    original=studio._row;executions=[]
    def measured(*args):
        executions.append(args[0].identifier)
        return original(*args)
    monkeypatch.setattr(studio,'_row',measured)
    session=dispatch({'action':'muse','engineering_context':context,'scenario_request':request})
    assert session['mock'] and session['provider_calls']==0
    assert session['session_id']==body['session_id'] and session['evidence_hash']==context['hash']
    assert session['final'] is not None,session['stopped']
    assert not any('error' in step for step in session['transcript'])
    assert any(step['tool']=='execute_controller_trial' for step in session['transcript'])
    cid=session['final']['candidate_id']
    assert session['final']['candidate_fingerprint']==session['candidates'][cid]['fingerprint']
    assert session['final']['actor']=='trusted_host'
    assert len(executions)==8
    assert session['selected_trial']['fingerprint']==session['selected_robustness']['fingerprint']==session['candidates'][cid]['fingerprint']
    assert session['selected_trial']['session_id']==body['session_id']
    assert session['selected_robustness']['host_decision']['same_candidate']
    assert len(body['hypotheses'])==5
    assert len(session['selected_trial']['rows'])==5


def test_unavailable_fit_error_stays_unavailable_in_the_handoff(evidence):
    from nautilus.engineering_session import context_from_result
    result,_=evidence;result=deepcopy(result)
    result['investigation']['outcome']['fits'][0]['wrms']=None
    context=context_from_result(result)
    fits=validate_context(context)['hypotheses']
    assert fits[-1]['weighted_rmse'] is None
