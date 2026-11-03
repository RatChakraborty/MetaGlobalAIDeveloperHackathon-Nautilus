"""Bounded controller intermediate representation (IR).

A policy is a JSON-serialisable tree of operations over a fixed set of public
inputs. It is interpreted by this module only: there is no `exec`, no `eval`,
no imports, no filesystem, network, environment or simulator-state access.
Every evaluation is bounded by explicit limits (node count, expression depth,
and output finiteness), and the interpreter is deterministic.

Inputs (public observation channels and the controller's own parameters):
    y_m            observed cross-track position (m)
    heading_rad    observed heading (rad)
    yaw_rate_radps observed yaw rate (rad/s)
    lookahead_m, max_heading_rad, cruise_thrust_n, max_thrust_n (constants)

Outputs: `port_n` and `starboard_n` thrust commands (N), validated as finite
and clipped to +/- max_thrust_n by the interpreter.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

SCHEMA = 'nautilus.policy-ir.v1'
MAX_NODES = 96
MAX_DEPTH = 14
INPUTS = ('y_m', 'heading_rad', 'yaw_rate_radps', 'integral_y', 'integral_limit_m', 'filtered_yaw_rate')
CONSTANTS = ('lookahead_m', 'max_heading_rad', 'cruise_thrust_n', 'max_thrust_n', 'lever_arm_m')
BINARY = ('add', 'sub', 'mul', 'div', 'min', 'max', 'lt', 'gt', 'atan2')
UNARY = ('neg', 'abs', 'sat', 'wrap_angle')
PARAM_LIMITS = {'heading_kp': (0.0, 200.0), 'heading_kd': (0.0, 200.0), 'integral_ki': (0.0, 50.0),
                'integral_limit': (0.0, 5.0), 'yaw_filter_alpha': (0.0, 1.0)}

class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class Context:
    y_m: float
    heading_rad: float
    yaw_rate_radps: float
    lookahead_m: float
    max_heading_rad: float
    cruise_thrust_n: float
    max_thrust_n: float
    lever_arm_m: float
    integral_y: float = 0.0
    integral_limit_m: float = 0.5
    filtered_yaw_rate: float = 0.0


def _check_node(node, depth, counter):
    counter[0] += 1
    if counter[0] > MAX_NODES:
        raise PolicyError('policy exceeds node limit')
    if depth > MAX_DEPTH:
        raise PolicyError('policy exceeds depth limit')
    if type(node) in (int, float) and type(node) is not bool:
        if not math.isfinite(float(node)):
            raise PolicyError('non-finite constant')
        return
    if type(node) is str:
        if node not in INPUTS and node not in CONSTANTS:
            raise PolicyError(f'unknown reference: {node}')
        return
    if type(node) is not dict or set(node) - {'op', 'args', 'value', 'name'}:
        raise PolicyError('malformed node')
    op = node.get('op')
    args = node.get('args', [])
    if op == 'const':
        value = node.get('value')
        if type(value) not in (int, float) or type(value) is bool or not math.isfinite(float(value)):
            raise PolicyError('constant must be a finite number')
        return
    if op == 'param':
        if node.get('name') not in PARAM_LIMITS:
            raise PolicyError('unknown parameter')
        return
    if op in BINARY:
        if type(args) is not list or len(args) != 2:
            raise PolicyError(f'{op} takes two arguments')
    elif op in UNARY:
        if type(args) is not list or len(args) != 1:
            raise PolicyError(f'{op} takes one argument')
    elif op == 'if':
        if type(args) is not list or len(args) != 3:
            raise PolicyError('if takes condition, then, else')
    else:
        raise PolicyError(f'unsupported operation: {op}')
    for child in args:
        _check_node(child, depth + 1, counter)


def validate(policy: dict) -> dict:
    """Validate a policy document. Raises PolicyError on anything outside the subset."""
    if type(policy) is not dict or policy.get('schema') != SCHEMA:
        raise PolicyError('unsupported policy schema')
    if set(policy) - {'schema', 'name', 'port', 'starboard', 'params', 'desired_heading'}:
        raise PolicyError('unknown policy field')
    params = policy.get('params', {})
    if type(params) is not dict or set(params) - set(PARAM_LIMITS):
        raise PolicyError('unknown parameter')
    for key, value in params.items():
        lo, hi = PARAM_LIMITS[key]
        if type(value) not in (int, float) or type(value) is bool or not lo <= float(value) <= hi:
            raise PolicyError(f'parameter {key} outside [{lo}, {hi}]')
    counter = [0]
    for side in ('port', 'starboard', 'desired_heading'):
        if side == 'desired_heading' and side not in policy:
            continue
        if side not in policy:
            raise PolicyError(f'missing {side} expression')
        _check_node(policy[side], 0, counter)
    return policy


def _eval(node, ctx: Context, params: dict):
    if type(node) in (int, float):
        return float(node)
    if type(node) is str:
        return float(getattr(ctx, node))
    op = node['op']
    if op == 'const':
        return float(node['value'])
    if op == 'param':
        return float(params.get(node['name'], 0.0))
    args = node.get('args', [])
    if op == 'if':
        return _eval(args[1], ctx, params) if _eval(args[0], ctx, params) > 0 else _eval(args[2], ctx, params)
    vals = [_eval(child, ctx, params) for child in args]
    if op == 'add':
        return vals[0] + vals[1]
    if op == 'sub':
        return vals[0] - vals[1]
    if op == 'mul':
        return vals[0] * vals[1]
    if op == 'div':
        if vals[1] == 0.0:
            raise PolicyError('division by zero')
        return vals[0] / vals[1]
    if op == 'min':
        return min(vals)
    if op == 'max':
        return max(vals)
    if op == 'lt':
        return 1.0 if vals[0] < vals[1] else -1.0
    if op == 'gt':
        return 1.0 if vals[0] > vals[1] else -1.0
    if op == 'neg':
        return -vals[0]
    if op == 'abs':
        return abs(vals[0])
    if op == 'sat':
        return max(-ctx.max_thrust_n, min(ctx.max_thrust_n, vals[0]))
    if op == 'wrap_angle':
        return math.atan2(math.sin(vals[0]), math.cos(vals[0]))
    if op == 'atan2':
        return math.atan2(vals[0], vals[1])
    raise PolicyError(f'unsupported operation: {op}')


def evaluate(policy: dict, ctx: Context, params: dict | None = None) -> tuple[float, float]:
    """Stateless evaluation of one control step. Output is finite and clipped to actuator limits."""
    values = []
    bound = dict(policy.get('params', {}))
    bound.update(params or {})
    for side in ('port', 'starboard'):
        value = _eval(policy[side], ctx, bound)
        if not math.isfinite(value):
            raise PolicyError('non-finite controller output')
        values.append(max(-ctx.max_thrust_n, min(ctx.max_thrust_n, value)))
    return values[0], values[1]


def baseline_policy() -> dict:
    """The reference controller law from nautilus.simulator.command, expressed in the IR.

    desired heading = clip(atan2(-y, lookahead), +/- max_heading)
    moment = kp * (desired - heading) - kd * yaw_rate
    port/starboard = cruise -/+ moment / (2 * lever_arm), then clipped.
    """
    desired = {'op': 'max', 'args': [
        {'op': 'neg', 'args': ['max_heading_rad']},
        {'op': 'min', 'args': ['max_heading_rad', {'op': 'atan2', 'args': [
            {'op': 'neg', 'args': ['y_m']}, 'lookahead_m']}]}]}
    error = {'op': 'wrap_angle', 'args': [{'op': 'sub', 'args': [desired, 'heading_rad']}]}
    moment = {'op': 'sub', 'args': [
        {'op': 'sub', 'args': [
            {'op': 'mul', 'args': [{'op': 'param', 'name': 'heading_kp'}, error]},
            {'op': 'mul', 'args': [{'op': 'param', 'name': 'heading_kd'}, 'yaw_rate_radps']}]},
        {'op': 'mul', 'args': [{'op': 'param', 'name': 'integral_ki'}, 'integral_y']}]}
    half = {'op': 'mul', 'args': [{'op': 'const', 'value': 2.0}, 'lever_arm_m']}
    return validate({
        'schema': SCHEMA,
        'name': 'baseline',
        'params': {'heading_kp': 39.0, 'heading_kd': 18.0, 'integral_ki': 0.0, 'integral_limit': 0.5},
        'desired_heading': desired,
        'port': {'op': 'sub', 'args': ['cruise_thrust_n', {'op': 'div', 'args': [moment, half]}]},
        'starboard': {'op': 'add', 'args': ['cruise_thrust_n', {'op': 'div', 'args': [moment, half]}]},
    })
