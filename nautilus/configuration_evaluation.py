from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import math
import re

import numpy as np

from .controller_context import build_controller_context, configuration, fingerprint
from .simulator import Controller, Faults, Mission, PlantConfig, SimulationResult, Vehicle, metrics, simulate, validate

CHANGES = ('lookahead_m', 'heading_kp', 'heading_kd', 'cruise_thrust')


@dataclass(frozen=True)
class DevelopmentScenario:
    identifier: str
    vehicle: Vehicle = field(default_factory=Vehicle)
    faults: Faults = field(default_factory=Faults)
    mission: Mission = field(default_factory=Mission)
    plant: PlantConfig = field(default_factory=PlantConfig)
    purpose: str = 'development-only'


@dataclass(frozen=True)
class EvaluatedRun:
    run_id: str
    context: dict
    configuration_id: str
    trajectory_sha256: str
    metrics: dict
    result: SimulationResult = field(repr=False)


@dataclass(frozen=True)
class ConfigurationEvaluation:
    scenario_id: str
    differences: dict
    baseline: EvaluatedRun
    candidate: EvaluatedRun
    metric_differences: dict
    reference: dict
    simulator_sha256: str
    conditions: tuple[str, ...]
    limitations: tuple[str, ...]

    def summary(self):
        def run(value):
            return {'run_id': value.run_id, 'controller_id': value.context['controller_id'],
                    'configuration_id': value.configuration_id, 'context_hash': value.context['context_hash'],
                    'source_sha256': value.context['source']['sha256'], 'trajectory_sha256': value.trajectory_sha256, 'metrics': value.metrics}
        return {'schema_version': 'nautilus.configuration-evaluation.v1', 'scenario_id': self.scenario_id,
                'baseline': run(self.baseline), 'candidate': run(self.candidate),
                'approved_differences': self.differences, 'metric_differences': self.metric_differences,
                'simulator_sha256': self.simulator_sha256, 'conditions': list(self.conditions),
                'limitations': list(self.limitations), 'scope': 'Trusted development comparison; visualization-only metrics; not a verified repair.'}


def _metrics(result, mission, vehicle):
    out = metrics(result, mission, vehicle)
    count = sum(abs(r['y_m']) > mission.cable_half_width_m for r in result.truth)
    reached = out['reached_cable_end']
    commands = np.array([[r['port_command_n'], r['starboard_command_n']] for r in result.observations])
    return {**out, 'samples': len(result.truth), 'outside_corridor_samples': count,
            'completion_time_s': out['elapsed_s'] if reached else None,
            'termination': 'cable_end' if reached else 'duration_cap',
            'saturated_command_samples': int(np.sum(np.any(abs(commands) >= vehicle.max_thrust-1e-6, axis=1))),
            'mean_squared_command_n2': float(np.mean(commands**2))}


def evaluate_configuration(scenario: DevelopmentScenario, baseline: Controller, changes: dict) -> ConfigurationEvaluation:
    # Privileged development API; never registered as an investigator tool.
    if type(scenario) is not DevelopmentScenario or scenario.purpose != 'development-only' or not re.fullmatch(r'[A-Za-z0-9._-]{1,100}', scenario.identifier):
        raise ValueError('Trusted development scenario required')
    if type(changes) is not dict or not changes or set(changes)-set(CHANGES):
        raise ValueError('Unsupported controller configuration change')
    approved = configuration(baseline)
    for name, value in changes.items():
        low, high = approved[name]['bounds']
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError('Candidate value outside approved bounds')
    candidate = replace(baseline, **changes)
    for obj, kind in ((scenario.vehicle, Vehicle), (scenario.faults, Faults), (scenario.mission, Mission), (scenario.plant, PlantConfig)):
        if type(obj) is not kind or any(type(v) not in (int, float) or not math.isfinite(v) for v in asdict(obj).values()):
            raise ValueError('Invalid trusted scenario configuration')
    if scenario.vehicle.max_thrust != 45. or not .02 <= scenario.mission.dt_s <= .2 or not 0 < scenario.mission.duration_s <= 120 or type(scenario.mission.seed) is not int or scenario.mission.seed < 0:
        raise ValueError('Outside bounded development comparison conditions')
    validate(scenario.vehicle, scenario.faults, baseline, scenario.mission, scenario.plant)
    differences = {key: {'baseline': approved[key]['value'], 'candidate': float(value), 'unit': approved[key]['unit']}
                   for key, value in changes.items() if value != getattr(baseline, key)}
    def run(controller):
        context = build_controller_context(controller)
        if context['source']['inspection_status'] != 'supported':
            raise ValueError('Approved controller implementation required')
        result = simulate(scenario.vehicle, scenario.faults, controller, scenario.mission, scenario.plant)
        return EvaluatedRun(fingerprint({'observations': result.observations, 'context_hash': context['context_hash']}),
                            context, fingerprint(configuration(controller)),
                            fingerprint([{k:r[k] for k in ('time_s','x_m','y_m','heading_rad')} for r in result.truth]),
                            _metrics(result, scenario.mission, scenario.vehicle), result)
    a, b = run(baseline), run(candidate)
    delta = {k: b.metrics[k]-v for k, v in a.metrics.items()
             if type(v) in (int, float) and type(b.metrics[k]) in (int, float)}
    import hashlib
    from pathlib import Path
    return ConfigurationEvaluation(scenario.identifier, differences, a, b, delta,
        {'cable_length_m': scenario.mission.cable_length_m, 'cable_half_width_m': scenario.mission.cable_half_width_m,
         'source': 'Recorded matched development mission dimensions; y=0 centerline'},
        hashlib.sha256(Path(__file__).with_name('simulator.py').read_bytes()).hexdigest(),
        ('Vehicle, faults, actuator model, geometry, duration cap, timestep, noise configuration and seed are matched.',
         'Both runs start from the simulator zero state with zero actuator state.',
         'Noise streams match by sample index; different completion times can yield different trace lengths.'),
        ('Truth-derived tracking/completion metrics are visualization-only, not investigator observations.',
         'Sample counts are not continuous breach durations; command saturation is not measured force.',
         'One development scenario does not establish diagnosis, general improvement or verified repair.',
         'Private scenario settings and seeds are intentionally excluded from the summary.'))
