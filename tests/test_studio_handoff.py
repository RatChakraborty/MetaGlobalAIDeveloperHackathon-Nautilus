import copy

import pytest

from nautilus.studio_handoff import HandoffError, validate_handoff
from nautilus.studio_muse import Session, call
from api.v1.studio import RequestError, dispatch


def _handoff():
    return {
        'schema_version': 'nautilus.studio-handoff.v1',
        'reproducibility': {'run_id': 'run-1', 'source_kind': 'recorded', 'ledger_head': 'h-final', 'events': 4},
        'observations': {'episodes': 1, 'evidence_refs': ['h-obs'], 'max_abs_observed_y_m': 0.4},
        'hypotheses': [{
            'hypothesis': 'thruster_gain_loss', 'converged': True, 'parameters': {'gain': 0.8},
            'weighted_rmse': 0.07, 'identifiability': {'rank': 1, 'condition': 1e8, 'qualification': 'weak'},
            'evidence_refs': ['h-obs'], 'status': 'candidate_hypothesis'}],
        'conclusion': None,
        'limitations': ['Hypotheses are candidate explanations, not proven causes.'],
    }


def test_valid_handoff_is_sanitised_and_kept():
    clean = validate_handoff(_handoff())
    assert clean['hypotheses'][0]['status'] == 'candidate_hypothesis'
    assert clean['observations']['episodes'] == 1


@pytest.mark.parametrize('mutate', [
    lambda h: h.update(hidden_truth={'fault': 'x'}),                      # unexpected top-level key
    lambda h: h['hypotheses'][0].update(true_fault='gain'),              # unexpected hypothesis key
    lambda h: h['hypotheses'][0].update(status='proven'),                 # overclaiming status
    lambda h: h.update(conclusion={'diagnosis': 'x', 'confidence': 'high', 'ambiguity_statement': None,
                                   'evidence_refs': [], 'status': 'proven'}),
    lambda h: h['hypotheses'][0]['parameters'].update(gain=float('nan')),  # non-finite number
    lambda h: h['hypotheses'][0]['parameters'].update(gain='0.8'),        # wrong type
    lambda h: h.update(schema_version='nautilus.other.v1'),               # wrong schema
    lambda h: h['observations'].update(evidence_refs=['x'] * 17),          # over bound
])
def test_rejects_unsafe_or_malformed_handoff(mutate):
    payload = _handoff()
    mutate(payload)
    with pytest.raises(HandoffError):
        validate_handoff(payload)


def test_dispatch_rejects_bad_handoff_with_request_error():
    body = {'action': 'muse', 'handoff': {'schema_version': 'nautilus.studio-handoff.v1', 'extra': 1}}
    with pytest.raises(RequestError):
        dispatch(body)


def test_muse_evidence_tool_returns_handoff_not_hidden_truth():
    session = Session(handoff=validate_handoff(_handoff()))
    evidence = call(session, 'inspect_diagnosis_evidence', {})
    assert evidence['source'] == 'investigation_handoff'
    assert evidence['hidden_truth_exposed'] is False
    assert evidence['handoff']['hypotheses'][0]['status'] == 'candidate_hypothesis'
    assert 'not proven causes' in evidence['uncertainty']


def test_fixed_evidence_is_used_when_no_handoff_is_given():
    evidence = call(Session(), 'inspect_diagnosis_evidence', {})
    assert evidence['hidden_truth_exposed'] is False
    assert evidence.get('source') != 'investigation_handoff'


def test_worst_case_handoff_fits_the_studio_request_limit():
    import json
    payload = _handoff()
    payload['observations']['evidence_refs'] = ['r' * 64] * 16
    payload['hypotheses'] = [copy.deepcopy(payload['hypotheses'][0]) for _ in range(4)]
    for h in payload['hypotheses']:
        h['parameters'] = {f'p{i}': 1.0 for i in range(8)}
        h['evidence_refs'] = ['r' * 64] * 16
    body = json.dumps({'action': 'muse', 'handoff': payload}).encode()
    assert len(body) <= 16384, len(body)
