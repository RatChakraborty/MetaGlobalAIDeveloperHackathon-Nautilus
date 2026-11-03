"""Matched candidate/baseline evaluation with instrumentation.

Reuses the frozen V4 development comparison (identical vehicle, faults, mission,
plant, timestep, noise seed and metrics) and adds actuation-effort, stability and
guard context. Nothing here alters simulator physics or the evaluator.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..configuration_evaluation import DevelopmentScenario, evaluate_configuration
from ..simulator import SimulationResult

EXTRA_METRICS = ('effort_proxy_n_s', 'mean_absolute_command_n', 'peak_absolute_command_n',
                 'max_abs_yaw_rate_radps', 'finite_samples', 'guard_involvement')
LIMITATIONS = (
    'Matched offline simulation only; metrics are recorded outputs, not physical measurements.',
    'A lower tracking error does not establish that a physical fault was repaired.',
    'Guard/fallback involvement is not applicable to unguarded matched mission runs; corridor excursions are measured directly.',
    'Command effort is a requested-thrust proxy; it is not electrical power or measured actuator work.',
)


def instrumentation(result: SimulationResult) -> dict:
    if type(result) is not SimulationResult or not result.observations or len(result.observations) != len(result.truth):
        raise ValueError('Matched simulation traces required')
    times = np.array([row['time_s'] for row in result.observations], dtype=float)
    port = np.array([abs(row['port_command_n']) for row in result.observations], dtype=float)
    starboard = np.array([abs(row['starboard_command_n']) for row in result.observations], dtype=float)
    mean_absolute = (port + starboard) / 2
    effort = float(np.sum(mean_absolute[:-1] * np.diff(times))) if len(times) > 1 else 0.
    lateral = np.array([row['y_m'] for row in result.truth], dtype=float)
    rate = np.array([abs(row['yaw_rate_radps']) for row in result.truth], dtype=float)
    finite = bool(np.all(np.isfinite(lateral)) and np.all(np.isfinite(mean_absolute)) and np.all(np.isfinite(rate)))
    return {'effort_proxy_n_s': effort,
            'mean_absolute_command_n': float(np.mean(mean_absolute)) if len(mean_absolute) else 0.,
            'peak_absolute_command_n': float(max(port.max(initial=0.), starboard.max(initial=0.))),
            'max_abs_yaw_rate_radps': float(rate.max(initial=0.)),
            'finite_samples': finite, 'guard_involvement': None}


@dataclass(frozen=True)
class CaseEvaluation:
    scenario_id: str
    evaluation: object
    baseline_instrumentation: dict
    candidate_instrumentation: dict
    instrumentation_differences: dict

    def summary(self) -> dict:
        def run(name):
            evaluated = getattr(self.evaluation, name)
            extra = getattr(self, name + '_instrumentation')
            return {**evaluated.metrics, **extra}
        return {'scenario_id': self.scenario_id, 'baseline': run('baseline'), 'candidate': run('candidate'),
                'differences': {**self.evaluation.metric_differences, **self.instrumentation_differences},
                'approved_differences': self.evaluation.differences,
                'comparison': self.evaluation.summary(),
                'limitations': list(LIMITATIONS)}


def evaluate_case(scenario: DevelopmentScenario, baseline, changes: dict) -> CaseEvaluation:
    """Evaluate one candidate against the approved baseline under matched conditions."""
    evaluation = evaluate_configuration(scenario, baseline, changes)
    base = instrumentation(evaluation.baseline.result)
    cand = instrumentation(evaluation.candidate.result)
    delta = {}
    for name in EXTRA_METRICS:
        if type(base[name]) in (int, float) and type(base[name]) is not bool:
            delta[name] = float(cand[name] - base[name])
    return CaseEvaluation(scenario.identifier, evaluation, base, cand, delta)


def condition_report(case: CaseEvaluation) -> dict:
    """Public, truth-free description of the matched conditions actually used."""
    evaluation = case.evaluation
    return {'scenario_id': case.scenario_id, 'matched': True,
            'simulator_sha256': evaluation.simulator_sha256,
            'conditions': list(evaluation.conditions),
            'reference': dict(evaluation.reference),
            'baseline_run_id': evaluation.baseline.run_id, 'candidate_run_id': evaluation.candidate.run_id,
            'baseline_configuration_id': evaluation.baseline.configuration_id,
            'candidate_configuration_id': evaluation.candidate.configuration_id,
            'baseline_source_sha256': evaluation.baseline.context['source']['sha256'],
            'candidate_source_sha256': evaluation.candidate.context['source']['sha256'],
            'controller_unchanged': evaluation.baseline.context['controller_id'] == evaluation.candidate.context['controller_id'],
            'simulation_seconds': float(evaluation.baseline.metrics['elapsed_s'] + evaluation.candidate.metrics['elapsed_s'])}
