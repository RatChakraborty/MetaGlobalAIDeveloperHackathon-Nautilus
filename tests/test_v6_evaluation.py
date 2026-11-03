from dataclasses import replace

import numpy as np
import pytest

from nautilus.configuration_evaluation import DevelopmentScenario
from nautilus.simulator import Controller, Faults, Mission, simulate
from nautilus.v6 import evaluate_case
from nautilus.v6.evaluation import EXTRA_METRICS, condition_report, instrumentation


def scenario(identifier='unit-v6', faults=None):
    return DevelopmentScenario(identifier, faults=Faults(current_y=.35) if faults is None else faults,
                               mission=Mission(duration_s=6., cable_length_m=6., seed=880011))


def test_matched_conditions_reuse_the_frozen_evaluator():
    case = scenario()
    measured = evaluate_case(case, Controller(), {'lookahead_m': 3.})
    assert measured.evaluation.baseline.result == simulate(case.vehicle, case.faults, Controller(), case.mission, case.plant)
    edited = replace(Controller(), lookahead_m=3.)
    assert measured.evaluation.candidate.result == simulate(case.vehicle, case.faults, edited, case.mission, case.plant)
    assert measured.evaluation.baseline.result != measured.evaluation.candidate.result
    report = condition_report(measured)
    assert report['matched'] is True and report['controller_unchanged'] is True
    assert report['simulation_seconds'] > 0
    assert report['baseline_source_sha256'] == report['candidate_source_sha256']
    assert 'current_y' not in str(report['conditions'])


def test_instrumentation_is_derived_from_recorded_samples():
    case = scenario()
    measured = evaluate_case(case, Controller(), {'heading_kd': 26.})
    result = measured.evaluation.candidate.result
    times = np.array([row['time_s'] for row in result.observations])
    commands = np.array([[abs(row['port_command_n']), abs(row['starboard_command_n'])] for row in result.observations])
    mean_absolute = commands.mean(axis=1)
    expected_effort = float(np.sum(mean_absolute[:-1] * np.diff(times)))
    values = instrumentation(result)
    assert values['effort_proxy_n_s'] == pytest.approx(expected_effort)
    assert values['mean_absolute_command_n'] == pytest.approx(mean_absolute.mean())
    assert values['peak_absolute_command_n'] == pytest.approx(commands.max())
    assert values['max_abs_yaw_rate_radps'] == pytest.approx(max(abs(row['yaw_rate_radps']) for row in result.truth))
    assert values['finite_samples'] is True
    assert values['guard_involvement'] is None
    assert set(measured.baseline_instrumentation) == set(EXTRA_METRICS)


def test_paired_differences_and_partial_metrics():
    measured = evaluate_case(scenario(), Controller(), {'cruise_thrust': 15.})
    summary = measured.summary()
    for name in ('rms_cross_track_m', 'max_abs_cross_track_m', 'fraction_outside_corridor', 'effort_proxy_n_s'):
        assert summary['differences'][name] == pytest.approx(summary['candidate'][name] - summary['baseline'][name])
    assert summary['comparison']['schema_version'] == 'nautilus.configuration-evaluation.v1'
    assert summary['approved_differences'] == {'cruise_thrust': {'baseline': 13., 'candidate': 15., 'unit': 'N'}}
    assert any('not physical measurements' in text for text in summary['limitations'])


def test_no_op_and_determinism():
    case = scenario()
    first = evaluate_case(case, Controller(), {'lookahead_m': 7.})
    second = evaluate_case(case, Controller(), {'lookahead_m': 7.})
    assert first.summary() == second.summary()
    assert first.evaluation.differences == {}
    assert all(value == 0 for value in first.evaluation.metric_differences.values())
    assert all(value == 0 for value in first.instrumentation_differences.values())
    with pytest.raises(ValueError):
        evaluate_case(case, Controller(), {'heading_kp': 500.})


def test_partial_and_model_inadequate_diagnosis_still_evaluates_only_the_controller():
    # A controller change cannot repair a degraded thruster; the metrics must show that.
    degraded = scenario('unit-v6-degraded', faults=Faults(port_efficiency=.3))
    measured = evaluate_case(degraded, Controller(), {'lookahead_m': 3.})
    assert measured.evaluation.candidate.context['controller_id'] == measured.evaluation.baseline.context['controller_id']
    assert 'port_efficiency' not in str(measured.summary()['comparison'])
    with pytest.raises(ValueError):
        evaluate_case(replace(degraded, purpose='held-out'), Controller(), {'lookahead_m': 3.})
