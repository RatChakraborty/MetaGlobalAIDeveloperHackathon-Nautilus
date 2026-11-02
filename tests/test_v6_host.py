import json

import pytest

from nautilus.simulator import Controller
from nautilus.v6 import ControlLabHost, build_suite, validate_artifact
from nautilus.v6.host import SCHEMA

REF = 'a' * 64


def suite(identifier='current_positive'):
    return build_suite(duration_s=20., cable_length_m=12.,
                       specs=((identifier, {'current_y': .45}, {}, 9102),))


def lab(**overrides):
    options = {'investigation_id': 'inv-1', 'evidence_refs': [REF], 'authorized': True,
               'suite': suite(), 'evaluation_limit': 1, 'simulation_limit_s': 600.}
    options.update(overrides)
    return ControlLabHost(Controller(), **options)


def proposal(**overrides):
    value = {'parameter': 'lookahead_m', 'value': 3., 'rationale': 'Cross-track excursions under lateral current.',
             'evidence_refs': [REF], 'expected_effect': 'Lower mean cross-track RMS.'}
    value.update(overrides)
    return value


def test_context_withholds_truth_seeds_and_private_conditions():
    host = lab(rubric={'status': 'insufficient_diagnosis'})
    context = host.context()
    assert context['schema_version'] == SCHEMA
    assert context['phase'] == 'post-finalization control improvement'
    serialized = json.dumps(context)
    for private in ('current_y', 'port_efficiency', 'heading_bias_rad', '"seed"', 'actuator_tau_s'):
        assert private not in serialized
    assert context['policy']['parameters']['lookahead_m']['value'] == 7.
    assert context['diagnosis_rubric'] == {'status': 'insufficient_diagnosis'}
    assert context['tools'] == ['search_candidates', 'propose_change', 'evaluate_change', 'recommend', 'review_patch']
    assert context['patch_lab']['available'] is False
    assert context['patch_lab']['execution'] == 'unavailable'


def test_model_cannot_inject_metrics_or_unpermitted_parameters():
    host = lab(permitted=('heading_kp',))
    with pytest.raises(ValueError):
        host.propose(proposal())  # lookahead is not permitted in this phase
    allowed = lab()
    with pytest.raises(ValueError):
        allowed.propose({**proposal(), 'metrics': {'rms_cross_track_m': 0.01}})
    with pytest.raises(ValueError):
        allowed.propose(proposal(evidence_refs=['f' * 64]))
    record = allowed.propose(proposal())
    assert record['status'] == 'proposed_not_evaluated'
    assert record['proposal']['value'] == 3.
    for _ in range(3):
        allowed.propose(proposal())
    with pytest.raises(ValueError, match='Proposal limit'):
        allowed.propose(proposal())


def test_host_alone_runs_evaluations_and_enforces_budgets():
    host = lab()
    host.propose(proposal())
    unauthorized = lab(authorized=False)
    unauthorized.propose(proposal())
    with pytest.raises(ValueError, match='not authorized'):
        unauthorized.evaluate(0)
    with pytest.raises(ValueError, match='Unknown proposal index'):
        host.evaluate(5)
    result = host.evaluate(0)
    assert result['budget']['simulations'] == 2 and result['budget']['equal_per_case_budget'] is True
    assert result['cases'][0]['matched'] is True
    assert host.budget['evaluations'] == 1 and host.budget['simulation_used_s'] > 0
    with pytest.raises(ValueError, match='Evaluation budget'):
        host.evaluate(0)
    empty = lab(evaluation_limit=0)
    empty.propose(proposal())
    with pytest.raises(ValueError, match='Evaluation budget'):
        empty.evaluate(0)


def test_recommendation_requires_a_completed_evaluation():
    host = lab()
    with pytest.raises(ValueError):
        host.recommend('accept', 'looks better')
    host.propose(proposal())
    host.evaluate(0)
    with pytest.raises(ValueError):
        host.recommend('approved', 'not an allowed recommendation')
    with pytest.raises(ValueError):
        host.recommend('accept', '')
    recommendation = host.recommend('accept', 'The measured suite improves tracking at equal conditions.')
    assert recommendation == {'recommendation': 'accept',
                              'rationale': 'The measured suite improves tracking at equal conditions.'}


def test_artifact_records_host_authority_and_required_human_review():
    host = lab()
    host.propose(proposal())
    host.evaluate(0)
    host.recommend('accept', 'Measured improvement under matched conditions.')
    artifact = host.finish()
    validate_artifact(artifact)
    assert artifact['scope'].startswith('Engineering recommendation from matched offline simulation')
    assert artifact['human_review'] == {'status': 'required', 'performed': False,
                                        'checklist': artifact['human_review']['checklist']}
    assert artifact['recommendation']['decision'] == artifact['robustness']['decision']
    if artifact['robustness']['decision'] == 'accept':
        assert artifact['approved_differences'] == {'lookahead_m': {'baseline': 7., 'candidate': 3., 'unit': 'm'}}
        assert artifact['recommendation']['agreement'] is True
    assert '"seed"' not in json.dumps(artifact) and 'current_y' not in json.dumps(artifact)
    with pytest.raises(ValueError, match='already finalized'):
        host.finish()
    with pytest.raises(ValueError):
        host.evaluate(0)


def test_disagreement_is_recorded_but_the_host_rule_governs():
    host = lab()
    host.propose(proposal(value=11.))  # a longer lookahead regresses under lateral current
    result = host.evaluate(0)
    host.recommend('accept', 'The model prefers this candidate despite the measured regression.')
    artifact = host.finish()
    assert result['decision'] == 'reject'
    assert artifact['recommendation']['decision'] == 'reject'
    assert artifact['recommendation']['agreement'] is False
    assert artifact['approved_differences'] == {}
    assert artifact['proposal'] is None
    assert any('rejected by the predeclared acceptance rule' in risk for risk in artifact['unresolved_risks'])


def test_search_and_patch_lab_are_host_controlled():
    host = lab()
    search = host.search()
    assert search['best'] is not None and search['screening_cases'] == ['nominal', 'current_positive']
    assert host.context()['screening']['best'] == search['best']
    assert host.review_patch('--- a/nautilus/v6/controller_variant.py\n+++ b/nautilus/v6/controller_variant.py\n')['status'] == 'unavailable'


def test_finish_uses_the_last_evaluated_proposal_not_the_last_proposed():
    host = lab(evaluation_limit=2)
    host.propose(proposal())            # lookahead 3: improves under lateral current
    host.propose(proposal(value=11.))   # lookahead 11: regresses under lateral current
    host.evaluate(1)                    # evaluate the regressing candidate first
    host.evaluate(0)                    # then the improving one
    assert [item['proposal_index'] for item in host.results] == [1, 0]
    assert host.budget['evaluations'] == 2
    artifact = host.finish()
    assert artifact['approved_differences'] == {'lookahead_m': {'baseline': 7., 'candidate': 3., 'unit': 'm'}}
    assert artifact['proposal']['value'] == 3.
    assert artifact['recommendation']['decision'] == 'accept'
