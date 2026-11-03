"""Isolated experimental controller variant.

This module exists only so the restricted patch lab has a small, well-defined
target. The trusted simulator never imports it; `nautilus.simulator.command`
remains the only control law that can affect a recorded evaluation. Its default
behaviour is unit-tested for exact equivalence with the simulator's command law.
"""
from __future__ import annotations

import math


def wrap_angle(value: float) -> float:
    return math.atan2(math.sin(value), math.cos(value))


def command(observed_y, observed_heading, observed_yaw_rate, vehicle, controller):
    wanted = math.atan2(-observed_y, controller.lookahead_m)
    wanted = max(-controller.max_heading_rad, min(controller.max_heading_rad, wanted))
    error = wrap_angle(wanted - observed_heading)
    moment = controller.heading_kp * error - controller.heading_kd * observed_yaw_rate
    port = controller.cruise_thrust - moment / (2 * vehicle.lever_arm)
    starboard = controller.cruise_thrust + moment / (2 * vehicle.lever_arm)
    limit = vehicle.max_thrust
    return (max(-limit, min(limit, port)), max(-limit, min(limit, starboard)), wanted)
