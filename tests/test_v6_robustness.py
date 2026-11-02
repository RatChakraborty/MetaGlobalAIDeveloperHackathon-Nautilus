import pytest

from nautilus.simulator import Controller
from nautilus.v6 import evaluate_case
from nautilus.v6.robustness import (ACCEPTANCE, GATES, build_suite, decide, evaluate_suite,
                                    suite_fingerprint, validate_robustness)


def metrics(rms=.5, worst=1.0, outside=.1, saturation=.1, success=True, effort=100., finite=True):
    return {'rms_cross_track_m': rms, 'max_abs_cross_track_m': worst, 'fraction_outside_corridor': outside,
            'command_saturation_fraction': saturation, 'mission_success': success,
            'effort_proxy_n_s': effort, 'finite_samples': finite}


def row(identifier='nominal', baseline=None, candidate=None):
    return {'scenario_id': identifier, 'baseline': baseline or metrics(), 'candidate': candidate or metrics(rms=.3)}


def test_suite_is_fixed_and_matched():
    suite = build_suite(duration_s=20., cable_length_m=12.)
    assert [case.identifier for case in suite] == ['nominal', 'current_positive', 'current_negative',
                                                  'thruster_degradation', 'heading_bias',
                                                  'compound_current_bias_degradation', 'model_mismatch']
    assert len({case.mission.seed for case in suite}) == len(suite)
    assert len({case.identifier for case in suite}) == len(suite)
    assert suite[1].faults.current_y == .45 and suite[2].faults.current_y == -.45
    assert suite[3].faults.port_efficiency == .45
    assert suite[6].plant.actuator_tau_s == 1.2 and suite[6].plant.thrust_deadzone_n == 4.
    assert all(case.purpose == 'development-only' for case in suite)
    assert suite_fingerprint(suite) == suite_fingerprint(build_suite(duration_s=20., cable_length_m=12.))
    assert suite_fingerprint(suite) != suite_fingerprint(build_suite(duration_s=21., cable_length_m=12.))
    with pytest.raises(ValueError):
        build_suite(duration_s=0)


def test_rule_accepts_a_genuine_improvement():
    rows = [row('nominal', metrics(rms=.4), metrics(rms=.2)), row('current_positive', metrics(rms=.8, worst=1.4), metrics(rms=.3, worst=1.0))]
    outcome = decide(rows)
    assert outcome['decision'] == 'accept' and outcome['reasons'] == []
    assert [gate['id'] for gate in outcome['gates']] == [gate[0] for gate in GATES]
    assert all(gate['passed'] for gate in outcome['gates'])
    assert outcome['aggregate']['mean_rms_cross_track_m']['difference'] == pytest.approx(-.35)


def test_rule_rejects_average_improvement_with_worse_worst_case():
    # The exact failure mode the specification forbids: mean improves, worst-case corridor grows.
    rows = [row('nominal', metrics(rms=1.0, worst=1.0), metrics(rms=.05, worst=1.0)),
            row('current_positive', metrics(rms=1.0, worst=1.6), metrics(rms=.9, worst=2.6))]
    outcome = decide(rows)
    assert outcome['aggregate']['mean_rms_cross_track_m']['difference'] < 0
    assert outcome['decision'] == 'reject'
    assert 'no_worst_case_cross_track_regression' in outcome['reasons']
    assert 'no_scenario_rms_regression' not in outcome['reasons']


@pytest.mark.parametrize('mutated,gate', [
    ({'mission_success': False}, 'no_completion_regression'),
    ({'command_saturation_fraction': .5}, 'no_saturation_regression'),
    ({'effort_proxy_n_s': 400.}, 'no_effort_blowup'),
    ({'rms_cross_track_m': .9}, 'no_scenario_rms_regression'),
    ({'fraction_outside_corridor': .9}, 'no_worst_case_excursion_regression'),
])
def test_each_declared_gate_can_reject(mutated, gate):
    improved = metrics(rms=.2)
    weakened = {**improved, **mutated}
    outcome = decide([row('nominal', metrics(), improved), row('current_positive', metrics(), weakened)])
    assert outcome['decision'] == 'reject' and gate in outcome['reasons']


def test_no_measured_cases_or_failures_block_acceptance():
    assert decide([])['decision'] == 'reject'
    assert decide([])['reasons'] == ['no_measured_cases']
    outcome = decide([row()], failures=[{'scenario_id': 'model_mismatch', 'error': 'FloatingPointError'}])
    assert outcome['decision'] == 'reject' and 'finite_runs' in outcome['reasons']
    nonfinite = decide([row(candidate=metrics(finite=False))])
    assert nonfinite['decision'] == 'reject' and 'finite_runs' in nonfinite['reasons']
    with pytest.raises(ValueError):
        decide([{'scenario_id': 'x', 'baseline': {}, 'candidate': {}}])
    with pytest.raises(ValueError):
        decide([row()], acceptance={**ACCEPTANCE, 'extra': 1})


def test_suite_evaluation_is_matched_and_budgeted():
    suite = build_suite(duration_s=6., cable_length_m=6.)
    outcome = evaluate_suite(Controller(), {'lookahead_m': 3.}, suite=suite)
    validate_robustness(outcome)
    assert outcome['budget']['cases'] == len(suite)
    assert outcome['budget']['simulations'] == 2 * len(suite)
    assert outcome['budget']['equal_per_case_budget'] is True
    assert outcome['conditions']['matched_noise_seed'] is True
    assert outcome['conditions']['physics'] == 'unchanged simulator kernel'
    for case in outcome['cases']:
        assert case['matched'] is True
        assert case['simulator_sha256'] == case['simulator_sha256']
        assert case['baseline_run_id'] != case['candidate_run_id']
        assert set(case['differences']) >= {'rms_cross_track_m', 'effort_proxy_n_s', 'max_abs_cross_track_m'}
    failed = [gate['id'] for gate in outcome['gates'] if not gate['passed']]
    assert outcome['decision'] == ('reject' if failed else 'accept')
    assert outcome['decision_reasons'] == failed


def test_validation_rejects_inconsistent_acceptance():
    suite = build_suite(duration_s=6., cable_length_m=6.)
    outcome = evaluate_suite(Controller(), {'lookahead_m': 3.}, suite=suite)
    forged = {**outcome, 'decision': 'accept', 'decision_reasons': ['no_scenario_rms_regression']}
    with pytest.raises(ValueError):
        validate_robustness(forged)
    with pytest.raises(ValueError):
        validate_robustness({**outcome, 'budget': {**outcome['budget'], 'equal_per_case_budget': False}})


def test_failed_case_is_recorded_without_invented_metrics(monkeypatch):
    import nautilus.v6.robustness as module
    calls = {'n': 0}
    real = module.evaluate_case

    def flaky(case, baseline, changes):
        calls['n'] += 1
        if calls['n'] == 2:
            raise FloatingPointError('nonfinite experimental trajectory')
        return real(case, baseline, changes)

    monkeypatch.setattr(module, 'evaluate_case', flaky)
    outcome = evaluate_suite(Controller(), {'lookahead_m': 3.}, suite=build_suite(duration_s=5., cable_length_m=5.))
    assert outcome['decision'] == 'reject'
    assert outcome['failures'] == [{'scenario_id': 'current_positive', 'error': 'FloatingPointError'}]
    assert len(outcome['cases']) == 6 and len(outcome['suite']) == 7
    assert all(case['scenario_id'] != 'current_positive' for case in outcome['cases'])
