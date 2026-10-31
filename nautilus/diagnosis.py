
from __future__ import annotations

from dataclasses import dataclass, field, replace
import math
import time
from typing import Mapping, Sequence

import numpy as np
from scipy.optimize import least_squares

from .simulator import (OBSERVATION_FIELDS, Faults, Vehicle, PlantConfig,
                        actuator_step, dynamics, wrap_angle, effective_vehicle)

CHANNELS = ("observed_y_m", "observed_heading_rad", "observed_yaw_rate_radps")

HYPOTHESES = {
    "nominal": None,
    "lateral_current": ("current_y", -1.0, 1.0),
    "port_degradation": ("port_efficiency", 0.1, 1.0),
    "starboard_degradation": ("starboard_efficiency", 0.1, 1.0),
    "heading_bias": ("heading_bias_rad", -0.8, 0.8),
}


DISCREPANCY_BOUNDS = (("actuator_tau_s", 0.0, 0.6),
                      ("thrust_deadzone_n", 0.0, 1.5),
                      ("drag_scale", 0.8, 1.2))


@dataclass(frozen=True)
class FitConfig:
    dt_s: float = 0.05

    scales: tuple[float, float, float] = (0.035, 0.004, 0.003)
    max_nfev: int = 60
    starts: int = 3
    end_s: float | None = None
    ambiguity_delta: float = 6.0
    inadequacy_wrms: float = 2.0

    method: str = "replay"


@dataclass
class FitResult:
    hypothesis: str
    parameters: dict[str, float]
    bounds: dict[str, tuple[float, float]]
    converged: bool
    status: str
    weighted_sse: float
    weighted_rmse: float
    penalized_score: float
    rmse: dict[str, float]
    channels: tuple[str, ...]
    fit_window_s: tuple[float, float]
    n_observations: int
    evaluations: int
    elapsed_s: float
    warnings: list[str]
    time_s: list[float] = field(repr=False)
    predictions: dict[str, list[float]] = field(repr=False)
    residuals: dict[str, list[float]] = field(repr=False)
    method: str = "replay"
    nuisance_parameters: dict[str, float] = field(default_factory=dict)
    nuisance_bounds: dict[str, tuple[float, float]] = field(default_factory=dict)
    episode_lengths: list[int] = field(default_factory=list)


@dataclass
class Diagnosis:
    fits: list[FitResult]
    competitive: list[str]
    ambiguous: bool
    inadequate: bool
    warnings: list[str]


def _prepare(observations, config):
    if (config.method not in ("replay", "observer", "observer_discrepancy")
            or not math.isfinite(config.dt_s) or not 0 < config.dt_s <= 0.2
            or len(config.scales) != 3
            or not np.all(np.isfinite(config.scales)) or min(config.scales) <= 0
            or config.max_nfev < 1 or config.starts < 1
            or not math.isfinite(config.ambiguity_delta) or config.ambiguity_delta < 0
            or not math.isfinite(config.inadequacy_wrms) or config.inadequacy_wrms <= 0
            or (config.end_s is not None and
                (not math.isfinite(config.end_s) or config.end_s <= 0))):
        raise ValueError("Invalid fitting configuration")
    if len(observations) < 3:
        raise ValueError("At least three reset-aligned observations are required")
    if any(set(row) != set(OBSERVATION_FIELDS) for row in observations):
        raise ValueError("Supply exactly the public observation fields; no truth or metadata")
    a = np.array([[row[k] for k in OBSERVATION_FIELDS] for row in observations], dtype=float)
    if not np.all(np.isfinite(a)):
        raise ValueError("Observations must be finite")
    if abs(a[0, 0]) > 1e-10 or np.any(np.diff(a[:, 0]) <= 0):
        raise ValueError("Trace must start at reset t=0 and have strictly increasing times")
    gaps = np.diff(a[:, 0])
    regular = np.isclose(gaps, config.dt_s, atol=1e-9, rtol=0)
    warnings = []
    if not np.all(regular):
        if not np.all(regular[:-1]) or gaps[-1] >= config.dt_s:
            raise ValueError("Missing or irregular samples: full command history is required")


        a = a[:-1]
        warnings.append("Final fractional-step observation excluded; endpoint x is unobserved.")
    if config.end_s is not None:
        a = a[a[:, 0] <= config.end_s + 1e-10]
    if len(a) < 3:
        raise ValueError("Fit window has fewer than three regular observations")
    return a, warnings


