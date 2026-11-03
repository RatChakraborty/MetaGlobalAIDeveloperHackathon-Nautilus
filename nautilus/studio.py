"""Paired, matched evaluation of structural policy-IR controllers.

Reuses the frozen V6 development suite and decision gates
(`nautilus.v6.robustness`) and the simulator's recorded metrics. Baseline and
candidate run against the identical scenario (vehicle, faults, mission, plant,
seed, duration) so differences come only from the controller law.

Development cases may be used for iteration; held-out cases are reported but
never consulted when a candidate is selected.
"""
from __future__ import annotations

import hashlib
import json

from nautilus.policy_ir import PolicyError, baseline_policy, validate
from nautilus.policy_runtime import PolicyController
from nautilus.simulator import Controller, simulate, metrics
from nautilus.v6.evaluation import instrumentation
from nautilus.v6.robustness import ACCEPTANCE, GATES, SUITE_SPECS, decide

# Split of the frozen seven-case V6 suite. Iteration sees only DEVELOPMENT.
DEVELOPMENT_INDEX = (0, 1, 2, 3)
HELD_OUT_INDEX = (4, 5, 6)
METRIC_KEYS = ('rms_cross_track_m', 'max_abs_cross_track_m', 'fraction_outside_corridor',
               'command_saturation_fraction', 'mission_success', 'effort_proxy_n_s')
MAX_TRIALS = 24


def cases(part: str = 'development'):
    """Matched scenarios from the V6 suite, selected by the declared split."""
    from nautilus.v6.robustness import build_suite
    full = build_suite()
    index = DEVELOPMENT_INDEX if part == 'development' else HELD_OUT_INDEX
    return tuple(full[i] for i in index)


def policy_fingerprint(policy: dict) -> str:
    payload = json.dumps(policy, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode()).hexdigest()


def _metrics(result, mission, vehicle) -> dict:
    """Recorded simulator metrics plus the V6 actuation-effort instrumentation."""
    measured = dict(metrics(result, mission, vehicle))
    measured.update(instrumentation(result))
    return measured


def _run(scenario, policy):
    """Execute one controller on one matched scenario; returns (metrics, result, runtime)."""
    mission = scenario.mission
    controller = PolicyController(policy, mission.dt_s)
    result = simulate(scenario.vehicle, scenario.faults, Controller(),
                      mission, scenario.plant, policy=controller)
    return _metrics(result, mission, scenario.vehicle), result, controller


def _baseline_run(scenario):
    result = simulate(scenario.vehicle, scenario.faults, Controller(),
                      scenario.mission, scenario.plant)
    return _metrics(result, scenario.mission, scenario.vehicle), result


def _row(scenario, policy):
    base, _ = _baseline_run(scenario)
    cand, result, controller = _run(scenario, policy)
    row = {'scenario_id': scenario.identifier,
           'baseline': {k: base[k] for k in METRIC_KEYS},
           'candidate': {k: cand[k] for k in METRIC_KEYS}}
    row['baseline']['finite_samples'] = bool(base['mission_success'] is not None)
    row['candidate']['finite_samples'] = bool(cand['mission_success'] is not None)
    row['saturation_steps'] = controller.saturated_steps
    row['steps'] = controller.steps
    return row, result


def paired_trial(policy: dict, part: str = 'development', scenario_ids=None) -> dict:
    """Evaluate a candidate against the baseline on matched scenarios."""
    validate(policy)
    selected = [case for case in cases(part) if scenario_ids is None or case.identifier in scenario_ids]
    if not selected or len(selected) > MAX_TRIALS:
        raise PolicyError('trial selection outside supported bounds')
    rows, traces = [], {}
    for scenario in selected:
        row, result = _row(scenario, policy)
        rows.append(row)
        traces[scenario.identifier] = result
    decision = decide([{k: row[k] for k in ('scenario_id', 'baseline', 'candidate')} for row in rows])
    return {'part': part, 'rows': rows, 'decision': decision,
            'outcome': outcome(decision, rows), 'traces': traces,
            'policy_fingerprint': policy_fingerprint(policy), 'acceptance': dict(ACCEPTANCE)}


def outcome(decision: dict, rows) -> dict:
    """Recommended / Rejected / Inconclusive with explicit numerical reasons.

    A rejection is only 'inconclusive' when the evidence does not separate the
    candidate from noise-level differences: the candidate neither improves the
    mean RMS by the declared margin nor violates any safety/regression gate.
    """
    gates = {gate['id']: gate for gate in decision['gates']}
    failed = [gid for gid, gate in gates.items() if not gate['passed']]
    improved = gates['mean_rms_improvement']['passed']
    regression = [gid for gid in failed if gid != 'mean_rms_improvement']
    if decision['decision'] == 'accept':
        label = 'Recommended'
    elif not improved and not regression:
        label = 'Inconclusive'
    elif not improved:
        label = 'Rejected'
    else:
        label = 'Rejected'
    return {'label': label, 'failed_gates': failed,
            'mean_rms_difference_m': decision['aggregate']['mean_rms_cross_track_m']['difference'],
            'gate_descriptions': {gid: dict(GATES)[gid] for gid in failed if gid in dict(GATES)},
            'rationale': _rationale(label, gates)}


def _rationale(label, gates):
    if label == 'Recommended':
        return 'All declared gates passed: cross-track RMS improved by the required margin with no regression or constraint breach.'
    if label == 'Inconclusive':
        return 'The candidate neither improved mean cross-track RMS by the required margin nor failed a safety gate; the evidence does not justify a recommendation.'
    improved = gates['mean_rms_improvement']['passed']
    if improved:
        return 'The candidate improved tracking but failed at least one regression or safety gate; the tradeoff is not acceptable.'
    return 'The candidate did not improve cross-track RMS and did not pass every safety gate.'


def compare_metrics(trial: dict) -> dict:
    """Per-scenario numerical comparison from actual runs."""
    aggregate = trial['decision']['aggregate']
    return {'aggregate': aggregate, 'per_case': trial['decision']['per_case'],
            'gates': trial['decision']['gates'], 'outcome': trial['outcome']}


def robustness(policy: dict) -> dict:
    """Evaluate on the held-out split; reported for evidence, never used for selection."""
    trial = paired_trial(policy, part='held_out')
    trial.pop('traces', None)
    return trial


def canonical_baseline():
    return baseline_policy()
