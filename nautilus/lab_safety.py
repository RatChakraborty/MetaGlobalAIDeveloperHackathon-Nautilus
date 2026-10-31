from dataclasses import replace, asdict
import math
import numpy as np
from .simulator import (Vehicle, Faults, PlantConfig, Controller, Mission, simulate,
                        effective_vehicle, actuator_step, dynamics, experiment_command, wrap_angle, validate)
from .v2_experiments import parse_trial

CORRIDOR = 1.5
PREDICTIVE_LIMIT = 1.1
GUARD = .9
TAIL_S = 2.
DT = .05
MODES = ('simulation_advisory', 'simulation_enforced')


def uncertainty_cases():
    base = (Faults(), PlantConfig(), Controller())
    result = [base]
    for field, values in [('current_y', (-.65, .65)), ('heading_bias_rad', (-.5, .5)),
                          ('port_efficiency', (.3,)), ('starboard_efficiency', (.3,))]:
        for value in values:
            result.append((replace(base[0], **{field: value}), PlantConfig(actuator_tau_s=1.2, thrust_deadzone_n=.5), base[2]))
    for field in ('drag_surge_scale', 'drag_sway_scale', 'drag_yaw_scale', 'uniform_drag_scale'):
        result.append((base[0], replace(base[1], **{field: 3.}), base[2]))
    for current in (-.65, .65):
        for bias in (-.5, .5):
            result.append((Faults(current_y=current, heading_bias_rad=bias, port_efficiency=.3),
                           PlantConfig(actuator_tau_s=1.2, thrust_deadzone_n=6., drag_scale=.9), base[2]))
    return result


def screen(trial):
    maxima = []
    for faults, plant, controller in uncertainty_cases():
        rows, _, _ = guarded_trial(trial, faults, plant, controller, 0, noise_y=0.)
        maxima.append(max(abs(row['observed_y_m']) for row in rows))
    worst = max(maxima)
    return {'accepted': worst + 4*.035 <= PREDICTIVE_LIMIT,
            'nominal_max_y_m': maxima[0], 'ensemble_max_y_m': worst,
            'limit_m': PREDICTIVE_LIMIT, 'corridor_m': CORRIDOR, 'noise_allowance_m': .14,
            'ensemble_size': len(maxima), 'tail_reserve_s': TAIL_S,
            'uncertainty': 'Finite singleton and selected combined stress cases: current±.65m/s, bias±.5rad, efficiency≥.3, lag≤1.2s, dead zone≤6N, drag scales≤3.',
            'qualification': 'Finite screening, not a reachable-set proof. Unmodeled conditions and stopping drift may violate the corridor.'}