def _predict(a, vehicle, faults, method="replay", discrepancy=None):
    state = np.zeros(6)
    actual = np.zeros(2)
    plant = PlantConfig(**(discrepancy or {}))
    if discrepancy:
        vehicle = effective_vehicle(vehicle, plant)
    predicted = np.empty((len(a), 3))
    for i, row in enumerate(a):
        predicted[i] = (state[1], wrap_angle(state[2] + faults.heading_bias_rad), state[5])
        if i == len(a) - 1:
            break
        if method != "replay":



            state[1] = row[1]
            state[2] = wrap_angle(row[2] - faults.heading_bias_rad)
            state[5] = row[3]
        dt = a[i + 1, 0] - row[0]
        port, star = row[4:6]
        if discrepancy:
            actual = actuator_step(actual, np.array([port, star]), dt, plant)
            port, star = actual
        k1 = dynamics(state, port, star, vehicle, faults)
        k2 = dynamics(state + dt * k1 / 2, port, star, vehicle, faults)
        k3 = dynamics(state + dt * k2 / 2, port, star, vehicle, faults)
        k4 = dynamics(state + dt * k3, port, star, vehicle, faults)
        state += dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        state[2] = wrap_angle(state[2])
        if not np.all(np.isfinite(state)):
            raise FloatingPointError("Nonfinite diagnostic prediction")
    return predicted


def fit_hypothesis(
    observations: Sequence[Mapping[str, float]], hypothesis: str,
    *, vehicle: Vehicle = Vehicle(), config: FitConfig = FitConfig(),
) -> FitResult:

    if hypothesis not in HYPOTHESES:
        raise ValueError(f"Unknown hypothesis: {hypothesis}")
    started = time.perf_counter()
    a, warnings = _prepare(observations, config)
    return _fit_arrays([a], warnings, hypothesis, vehicle, config, started)


def fit_evidence(episodes, hypothesis, *, vehicle=Vehicle(), config=FitConfig(method="observer")):

    if not episodes:
        raise ValueError("At least one public episode is required")
    arrays, warnings = [], []
    for episode in episodes:
        a, notes = _prepare(episode, replace(config, end_s=None))
        arrays.append(a)
        warnings.extend(notes)
    return _fit_arrays(arrays, warnings, hypothesis, vehicle, config, time.perf_counter())


