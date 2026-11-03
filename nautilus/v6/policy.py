"""Versioned, closed description of the approved control policy.

The policy contract is descriptive: it records what the trusted controller
actually does, which parameters may be varied, and which behaviours are out of
scope. It never re-implements or replaces the simulator.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import math

from ..controller_context import PARAMETERS, build_controller_context, canonical, configuration, fingerprint
from ..simulator import Controller, Vehicle

SCHEMA = 'nautilus.control-policy.v1'
POLICY_ID = 'nautilus.classical.v1'
TUNABLE = ('lookahead_m', 'heading_kp', 'heading_kd', 'cruise_thrust')
UNSUPPORTED = (
    'learned or neural control policies',
    'stateful integrators or adaptive gain scheduling',
    'measured force, surge-speed or x-position feedback',
    'six-degree-of-freedom or depth control',
    'runtime code loading, uploaded checkpoints or arbitrary callables',
    'changes to vehicle dynamics, actuator model, faults or mission geometry',
)
DETERMINISM = (
    'The command law is a pure function of the supplied observation sample and declared parameters.',
    'The host supplies the integration step; the controller never advances physics or holds hidden state.',
    'Sensor noise seeds are owned by the trusted host and are identical for a matched baseline/candidate pair.',
)


def _body(controller):
    context = build_controller_context(controller)
    if context['source']['inspection_status'] != 'supported':
        raise ValueError('Approved controller implementation required')
    approved = configuration(controller)
    vehicle = Vehicle()
    return {
        'schema_version': SCHEMA,
        'policy_id': POLICY_ID,
        'policy_type': context['controller_type'],
        'implementation_version': context['implementation_version'],
        'source': {'path': context['source']['path'], 'sha256': context['source']['sha256'],
                   'inspection_status': context['source']['inspection_status'],
                   'revision': context['source']['revision']},
        'parameters': {name: {'value': approved[name]['value'], 'unit': approved[name]['unit'],
                              'bounds': list(approved[name]['bounds']), 'tunable': name in TUNABLE}
                       for name in PARAMETERS},
        'interface': {'observations': list(context['interface']['inputs']),
                      'observation_units': list(context['interface']['input_units']),
                      'commands': list(context['interface']['actions']),
                      'command_units': list(context['interface']['action_units']),
                      'statefulness': context['interface']['statefulness'],
                      'initialization': 'No controller state is allocated; every call starts from the declared parameters.',
                      'reset': 'Equivalent to discarding the previous sample; no accumulated state exists to reset.'},
        'actuator': {'max_thrust_n': vehicle.max_thrust, 'lever_arm_m': vehicle.lever_arm,
                     'saturation': 'each command is clipped to +/- max_thrust_n before allocation',
                     'measured_force_feedback': False},
        'execution': {'deterministic': True, 'tunable_parameters': list(TUNABLE), 'notes': list(DETERMINISM)},
        'unsupported': list(UNSUPPORTED),
    }


def build_policy(controller: Controller = Controller()) -> dict:
    body = _body(controller)
    return validate_policy({**body, 'policy_hash': fingerprint(body)})


def policy_hash(policy: dict) -> str:
    return policy['policy_hash']


def validate_policy(value: dict) -> dict:
    if type(value) is not dict:
        raise ValueError('Control policy object required')
    expected = {'schema_version', 'policy_id', 'policy_type', 'implementation_version', 'source',
                'parameters', 'interface', 'actuator', 'execution', 'unsupported', 'policy_hash'}
    if set(value) != expected or value['schema_version'] != SCHEMA or value['policy_id'] != POLICY_ID:
        raise ValueError('Unsupported control policy')
    if value['policy_type'] != 'classical':
        raise ValueError('Only the classical policy is approved')
    for key in ('implementation_version',):
        if type(value[key]) is not str or not value[key]:
            raise ValueError('Invalid policy identity')
    source = value['source']
    if type(source) is not dict or set(source) != {'path', 'sha256', 'inspection_status', 'revision'}:
        raise ValueError('Invalid policy source')
    if source['path'] != 'nautilus/simulator.py' or source['inspection_status'] != 'supported':
        raise ValueError('Approved controller source required')
    if type(source['sha256']) is not str or len(source['sha256']) != 64 or any(c not in '0123456789abcdef' for c in source['sha256']):
        raise ValueError('Invalid source fingerprint')
    if source['revision'] is not None and (type(source['revision']) is not str or len(source['revision']) not in (40, 64)):
        raise ValueError('Invalid source revision')
    parameters = value['parameters']
    if type(parameters) is not dict or set(parameters) != set(PARAMETERS):
        raise ValueError('Invalid policy parameters')
    for name, (unit, low, high) in PARAMETERS.items():
        item = parameters[name]
        if type(item) is not dict or set(item) != {'value', 'unit', 'bounds', 'tunable'}:
            raise ValueError('Invalid policy parameter')
        if item['unit'] != unit or item['bounds'] != [low, high] or item['tunable'] is not (name in TUNABLE):
            raise ValueError('Policy parameter contract changed')
        if type(item['value']) not in (int, float) or not math.isfinite(item['value']) or not low <= item['value'] <= high:
            raise ValueError('Declared parameter outside approved bounds')
    interface = value['interface']
    if type(interface) is not dict or set(interface) != {'observations', 'observation_units', 'commands', 'command_units', 'statefulness', 'initialization', 'reset'}:
        raise ValueError('Invalid policy interface')
    if interface['observations'] != ['observed_y_m', 'observed_heading_rad', 'observed_yaw_rate_radps'] or interface['observation_units'] != ['m', 'rad', 'rad/s']:
        raise ValueError('Policy observation contract changed')
    if interface['commands'] != ['port_command_n', 'starboard_command_n'] or interface['command_units'] != ['N', 'N']:
        raise ValueError('Policy command contract changed')
    actuator = value['actuator']
    if type(actuator) is not dict or set(actuator) != {'max_thrust_n', 'lever_arm_m', 'saturation', 'measured_force_feedback'}:
        raise ValueError('Invalid actuator contract')
    vehicle = Vehicle()
    if actuator['max_thrust_n'] != vehicle.max_thrust or actuator['lever_arm_m'] != vehicle.lever_arm or actuator['measured_force_feedback'] is not False:
        raise ValueError('Actuator contract must match the trusted vehicle')
    execution = value['execution']
    if type(execution) is not dict or set(execution) != {'deterministic', 'tunable_parameters', 'notes'}:
        raise ValueError('Invalid execution contract')
    if execution['deterministic'] is not True or execution['tunable_parameters'] != list(TUNABLE) or execution['notes'] != list(DETERMINISM):
        raise ValueError('Execution contract changed')
    if value['unsupported'] != list(UNSUPPORTED):
        raise ValueError('Unsupported-behaviour declaration changed')
    if type(value['policy_hash']) is not str or fingerprint({k: v for k, v in value.items() if k != 'policy_hash'}) != value['policy_hash']:
        raise ValueError('Control policy hash mismatch')
    return deepcopy(value)


def candidate(controller: Controller, changes: dict) -> Controller:
    """Return a controller with wholesale validated parameter values applied."""
    if type(changes) is not dict or not changes or set(changes) - set(TUNABLE):
        raise ValueError('Only approved tunable parameters may change')
    for name, value in changes.items():
        low, high = PARAMETERS[name][1:3]
        if type(value) not in (int, float) or type(value) is bool or not math.isfinite(value) or not low <= value <= high:
            raise ValueError('Candidate value outside approved bounds')
    updated = replace(controller, **changes)
    configuration(updated)
    return updated


def differences(policy: dict, controller: Controller) -> dict:
    """Approved differences between the policy's declared values and a candidate."""
    approved = validate_policy(policy)['parameters']
    out = {}
    for name in TUNABLE:
        base, value = approved[name]['value'], float(getattr(controller, name))
        if value != base:
            out[name] = {'baseline': base, 'candidate': value, 'unit': approved[name]['unit']}
    return out


def identity(policy: dict) -> dict:
    policy = validate_policy(policy)
    return {'policy_id': policy['policy_id'], 'implementation_version': policy['implementation_version'],
            'source_sha256': policy['source']['sha256'], 'policy_hash': policy['policy_hash'],
            'configuration_id': fingerprint({name: item['value'] for name, item in policy['parameters'].items()})}


def canonical_policy(policy: dict) -> str:
    return canonical(validate_policy(policy))
