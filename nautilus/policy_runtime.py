"""Stateful, bounded runtime for policy IR controllers.

The runtime owns all controller memory. Policies may reference the state terms
`integral_y` (bounded integral of cross-track error) and `filtered_yaw_rate`
(first-order low-pass of the observed yaw rate); they cannot create unbounded
state, and the update rules below are fixed and provably bounded:

    integral_y       <- clip(integral_y + dt * y_m, +/- integral_limit_m)
                        (not accumulated while the previous command saturated: anti-windup)
    filtered_yaw_rate <- alpha * yaw_rate + (1 - alpha) * filtered_yaw_rate

Every step returns finite, actuator-clipped thrust commands, or raises
PolicyError so the caller can record an execution failure.
"""
from __future__ import annotations

import math

from nautilus.policy_ir import Context, PolicyError, evaluate, validate

DEFAULT_PARAMS = {'integral_ki': 0.0, 'integral_limit': 0.5, 'yaw_filter_alpha': 1.0}
FILTER_ALPHA_LIMITS = (0.0, 1.0)


def params_for(policy: dict) -> dict:
    params = dict(DEFAULT_PARAMS)
    params.update(policy.get('params', {}))
    alpha = params.get('yaw_filter_alpha', 1.0)
    lo, hi = FILTER_ALPHA_LIMITS
    if type(alpha) not in (int, float) or type(alpha) is bool or not lo <= float(alpha) <= hi:
        raise PolicyError(f'yaw_filter_alpha outside [{lo}, {hi}]')
    return params


class PolicyController:
    """Executes a validated policy step by step against public observations only."""

    def __init__(self, policy: dict, dt_s: float = 0.05):
        self.policy = validate(policy)
        self.params = params_for(self.policy)
        self.dt_s = float(dt_s)
        if not math.isfinite(self.dt_s) or self.dt_s <= 0:
            raise PolicyError('invalid timestep')
        self.integral_y = 0.0
        self.filtered_yaw_rate = 0.0
        self.steps = 0
        self.saturated_steps = 0
        self.failure = None

    def reset(self):
        self.integral_y = 0.0
        self.filtered_yaw_rate = 0.0
        self.steps = 0
        self.saturated_steps = 0
        self.failure = None

    def __call__(self, t, observed_y, observed_heading, observed_yaw_rate, vehicle, controller):
        """Signature-compatible with nautilus.simulator.experiment_command."""
        return self.step(observed_y, observed_heading, observed_yaw_rate, vehicle, controller)

    def step(self, observed_y, observed_heading, observed_yaw_rate, vehicle, controller):
        alpha = float(self.params['yaw_filter_alpha'])
        self.filtered_yaw_rate = alpha * observed_yaw_rate + (1.0 - alpha) * self.filtered_yaw_rate
        limit = float(self.params['integral_limit'])
        integral = max(-limit, min(limit, self.integral_y + self.dt_s * observed_y))
        ctx = Context(
            y_m=float(observed_y),
            heading_rad=float(observed_heading),
            yaw_rate_radps=float(observed_yaw_rate),
            lookahead_m=float(controller.lookahead_m),
            max_heading_rad=float(controller.max_heading_rad),
            cruise_thrust_n=float(controller.cruise_thrust),
            max_thrust_n=float(vehicle.max_thrust),
            lever_arm_m=float(vehicle.lever_arm),
            integral_y=integral,
            integral_limit_m=limit,
            filtered_yaw_rate=float(self.filtered_yaw_rate),
        )
        port, starboard = evaluate(self.policy, ctx, self.params)
        self.steps += 1
        saturated = abs(port) >= vehicle.max_thrust or abs(starboard) >= vehicle.max_thrust
        if saturated:
            self.saturated_steps += 1
        else:
            self.integral_y = integral  # anti-windup: freeze the integrator while saturated
        # Desired heading is reported for plotting only; recomputed from the same law.
        try:
            desired = _desired_heading(self.policy, ctx, self.params)
        except PolicyError:
            desired = 0.0
        return port, starboard, desired


def _desired_heading(policy, ctx, params):
    node = policy.get('desired_heading')
    if node is None:
        return 0.0
    from nautilus.policy_ir import _eval  # local import keeps the public surface small
    return _eval(node, ctx, params)
