"""Request validation for public API inputs.

Only the public knobs below are accepted. Every other key is rejected, so a client
cannot supply hidden plant parameters, oracle values or evaluator keys.
"""
import math

from nautilus.simulator import Faults, Mission

SCENARIO_KEYS = {"current_y", "port_efficiency", "starboard_efficiency", "heading_bias_rad"}
RANGES = {
    "current_y": (-2.5, 2.5),
    "port_efficiency": (0.1, 1.0),
    "starboard_efficiency": (0.1, 1.0),
    "heading_bias_rad": (-0.8, 0.8),
}
MISSION_DURATION_S = (2.0, 45.0)
SEED_RANGE = (0, 2**31 - 1)


class RequestError(ValueError):
    pass


def _number(value, name, lo, hi):
    if type(value) not in (int, float) or not math.isfinite(value) or not lo <= value <= hi:
        raise RequestError(f"{name} must be a number in [{lo}, {hi}]")
    return float(value)


def scenario(body):
    if not isinstance(body, dict):
        raise RequestError("Request body must be a JSON object")
    unknown = set(body) - {"scenario", "seed", "duration_s"}
    if unknown:
        raise RequestError(f"Unknown fields: {sorted(unknown)}")
    raw = body.get("scenario", {})
    if not isinstance(raw, dict) or set(raw) - SCENARIO_KEYS:
        raise RequestError("scenario accepts only: " + ", ".join(sorted(SCENARIO_KEYS)))
    values = {k: _number(raw.get(k, 1.0 if k.endswith("efficiency") else 0.0), k, *RANGES[k])
              for k in SCENARIO_KEYS}
    seed = body.get("seed", 42)
    if type(seed) is not int or not SEED_RANGE[0] <= seed <= SEED_RANGE[1]:
        raise RequestError("seed must be an integer")
    duration = _number(body.get("duration_s", 45.0), "duration_s", *MISSION_DURATION_S)
    faults = Faults(current_y=values["current_y"], port_efficiency=values["port_efficiency"],
                    starboard_efficiency=values["starboard_efficiency"],
                    heading_bias_rad=values["heading_bias_rad"])
    mission = Mission(duration_s=duration, dt_s=0.05, cable_length_m=30.0,
                      cable_half_width_m=1.5, seed=seed)
    return faults, mission, {"scenario": values, "seed": seed, "duration_s": duration}
