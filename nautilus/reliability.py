from dataclasses import replace
import time
import math
import numpy as np
from scipy.optimize import least_squares

from .diagnosis import _prepare, _predict, FitConfig
from .simulator import Vehicle, effective_vehicle
from .v2_models import REGISTRY, configs, commanded


NUISANCE = {'actuator_tau_s': (0., .25), 'thrust_deadzone_n': (0., .5),
            'drag_scale': (.9, 1.1)}
SCALES = np.array([.035, .004, .003])


def residual_diagnostics(residuals):
    result = []
    for residual in residuals:
        channels = []
        for column in residual.T:
            centered = column - column.mean()
            denominator = centered @ centered
            channels.append({'mean': float(column.mean()),
                             'rms': float(np.sqrt(np.mean(column**2))),
                             'lag1': float(centered[1:] @ centered[:-1] / denominator)
                             if denominator > 0 else None})
        result.append(channels)
    return result


def fit(episodes, hypothesis, *, method='nuisance', starts=2, max_nfev=60):
    if method not in ('nuisance', 'discrepancy'):
        raise ValueError('Unknown reliability method')
    if hypothesis not in REGISTRY or not episodes or starts not in (1, 2):
        raise ValueError('Invalid fitting request')
    spec = REGISTRY[hypothesis]
    parameters = {spec.parameter: spec.bounds} if spec.parameter else {}

    parameters.update({k: v for k, v in NUISANCE.items() if k != spec.parameter})
    if method == 'discrepancy':
        parameters['yaw_innovation_offset'] = (-.001, .001)
    names = list(parameters)
    lower, upper = np.array(list(parameters.values())).T
    arrays = [(_prepare(e['observations'], FitConfig(method='observer'))[0], e['experiment'])
              for e in episodes]
    calls = 0
    began = time.perf_counter()

    def calculate(p, details=False):
        nonlocal calls
        calls += 1
        values = dict(zip(names, p))
        faults, plant, controller = configs(hypothesis, float(values[spec.parameter]) if spec.parameter else None)
        plant = replace(plant, **{k: float(values[k]) for k in NUISANCE if k != spec.parameter})
        vehicle = effective_vehicle(Vehicle(), plant)
        residuals, controls, predictions = [], [], []
        for a, experiment in arrays:
            prediction = _predict(a, vehicle, faults, 'observer',
                                  {'actuator_tau_s': plant.actuator_tau_s,
                                   'thrust_deadzone_n': plant.thrust_deadzone_n})
            if method == 'discrepancy':
                prediction[1:, 2] += values['yaw_innovation_offset']
            delta = prediction - a[:, 1:4]
            delta[:, 1] = np.arctan2(np.sin(delta[:, 1]), np.cos(delta[:, 1]))
            delta /= SCALES
            delta[1:] /= math.sqrt(2)
            residuals.append(delta)
            controls.append((commanded(a, controller, experiment) - a[:, 4:6]) / .05)
            predictions.append(prediction.tolist())
        flat = np.concatenate([x.ravel() for x in residuals + controls])
        return (flat, residuals, controls, predictions) if details else flat

    solutions = [least_squares(calculate, lower + fraction*(upper-lower),
                               bounds=(lower, upper), x_scale='jac', max_nfev=max_nfev)
                 for fraction in ([.25, .75] if starts == 2 else [.5])]
    successful = [s for s in solutions if s.success]
    best = min(successful or solutions, key=lambda s: s.cost)
    residual, physical, controls, predictions = calculate(best.x, True)
    singular = np.linalg.svd(best.jac * (upper-lower), compute_uv=False)
    rank = int(np.sum(singular > max(singular[0]*1e-6, 1e-8)))
    physical_wrms = float(np.sqrt(np.mean(np.concatenate(physical)**2)))
    command_wrms = float(np.sqrt(np.mean(np.concatenate(controls)**2)))
    boundary = [n for n, x, lo, hi in zip(names, best.x, lower, upper)
                if min(x-lo, hi-x) < .001*(hi-lo)]
    return {'hypothesis': hypothesis, 'method': method,
            'parameters': dict(zip(names, map(float, best.x))), 'bounds': parameters,
            'converged': bool(best.success), 'optimizer_message': best.message,
            'wrms': max(physical_wrms, command_wrms),
            'physical_wrms': physical_wrms, 'command_wrms': command_wrms,
            'score': float(residual @ residual + len(names)*np.log(len(residual))),
            'parameter_count': len(names), 'bound_hits': boundary,
            'scaled_jacobian_singular_values': singular.tolist(), 'rank': rank,
            'condition': float(singular[0]/singular[-1]) if rank == len(names) else None,
            'residual_diagnostics': residual_diagnostics(physical),
            'predictions': predictions,
            'start_scores': [float(2*s.cost) for s in solutions],
            'evaluations': calls, 'elapsed_s': time.perf_counter()-began,
            'qualification': 'Conditional correlated innovations; scores are not probabilities. No calibrated covariance.'}


def diagnose(fits, *, prediction_failures=0):
    if not fits or any(not f['converged'] for f in fits):
        return {'status': 'OPTIMIZATION_FAILURE', 'selected': None}
    adequate = sorted([f for f in fits if f['wrms'] <= 2], key=lambda f: f['score'])
    if not adequate:
        structured = all(any(abs(c['mean']) > 1 and abs(c['lag1'] or 0) > .3
                             for episode in f['residual_diagnostics'] for c in episode) for f in fits)
        return {'status': 'SUSPECTED_UNKNOWN' if prediction_failures >= 2 and structured else 'MODEL_INADEQUATE',
                'selected': None, 'qualification': 'Family incompleteness is suspected, never proven; initialization and sensor assumptions require review.'}
    competitive = [f for f in adequate if f['score']-adequate[0]['score'] <= 6]
    best = adequate[0]
    supported = len(competitive) == 1 and best['rank'] == best['parameter_count'] and not best['bound_hits']
    return {'status': 'IDENTIFIED' if supported else 'AMBIGUOUS',
            'selected': best['hypothesis'] if supported else None,
            'competitive': [f['hypothesis'] for f in competitive],
            'qualification': 'Legacy gap6 retained; boundary/rank checks are conservative abstention rules, not calibrated confidence.'}
