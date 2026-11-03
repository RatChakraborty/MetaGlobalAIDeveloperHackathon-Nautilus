"""Bounded, evidence-grounded parameter proposals and coordinate search.

Screening uses only two declared development cases. They are members of the
reported development suite, so this is partial selection exposure and is disclosed
in every evaluation; the other five cases are never consulted and no case is held
out. Every attempted candidate is retained, including regressions.
"""
from __future__ import annotations

import math

from ..controller_context import PARAMETERS
from .evaluation import evaluate_case
from .policy import TUNABLE
from .robustness import SCREENED_IDS, SUITE_SPECS, build_suite

SCREENING_IDS = SCREENED_IDS
GRID = {'lookahead_m': (3., 5., 9., 11.), 'heading_kp': (30., 48.), 'heading_kd': (12., 26.),
        'cruise_thrust': (11.5, 15.)}
MAX_CANDIDATES = 14
SCREENING = build_suite(duration_s=30., cable_length_m=24.,
                        specs=tuple(spec for spec in SUITE_SPECS if spec[0] in SCREENING_IDS))


def validate_change(value, evidence_refs, policy=None) -> dict:
    """Strict schema for a model-generated single-parameter proposal."""
    if type(value) is not dict:
        raise ValueError('Configuration proposal object required')
    if set(value) - {'parameter', 'value', 'rationale', 'evidence_refs', 'expected_effect'} or \
            not {'parameter', 'value', 'rationale', 'evidence_refs', 'expected_effect'} <= set(value):
        raise ValueError('Invalid configuration proposal fields')
    name, number = value['parameter'], value['value']
    if type(name) is not str or name not in TUNABLE:
        raise ValueError('Unsupported configuration proposal parameter')
    low, high = PARAMETERS[name][1:3]
    if type(number) not in (int, float) or type(number) is bool or not math.isfinite(number) or not low <= number <= high:
        raise ValueError('Configuration proposal outside approved bounds')
    if policy is not None and policy['parameters'][name]['bounds'] != [low, high]:
        raise ValueError('Policy bounds changed')
    for key, limit in (('rationale', 1000), ('expected_effect', 500)):
        if type(value[key]) is not str or not value[key].strip() or len(value[key]) > limit:
            raise ValueError('Invalid configuration proposal text')
    refs = value['evidence_refs']
    if type(refs) is not list or not refs or len(refs) > 128 or len(set(refs)) != len(refs):
        raise ValueError('Public observation references required')
    if any(type(ref) is not str or ref not in evidence_refs for ref in refs):
        raise ValueError('Public observation references required')
    return {'parameter': name, 'value': float(number), 'rationale': value['rationale'],
            'evidence_refs': list(refs), 'expected_effect': value['expected_effect']}


def _screen_one(baseline, changes, screening):
    per_case, deltas = [], []
    for case in screening:
        measured = evaluate_case(case, baseline, changes)
        row = measured.summary()
        deltas.append({'scenario_id': row['scenario_id'],
                       'rms_difference_m': row['differences']['rms_cross_track_m'],
                       'worst_case_difference_m': row['differences']['max_abs_cross_track_m']})
        per_case.append(row)
    mean = sum(item['rms_difference_m'] for item in deltas) / len(deltas)
    worst = max(item['worst_case_difference_m'] for item in deltas)
    return {'changes': dict(changes), 'per_case': per_case, 'mean_rms_difference_m': mean,
            'worst_case_cross_track_difference_m': worst,
            'admissible': worst <= .25 and mean <= 0.,
            'simulation_seconds': sum(float(row['baseline']['elapsed_s'] + row['candidate']['elapsed_s']) for row in per_case)}


def screen(baseline, *, grid=GRID, screening=SCREENING, limit=MAX_CANDIDATES) -> dict:
    if type(limit) is not int or not 0 < limit <= MAX_CANDIDATES:
        raise ValueError('Bounded candidate limit required')
    if type(grid) is not dict or set(grid) - set(TUNABLE):
        raise ValueError('Only approved tunable parameters may be searched')
    screening = tuple(screening)
    if not screening:
        raise ValueError('Screening cases required')
    attempted, budget, count = [], 0., 0
    for name, values in grid.items():
        for value in values:
            if count >= limit:
                break
            low, high = PARAMETERS[name][1:3]
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError('Grid value outside approved bounds')
            result = _screen_one(baseline, {name: float(value)}, screening)
            attempted.append(result)
            budget += result['simulation_seconds']
            count += 1
    admissible = [item for item in attempted if item['admissible']]
    best = min(admissible, key=lambda item: item['mean_rms_difference_m']) if admissible else None
    return {'schema_version': 'nautilus.proposal-screening.v1', 'screening_cases': [c.identifier for c in screening],
            'attempted': attempted, 'best': best['changes'] if best else None,
            'admissible': len(admissible), 'evaluations': len(attempted),
            'budget': {'candidates': len(attempted), 'limit': limit, 'simulation_seconds': budget},
            'limitations': ('Screening uses two declared development cases that are also members of the reported suite; this is partial selection exposure, not held-out evaluation.',
                            'Every attempted candidate is retained, including regressions.')}


def coordinate_search(baseline, *, grid=GRID, screening=SCREENING, limit=MAX_CANDIDATES) -> dict:
    """One screening pass, then a bounded second pass combining the best single change."""
    first = screen(baseline, grid=grid, screening=screening, limit=limit)
    combinations, budget = [], first['budget']['simulation_seconds']
    best_single = first['best']
    if best_single:
        parameter, value = next(iter(best_single.items()))
        for name in TUNABLE:
            if name == parameter or first['evaluations'] + len(combinations) >= limit:
                continue
            values = [item['changes'][name] for item in first['attempted']
                      if item['admissible'] and name in item['changes']]
            if not values:
                continue
            nearest = min(values, key=lambda candidate: abs(candidate - getattr(baseline, name)))
            result = _screen_one(baseline, {parameter: value, name: nearest}, screening)
            combinations.append(result)
            budget += result['simulation_seconds']
    pool = [item for item in first['attempted'] + combinations if item['admissible']]
    best = min(pool, key=lambda item: item['mean_rms_difference_m']) if pool else None
    return {'schema_version': 'nautilus.proposal-search.v1', 'screening_cases': list(first['screening_cases']),
            'singles': first['attempted'], 'combinations': combinations,
            'attempted': first['attempted'] + combinations,
            'best': best['changes'] if best else None, 'best_measured': best,
            'budget': {'candidates': first['evaluations'] + len(combinations), 'limit': limit,
                       'simulation_seconds': budget},
            'limitations': ('Bounded coordinate search on a predeclared grid; not an optimizer and not a global optimum.',
                            'Two screening cases are members of the reported development suite; no case is held out.',
                            'Search improves tracking metrics only; it cannot repair a physical fault.')}