def _fit_arrays(arrays, warnings, hypothesis, vehicle, config, started):
    if hypothesis not in HYPOTHESES:
        raise ValueError(f"Unknown hypothesis: {hypothesis}")
    a = np.vstack(arrays)
    subsequent = np.ones(len(a), dtype=bool)
    subsequent[np.cumsum([0] + [len(x) for x in arrays[:-1]])] = False
    spec = HYPOTHESES[hypothesis]

    nuisance_specs = DISCREPANCY_BOUNDS if config.method == "observer_discrepancy" else ()
    specs = ([spec] if spec else []) + list(nuisance_specs)
    evaluations = 0

    def calculate(p):
        nonlocal evaluations
        evaluations += 1
        faults = Faults(**({spec[0]: float(p[0])} if spec else {}))
        nuisance = {s[0]: float(v) for s, v in zip(nuisance_specs, p[1:] if spec else p)}
        predicted = np.vstack([_predict(x, vehicle, faults, config.method, nuisance) for x in arrays])
        residual = predicted - a[:, 1:4]
        residual[:, 1] = np.arctan2(np.sin(residual[:, 1]), np.cos(residual[:, 1]))
        return predicted, residual

    def objective(p):
        scale = np.asarray(config.scales)
        residual = calculate(p)[1] / scale
        if config.method != "replay":



            residual[subsequent] /= math.sqrt(2)
        return residual.ravel()

    all_params = {}
    if specs:
        lower = np.array([s[1] for s in specs])
        upper = np.array([s[2] for s in specs])
        starts = [lower + fraction * (upper - lower)
                  for fraction in np.linspace(.1, .9, config.starts)]
        solutions = [least_squares(objective, s, bounds=(lower, upper),
                                   max_nfev=config.max_nfev, x_scale="jac") for s in starts]

        successful = [s for s in solutions if s.success]
        solution = min(successful or solutions, key=lambda s: s.cost)
        all_params = {s[0]: float(v) for s, v in zip(specs, solution.x)}
        params = {spec[0]: all_params[spec[0]]} if spec else {}
        bounds = {spec[0]: (spec[1], spec[2])} if spec else {}
        converged, status = bool(solution.success), str(solution.message)
        predicted, residual = calculate(solution.x)
        if np.any(np.minimum(solution.x - lower, upper - solution.x) < 1e-4 * (upper - lower)):
            warnings.append("Parameter at bound; fault family or operating bounds may be inadequate.")
        if spec and np.linalg.norm(solution.jac[:, 0]) < 1e-6:
            warnings.append("Locally insensitive parameter; recovery is not supported.")
    else:
        params, bounds, converged, status = {}, {}, True, "No free parameters"
        predicted, residual = calculate([])
    weighted = residual / np.asarray(config.scales)
    if config.method != "replay":
        weighted[subsequent] /= math.sqrt(2)
        warnings.append("Measured-state one-step innovations; not a free-running trajectory. "
                        "Approximate innovation scaling; temporal correlations are uncalibrated.")
    sse = float(np.sum(weighted ** 2))
    wrms = math.sqrt(sse / residual.size)
    if not converged:
        warnings.append("Optimizer did not converge; do not interpret this as a diagnosis.")
    if wrms > config.inadequacy_wrms:
        warnings.append("Residual exceeds configured noise tolerance; model mismatch or missing faults.")
    warnings.append("Conditional command replay; known zero reset required; current_x fixed to zero.")
    return FitResult(
        hypothesis, params, bounds, converged, status, sse, wrms,
        sse + len(specs) * math.log(residual.size),
        dict(zip(CHANNELS, np.sqrt(np.mean(residual ** 2, axis=0)).tolist())),
        CHANNELS, (0., max(float(x[-1, 0]) for x in arrays)), len(a), evaluations,
        time.perf_counter() - started, warnings, a[:, 0].tolist(),
        {c: predicted[:, i].tolist() for i, c in enumerate(CHANNELS)},
        {c: residual[:, i].tolist() for i, c in enumerate(CHANNELS)},
        config.method,
        {s[0]: all_params[s[0]] for s in nuisance_specs},
        {s[0]: (s[1], s[2]) for s in nuisance_specs},
        [len(x) for x in arrays],
    )


def diagnose(observations, *, hypotheses=tuple(HYPOTHESES),
             vehicle: Vehicle = Vehicle(), config: FitConfig = FitConfig()) -> Diagnosis:
    if not hypotheses or len(set(hypotheses)) != len(hypotheses):
        raise ValueError("Supply nonempty unique hypotheses")
    fits = sorted([fit_hypothesis(observations, h, vehicle=vehicle, config=config)
                   for h in hypotheses], key=lambda f: (not f.converged, f.penalized_score))
    valid = [f for f in fits if f.converged]
    competitive = [f.hypothesis for f in valid
                   if f.penalized_score <= valid[0].penalized_score + config.ambiguity_delta]
    inadequate = not valid or valid[0].weighted_rmse > config.inadequacy_wrms
    warnings = ["Scores are numerical comparisons, not posterior probabilities.",
                "A low residual or winning rank alone does not establish fault presence; "
                "model discrepancy and meaningful fault magnitudes are not calibrated.",
                "No observed x: longitudinal current and along-track recovery are untested."]
    if len(competitive) > 1:
        warnings.append("Several hypotheses fit similarly; further evidence is required.")
    if inadequate:
        warnings.append("No adequate converged model; abstain from a causal conclusion.")
    return Diagnosis(fits, competitive, len(competitive) > 1, inadequate, warnings)
