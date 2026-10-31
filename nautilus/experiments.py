
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math

import numpy as np

from .diagnosis import CHANNELS, HYPOTHESES
from .simulator import (Controller, Experiment, Faults, Mission, PlantConfig,
                        Vehicle, simulate)


@dataclass(frozen=True)
class ExperimentRequest:
    cruise_thrust_n: float
    duration_s: float

    def __post_init__(self):
        if (not math.isfinite(self.cruise_thrust_n) or not 2 <= self.cruise_thrust_n <= 25
                or not math.isfinite(self.duration_s) or not 2 <= self.duration_s <= 30):
            raise ValueError("Permitted experiments require thrust 2..25 N and duration 2..30 s")

    @property
    def key(self):
        return f"thrust-{self.cruise_thrust_n:g}-duration-{self.duration_s:g}"


EXPERIMENT_LIBRARY = (ExperimentRequest(6., 10.), ExperimentRequest(22., 20.))


def forecast(fit, request, *, dt_s=.05):

    if not isinstance(request, ExperimentRequest):
        raise ValueError("Expected a bounded experiment request")
    spec = HYPOTHESES.get(fit.hypothesis)
    expected = {spec[0]} if spec else set()
    if fit.hypothesis not in HYPOTHESES or set(fit.parameters) != expected or not fit.converged:
        raise ValueError("Unsupported or nonconverged fitted hypothesis")
    if spec and not spec[1] <= fit.parameters[spec[0]] <= spec[2]:
        raise ValueError("Fitted parameter outside declared bounds")
    mission = Mission(duration_s=request.duration_s, dt_s=dt_s,
                      sensor_y_std_m=0., sensor_heading_std_rad=0.,
                      sensor_yaw_rate_std_radps=0., seed=0)
    return simulate(faults=Faults(**fit.parameters), mission=mission,
                    experiment=Experiment(request.cruise_thrust_n, request.duration_s)).observations


def separation(fits, request, *, scales=(.035, .004, .003),
               discrepancy=(.10, .03, .02), dt_s=.05):

    if len(fits) < 2:
        return 0.
    predictions = [forecast(f, request, dt_s=dt_s) for f in fits]
    n = min(map(len, predictions))
    scale = np.sqrt(2*np.asarray(scales)**2 + np.asarray(discrepancy)**2)
    if n < 2 or len(scale) != 3 or not np.all(np.isfinite(scale)) or np.any(scale <= 0):
        raise ValueError("Invalid forecast interval or separation scale")
    scores = []
    for i, a in enumerate(predictions):
        for b in predictions[i+1:]:


            if not np.allclose([r['time_s'] for r in a[:n]], [r['time_s'] for r in b[:n]]):
                raise ValueError("Forecasts are not time aligned")
            delta = np.array([[x[c]-y[c] for c in CHANNELS] for x,y in zip(a[1:n], b[1:n])])
            delta[:, 1] = np.arctan2(np.sin(delta[:, 1]), np.cos(delta[:, 1]))
            scores.append(float(np.sqrt(np.mean((delta/scale)**2))))
    return min(scores)


class HiddenExperimentBackend:

    def __init__(self, *, faults, controller, plant, seed, dt_s=.05,
                 budget=2, time_budget_s=30.):
        if (not isinstance(budget, int) or not 0 <= budget <= 2
                or not math.isfinite(time_budget_s) or not 0 <= time_budget_s <= 30
                or not math.isfinite(dt_s) or not 0 < dt_s <= .2):
            raise ValueError("Invalid experiment service limits")
        self._faults, self._controller, self._plant = faults, controller, plant
        self._seed, self._dt_s = seed, dt_s
        self._used = set()
        self._budget, self._time_budget_s = budget, time_budget_s
        self._spent = 0.

    def execute(self, request):
        if not isinstance(request, ExperimentRequest):
            raise ValueError("Only bounded experiment requests are accepted")
        if request.key in self._used or len(self._used) >= self._budget:
            raise ValueError("Repeated request or experiment count budget exhausted")
        if self._spent + request.duration_s > self._time_budget_s + 1e-9:
            raise ValueError("Experiment time budget exhausted")
        token = f"{self._seed}:{request.key}".encode()
        seed = int.from_bytes(hashlib.sha256(token).digest()[:8], "big")
        mission = Mission(duration_s=request.duration_s, dt_s=self._dt_s, seed=seed)
        rows = simulate(faults=self._faults, controller=self._controller,
                        plant=self._plant, mission=mission,
                        experiment=Experiment(request.cruise_thrust_n, request.duration_s)).observations
        self._used.add(request.key)
        self._spent += request.duration_s
        return rows