def guarded_trial(trial, faults, plant, controller, seed, *, noise_y=.035, mode='simulation_enforced'):
    if mode not in MODES: raise ValueError('Unknown simulation policy')
    validate(Vehicle(), faults, controller, Mission(), plant)
    vehicle = Vehicle()
    effective = effective_vehicle(vehicle, plant)
    control = replace(controller, cruise_thrust=trial.cruise_thrust_n)
    experiment = trial.experiment()
    rng = np.random.default_rng(seed)
    state = np.zeros(6)
    actual = np.zeros(2)
    observations, truth = [], []
    triggered = None
    enforced = mode == 'simulation_enforced'
    limit = trial.duration_s + (TAIL_S if enforced else 0.)
    for index in range(round(limit/DT)+1):
        t = index*DT
        y = float(state[1] + rng.normal(0, noise_y))
        heading = wrap_angle(float(state[2])+faults.heading_bias_rad+rng.normal(0, .004))
        rate = float(state[5]+rng.normal(0, .003))
        if triggered is None and abs(y) >= GUARD:
            triggered = t
        stopping = enforced and (triggered is not None or t >= trial.duration_s)
        port, star, _ = (0., 0., 0.) if stopping else experiment_command(t, y, heading, rate, vehicle, control, experiment)
        observations.append(dict(time_s=t, observed_y_m=y, observed_heading_rad=heading,
                                 observed_yaw_rate_radps=rate, port_command_n=port, starboard_command_n=star))
        truth.append({'time_s': t, 'y_m': float(state[1]), 'speed_mps': float(np.linalg.norm(state[3:5]))})
        if t >= min(limit, (triggered+TAIL_S) if enforced and triggered is not None else limit)-1e-9:
            break
        actual = actuator_step(actual, np.array([port, star]), DT, plant)
        a = dynamics(state, *actual, effective, faults)
        b = dynamics(state+DT*a/2, *actual, effective, faults)
        c = dynamics(state+DT*b/2, *actual, effective, faults)
        d = dynamics(state+DT*c, *actual, effective, faults)
        state += DT*(a+2*b+2*c+d)/6
        state[2] = wrap_angle(state[2])
        if not np.all(np.isfinite(state)):
            raise FloatingPointError('Nonfinite experimental trajectory')
    observed_max = max(abs(r['observed_y_m']) for r in observations)
    stop_reason = 'observed_guard' if enforced and triggered is not None else 'duration_complete'
    metadata = {'mode': mode, 'guard_intervened': enforced and triggered is not None,
                'would_guard_trigger_s': triggered, 'stop_reason': stop_reason, 'guard_time_s': triggered,
                'observed_max_y_m': observed_max, 'observed_excursion': observed_max > CORRIDOR,
                'elapsed_s': observations[-1]['time_s'], 'fallback': 'zero commands with continued integration' if enforced else 'none; monitoring only',
                'fallback_safety': 'unverified', 'stopped_vehicle': 'not observable from available channels',
                'failure': 'observed_corridor_excursion' if observed_max > CORRIDOR else 'safe_fallback_unestablished' if enforced and triggered is not None else None,
                'fit_end_exclusive_s': min(trial.duration_s, triggered if enforced and triggered is not None else trial.duration_s)}
    private = {'true_excursion': any(abs(r['y_m']) > CORRIDOR for r in truth),
               'true_final_speed_mps': truth[-1]['speed_mps'], 'truth': truth}
    return observations, metadata, private


class SafeBackend:
    def __init__(self, *, faults=Faults(), plant=PlantConfig(), controller=Controller(), seed=0, mode='simulation_advisory'):
        if mode not in MODES: raise ValueError('Unknown simulation policy')
        validate(Vehicle(), faults, controller, Mission(), plant)
        self._mode = mode
        self._faults, self._plant, self._controller, self._seed = faults, plant, controller, seed
        self._count, self._time = 0, 0.
        self._used = set()
        self.private_results = []

    @property
    def mode(self):
        return self._mode

    @property
    def tail_reserve_s(self):
        return TAIL_S if self.mode == 'simulation_enforced' else 0.

    def execute(self, trial):
        trial = parse_trial(trial.name, trial.params())
        safety = screen(trial)
        safety = advisory_report(safety, self.mode)
        if not safety['accepted'] and self.mode == 'simulation_enforced':
            return {'accepted': False, 'constraint': 'predictive_envelope', 'safety': safety}
        cost = trial.duration_s + self.tail_reserve_s
        if self._count >= 3 or self._time+cost > 48 or trial.key in self._used:
            raise ValueError('Backend resource limit')
        self._count += 1
        self._time += cost
        self._used.add(trial.key)
        seed = self._seed + int(trial.key[:8], 16)
        rows, metadata, private = guarded_trial(trial, self._faults, self._plant, self._controller, seed, mode=self.mode)
        self.private_results.append(private)
        return {'accepted': True, 'observations': rows, 'execution': metadata, 'safety': safety}


def advisory_report(safety, mode):
    return {**safety, 'mode': mode, 'would_reject_enforced': not safety['accepted'],
            'exceedance_m': max(0., safety.get('ensemble_max_y_m', 0.) + safety.get('noise_allowance_m', 0.) - safety.get('limit_m', 1.1)),
            'risk': 'elevated' if not safety['accepted'] else 'within_sampled_envelope',
            'warnings': ['Predicted containment uncertain or exceeded; advisory mode permits offline execution.'] if not safety['accepted'] else [],
            'prediction_scope': 'Existing enforced-policy ensemble, including its guard and drift tail; not a forecast of the unguarded advisory trajectory.'}
