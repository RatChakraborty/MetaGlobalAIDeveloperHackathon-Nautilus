"""Fixed development robustness suite and its predeclared acceptance rule.

The suite is fixed before any candidate is proposed and every case runs the
baseline and the candidate with identical conditions. The rule is deliberately
conservative: average tracking error alone can never carry an acceptance.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import field
import hashlib
import math
from pathlib import Path

from ..configuration_evaluation import DevelopmentScenario
from ..simulator import Faults, Mission, PlantConfig, Vehicle
from .evaluation import evaluate_case

SCHEMA = 'nautilus.robustness-evaluation.v1'
ACCEPTANCE = {
    'min_mean_rms_improvement_m': .05,
    'max_scenario_rms_regression_m': .10,
    'max_worst_case_cross_track_increase_m': .25,
    'max_worst_case_outside_fraction_increase': .05,
    'max_saturation_increase': .05,
    'max_effort_increase_fraction': .20,
}
GATES = (
    ('finite_runs', 'Every baseline and candidate run produced finite traces.'),
    ('mean_rms_improvement', 'Mean cross-track RMS improves by at least the declared minimum.'),
    ('no_scenario_rms_regression', 'No single development scenario regresses beyond the declared limit.'),
    ('no_worst_case_cross_track_regression', 'Worst-case maximum cross-track error does not grow beyond the declared limit.'),
    ('no_worst_case_excursion_regression', 'Worst-case corridor excursion fraction does not grow beyond the declared limit.'),
    ('no_completion_regression', 'The number of completed development missions does not fall.'),
    ('no_saturation_regression', 'Worst-case command saturation does not grow beyond the declared limit.'),
    ('no_effort_blowup', 'Mean actuation-effort proxy does not grow beyond the declared fraction.'),
)
SUITE_SPECS = (
    ('nominal', {}, {}, 5201),
    ('current_positive', {'current_y': .45}, {}, 5202),
    ('current_negative', {'current_y': -.45}, {}, 5203),
    ('thruster_degradation', {'port_efficiency': .45}, {}, 5204),
    ('heading_bias', {'heading_bias_rad': .30}, {}, 5205),
    ('compound_current_bias_degradation', {'current_y': .40, 'heading_bias_rad': .22, 'starboard_efficiency': .55}, {}, 5206),
    ('model_mismatch', {}, {'actuator_tau_s': 1.2, 'thrust_deadzone_n': 4., 'drag_scale': 1.12}, 5207),
)
SCREENED_IDS = ('nominal', 'current_positive')
LIMITATIONS = (
    'Fixed development suite; these are not benchmark or held-out evaluation cases.',
    'Two declared cases screen candidate selection; the other five are never consulted, but no case is held out.',
    'No simulation result is a real-world controller safety certificate.',
    'Model mismatch is limited to actuator lag, dead zone and uniform drag scaling.',
)


def build_suite(duration_s: float = 45., dt_s: float = .05, cable_length_m: float = 30.,
                cable_half_width_m: float = 1.5, specs=SUITE_SPECS) -> tuple[DevelopmentScenario, ...]:
    if not (0 < duration_s <= 120) or not (.02 <= dt_s <= .2) or cable_length_m <= 0 or cable_half_width_m <= 0:
        raise ValueError('Invalid development suite geometry')
    suite = []
    for identifier, faults, plant, seed in specs:
        mission = Mission(duration_s=float(duration_s), dt_s=float(dt_s), cable_length_m=float(cable_length_m),
                          cable_half_width_m=float(cable_half_width_m), seed=seed)
        suite.append(DevelopmentScenario(identifier, vehicle=Vehicle(), faults=Faults(**faults),
                                         mission=mission, plant=PlantConfig(**plant)))
    return tuple(suite)


DEFAULT_SUITE = build_suite()


def suite_fingerprint(suite) -> str:
    body = [{'id': case.identifier, 'vehicle': case.vehicle.__dict__, 'faults': case.faults.__dict__,
             'plant': case.plant.__dict__, 'mission': case.mission.__dict__} for case in suite]
    return hashlib.sha256(str(body).encode()).hexdigest()


def _worst(rows, key, name):
    return max(row[name][key] for row in rows)


def _aggregate(rows) -> dict:
    """Paired aggregate for any measured row subset."""
    def mean(side, key):
        return sum(row[side][key] for row in rows) / len(rows)

    def worst(side, key):
        return max(row[side][key] for row in rows)

    def pair(base, cand):
        return {'baseline': base, 'candidate': cand, 'difference': cand - base}

    return {
        'mean_rms_cross_track_m': pair(mean('baseline', 'rms_cross_track_m'), mean('candidate', 'rms_cross_track_m')),
        'worst_case_max_abs_cross_track_m': pair(worst('baseline', 'max_abs_cross_track_m'),
                                                 worst('candidate', 'max_abs_cross_track_m')),
        'worst_case_fraction_outside_corridor': pair(worst('baseline', 'fraction_outside_corridor'),
                                                     worst('candidate', 'fraction_outside_corridor')),
        'worst_case_command_saturation_fraction': pair(worst('baseline', 'command_saturation_fraction'),
                                                       worst('candidate', 'command_saturation_fraction')),
        'completed_missions': pair(sum(bool(row['baseline']['mission_success']) for row in rows),
                                   sum(bool(row['candidate']['mission_success']) for row in rows)),
        'mean_effort_proxy_n_s': pair(mean('baseline', 'effort_proxy_n_s'), mean('candidate', 'effort_proxy_n_s')),
    }


def decide(rows, acceptance=ACCEPTANCE, *, failures=()) -> dict:
    """Apply the predeclared rule to measured per-scenario rows."""
    if type(acceptance) is not dict or set(acceptance) != set(ACCEPTANCE):
        raise ValueError('Predeclared acceptance rule required')
    for name, value in acceptance.items():
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('Invalid acceptance threshold')
    if type(failures) not in (list, tuple):
        raise ValueError('Invalid failure list')
    if not rows:
        return {'decision': 'reject', 'reasons': ['no_measured_cases'], 'gates': [], 'aggregate': None,
                'failures': list(failures), 'acceptance': dict(acceptance)}
    for row in rows:
        if type(row) is not dict or set(row) != {'scenario_id', 'baseline', 'candidate'}:
            raise ValueError('Measured robustness row required')
        for side in ('baseline', 'candidate'):
            metrics = row[side]
            for key in ('rms_cross_track_m', 'max_abs_cross_track_m', 'fraction_outside_corridor',
                        'command_saturation_fraction', 'mission_success', 'effort_proxy_n_s'):
                if key not in metrics or type(metrics[key]) not in (int, float, bool):
                    raise ValueError('Missing measured robustness metric')
    rms_base = [row['baseline']['rms_cross_track_m'] for row in rows]
    rms_cand = [row['candidate']['rms_cross_track_m'] for row in rows]
    mean_base = sum(rms_base) / len(rows)
    mean_cand = sum(rms_cand) / len(rows)
    worst_base = _worst(rows, 'max_abs_cross_track_m', 'baseline')
    worst_cand = _worst(rows, 'max_abs_cross_track_m', 'candidate')
    outside_base = _worst(rows, 'fraction_outside_corridor', 'baseline')
    outside_cand = _worst(rows, 'fraction_outside_corridor', 'candidate')
    saturation_base = _worst(rows, 'command_saturation_fraction', 'baseline')
    saturation_cand = _worst(rows, 'command_saturation_fraction', 'candidate')
    success_base = sum(bool(row['baseline']['mission_success']) for row in rows)
    success_cand = sum(bool(row['candidate']['mission_success']) for row in rows)
    effort_base = sum(row['baseline']['effort_proxy_n_s'] for row in rows) / len(rows)
    effort_cand = sum(row['candidate']['effort_proxy_n_s'] for row in rows) / len(rows)
    effort_limit = effort_base * (1 + acceptance['max_effort_increase_fraction'])
    per_case = [{'scenario_id': row['scenario_id'],
                 'rms_difference_m': row['candidate']['rms_cross_track_m'] - row['baseline']['rms_cross_track_m']}
                for row in rows]
    finite = not failures and all(bool(row[side].get('finite_samples', True)) for row in rows for side in ('baseline', 'candidate'))
    gates = [
        {'id': 'finite_runs', 'passed': bool(finite), 'observed': len(failures), 'threshold': 0,
         'description': GATES[0][1]},
        {'id': 'mean_rms_improvement', 'passed': (mean_cand - mean_base) <= -acceptance['min_mean_rms_improvement_m'],
         'observed': mean_cand - mean_base, 'threshold': -acceptance['min_mean_rms_improvement_m'],
         'description': GATES[1][1]},
        {'id': 'no_scenario_rms_regression',
         'passed': max(item['rms_difference_m'] for item in per_case) <= acceptance['max_scenario_rms_regression_m'],
         'observed': max(item['rms_difference_m'] for item in per_case),
         'threshold': acceptance['max_scenario_rms_regression_m'], 'description': GATES[2][1]},
        {'id': 'no_worst_case_cross_track_regression', 'passed': worst_cand - worst_base <= acceptance['max_worst_case_cross_track_increase_m'],
         'observed': worst_cand - worst_base, 'threshold': acceptance['max_worst_case_cross_track_increase_m'],
         'description': GATES[3][1]},
        {'id': 'no_worst_case_excursion_regression', 'passed': outside_cand - outside_base <= acceptance['max_worst_case_outside_fraction_increase'],
         'observed': outside_cand - outside_base, 'threshold': acceptance['max_worst_case_outside_fraction_increase'],
         'description': GATES[4][1]},
        {'id': 'no_completion_regression', 'passed': success_cand >= success_base, 'observed': success_cand,
         'threshold': success_base, 'description': GATES[5][1]},
        {'id': 'no_saturation_regression', 'passed': saturation_cand - saturation_base <= acceptance['max_saturation_increase'],
         'observed': saturation_cand - saturation_base, 'threshold': acceptance['max_saturation_increase'],
         'description': GATES[6][1]},
        {'id': 'no_effort_blowup', 'passed': effort_cand <= effort_limit, 'observed': effort_cand,
         'threshold': effort_limit, 'description': GATES[7][1]},
    ]
    reasons = [gate['id'] for gate in gates if not gate['passed']]
    return {'decision': 'accept' if not reasons else 'reject', 'reasons': reasons, 'gates': gates,
            'failures': list(failures), 'acceptance': dict(acceptance),
            'aggregate': _aggregate(rows),
            'per_case': per_case}


def evaluate_suite(baseline, changes: dict, *, suite=None, acceptance=ACCEPTANCE) -> dict:
    """Run every fixed development case once per side and apply the declared rule."""
    suite = tuple(DEFAULT_SUITE if suite is None else suite)
    if not suite:
        raise ValueError('Development suite required')
    cases, failures, budget = [], [], 0.
    for case in suite:
        try:
            measured = evaluate_case(case, baseline, changes)
        except (ValueError, FloatingPointError) as exc:
            failures.append({'scenario_id': case.identifier, 'error': type(exc).__name__})
            continue
        row = measured.summary()
        budget += float(measured.evaluation.baseline.metrics['elapsed_s'] + measured.evaluation.candidate.metrics['elapsed_s'])
        cases.append({'scenario_id': row['scenario_id'], 'baseline': row['baseline'], 'candidate': row['candidate'],
                      'differences': row['differences'], 'matched': True,
                      'conditions': list(measured.evaluation.conditions),
                      'baseline_run_id': measured.evaluation.baseline.run_id,
                      'candidate_run_id': measured.evaluation.candidate.run_id,
                      'baseline_configuration_id': measured.evaluation.baseline.configuration_id,
                      'candidate_configuration_id': measured.evaluation.candidate.configuration_id,
                      'simulator_sha256': measured.evaluation.simulator_sha256})
    rows = [{'scenario_id': case['scenario_id'], 'baseline': case['baseline'], 'candidate': case['candidate']} for case in cases]
    outcome = decide(rows, acceptance, failures=failures)
    screened = [row for row in rows if row['scenario_id'] in SCREENED_IDS]
    unscreened = [row for row in rows if row['scenario_id'] not in SCREENED_IDS]
    exposure = {'held_out': False,
                'screened_case_ids': [row['scenario_id'] for row in screened],
                'unscreened_case_ids': [row['scenario_id'] for row in unscreened],
                'screened_aggregate': _aggregate(screened) if screened else None,
                'unscreened_aggregate': _aggregate(unscreened) if unscreened else None,
                'statement': ('Two declared development cases screen candidate selection; the other five are never '
                              'consulted during selection. This suite is not held out.')}
    return {'schema_version': SCHEMA,
            'suite_id': 'nautilus.development-suite.v1',
            'suite_sha256': suite_fingerprint(suite),
            'suite': [case.identifier for case in suite],
            'cases': cases,
            'per_scenario': outcome['per_case'],
            'screening_exposure': exposure,
            'gates': outcome['gates'],
            'acceptance': outcome['acceptance'],
            'aggregate': outcome['aggregate'],
            'decision': outcome['decision'],
            'decision_reasons': outcome['reasons'],
            'failures': failures,
            'budget': {'cases': len(suite), 'simulations': 2 * len(suite),
                       'total_simulation_s': budget,
                       'equal_per_case_budget': True},
            'conditions': {'matched_vehicle': True, 'matched_faults': True, 'matched_mission': True,
                           'matched_plant': True, 'matched_timestep': True, 'matched_noise_seed': True,
                           'baseline_candidate_seed_identity': True,
                           'physics': 'unchanged simulator kernel'},
            'limitations': list(LIMITATIONS)}


def validate_robustness(value: dict) -> dict:
    if type(value) is not dict:
        raise ValueError('Robustness evaluation required')
    expected = {'schema_version', 'suite_id', 'suite_sha256', 'suite', 'cases', 'per_scenario', 'gates',
                'screening_exposure', 'acceptance', 'aggregate', 'decision', 'decision_reasons', 'failures',
                'budget', 'conditions', 'limitations'}
    if set(value) != expected or value['schema_version'] != SCHEMA:
        raise ValueError('Unsupported robustness schema')
    if type(value['suite_sha256']) is not str or len(value['suite_sha256']) != 64:
        raise ValueError('Invalid suite fingerprint')
    if value['decision'] not in ('accept', 'reject') or type(value['cases']) is not list or not value['cases']:
        raise ValueError('Invalid robustness decision')
    if len(value['suite']) != len(value['cases']) + len(value['failures']):
        raise ValueError('Incomplete robustness accounting')
    if [gate.get('id') for gate in value['gates']] != [gate[0] for gate in GATES]:
        raise ValueError('Predeclared gates required')
    failed = [gate['id'] for gate in value['gates'] if not gate['passed']]
    if value['decision'] == 'accept' and (failed or value['decision_reasons'] or value['failures']):
        raise ValueError('Acceptance requires every declared gate to pass')
    if value['decision'] == 'reject' and not value['decision_reasons']:
        raise ValueError('Rejection requires a recorded reason')
    if type(value['budget']) is not dict or value['budget'].get('equal_per_case_budget') is not True:
        raise ValueError('Equal evaluation budgets required')
    exposure = value['screening_exposure']
    if type(exposure) is not dict or set(exposure) != {'held_out', 'screened_case_ids', 'unscreened_case_ids',
                                                       'screened_aggregate', 'unscreened_aggregate', 'statement'}:
        raise ValueError('Invalid screening exposure record')
    if exposure['held_out'] is not False:
        raise ValueError('A development suite cannot be reported as held out')
    if sorted(list(exposure['screened_case_ids']) + list(exposure['unscreened_case_ids'])) != sorted(value['suite']):
        raise ValueError('Screening disclosure must account for every suite case')
    return deepcopy(value)
