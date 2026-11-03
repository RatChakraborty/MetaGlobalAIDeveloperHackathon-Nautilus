import pytest

from nautilus.controller_context import PARAMETERS
from nautilus.simulator import Controller
from nautilus.v6 import build_policy
from nautilus.v6.proposal import GRID, MAX_CANDIDATES, SCREENING, coordinate_search, screen, validate_change

REF = 'b' * 64
PROPOSAL = {'parameter': 'lookahead_m', 'value': 3.0, 'rationale': 'Cross-track excursions under lateral current.',
            'evidence_refs': [REF], 'expected_effect': 'Lower mean cross-track RMS.'}


def proposal(**overrides):
    return {**PROPOSAL, **overrides}


def test_proposal_schema_is_closed_and_bounded():
    policy = build_policy(Controller())
    assert validate_change(PROPOSAL, [REF], policy) == PROPOSAL
    assert validate_change(proposal(value=3), [REF], policy)['value'] == 3.0
    for bad in ({**PROPOSAL, 'metrics': {'rms': 0.1}}, {**PROPOSAL, 'verified': True},
                {k: v for k, v in PROPOSAL.items() if k != 'expected_effect'},
                proposal(parameter='max_heading_rad'), proposal(value=1.), proposal(value=21.),
                proposal(value=float('nan')), proposal(value=True), proposal(value='3'),
                proposal(evidence_refs=[]), proposal(evidence_refs=['c' * 64]),
                proposal(evidence_refs=[REF, REF]), proposal(rationale=''), {'parameter': 'lookahead_m'}):
        with pytest.raises(ValueError):
            validate_change(bad, [REF], policy)


def test_grid_values_stay_inside_approved_bounds():
    for name, values in GRID.items():
        unit, low, high = PARAMETERS[name]
        assert values, name
        assert all(low <= value <= high for value in values)
    assert set(GRID) == set(PARAMETERS) - {'max_heading_rad'}


def test_screening_uses_only_declared_development_cases():
    assert [case.identifier for case in SCREENING] == ['nominal', 'current_positive']
    outcome = screen(Controller(), grid={'lookahead_m': (3., 11.)}, limit=2)
    assert outcome['screening_cases'] == ['nominal', 'current_positive']
    assert outcome['evaluations'] == 2 and outcome['budget']['candidates'] == 2
    assert len(outcome['attempted']) == 2
    assert {item['changes']['lookahead_m'] for item in outcome['attempted']} == {3., 11.}
    # A shorter lookahead improves tracking here; a longer one does not.
    improved = next(item for item in outcome['attempted'] if item['changes']['lookahead_m'] == 3.)
    worsened = next(item for item in outcome['attempted'] if item['changes']['lookahead_m'] == 11.)
    assert improved['mean_rms_difference_m'] < 0 and improved['admissible']
    assert worsened['mean_rms_difference_m'] > 0 and not worsened['admissible']
    assert outcome['best'] == {'lookahead_m': 3.}


def test_search_is_bounded_and_retains_every_attempt():
    outcome = coordinate_search(Controller(), grid={'lookahead_m': (3.,), 'heading_kp': (48.,)}, limit=3)
    assert outcome['budget']['candidates'] <= 3
    assert len(outcome['singles']) == 2
    assert outcome['budget']['limit'] == 3
    assert outcome['best'] is not None
    assert all('admissible' in item for item in outcome['attempted'])
    assert any('not an optimizer' in text for text in outcome['limitations'])
    with pytest.raises(ValueError):
        screen(Controller(), grid={'max_heading_rad': (.5,)}, limit=2)
    with pytest.raises(ValueError):
        screen(Controller(), grid={'lookahead_m': (99.,)}, limit=2)
    with pytest.raises(ValueError):
        screen(Controller(), limit=MAX_CANDIDATES + 1)


def test_no_admissible_candidate_leaves_no_recommendation():
    outcome = coordinate_search(Controller(), grid={'lookahead_m': (11., 9.)}, limit=2)
    assert all(not item['admissible'] for item in outcome['attempted'])
    assert outcome['best'] is None
    assert outcome['combinations'] == []
