from dataclasses import replace

import pytest

from nautilus.controller_context import build_controller_context
from nautilus.simulator import Controller
from nautilus.v6 import build_policy, candidate, differences, identity, validate_policy
from nautilus.v6.policy import TUNABLE


def test_policy_contract_is_versioned_and_matches_the_trusted_source():
    policy = build_policy(Controller())
    assert policy['schema_version'] == 'nautilus.control-policy.v1'
    assert policy['source']['sha256'] == build_controller_context(Controller())['source']['sha256']
    assert policy['source']['inspection_status'] == 'supported'
    assert policy['actuator']['max_thrust_n'] == 45. and policy['actuator']['lever_arm_m'] == .32
    assert policy['execution']['deterministic'] is True
    assert policy['interface']['commands'] == ['port_command_n', 'starboard_command_n']
    assert [name for name in policy['parameters'] if policy['parameters'][name]['tunable']] == list(TUNABLE)
    assert 'learned or neural control policies' in policy['unsupported']
    assert validate_policy(policy) == policy
    assert build_policy(Controller()) == policy


def test_policy_rejects_tampering_and_unsupported_sources():
    policy = build_policy(Controller())
    tampered = {**policy, 'parameters': {**policy['parameters'], 'lookahead_m': {**policy['parameters']['lookahead_m'], 'value': 3.}}
                }
    with pytest.raises(ValueError, match='hash mismatch'):
        validate_policy(tampered)
    unsupported = {**policy, 'source': {**policy['source'], 'inspection_status': 'unsupported'}}
    with pytest.raises(ValueError, match='Approved controller source required'):
        validate_policy(unsupported)
    foreign = {**policy, 'source': {**policy['source'], 'path': 'nautilus/other.py'}}
    with pytest.raises(ValueError):
        validate_policy(foreign)
    widened = {**policy, 'parameters': {**policy['parameters'], 'heading_kp': {**policy['parameters']['heading_kp'], 'bounds': [0., 99.]}}}
    with pytest.raises(ValueError, match='contract changed'):
        validate_policy(widened)
    for key in ('actuator', 'execution', 'interface', 'unsupported'):
        with pytest.raises(ValueError):
            validate_policy({**policy, key: {}})


def test_candidate_respects_bounds_and_no_op_equivalence():
    baseline = Controller()
    assert candidate(baseline, {'lookahead_m': 7.}) == baseline
    assert candidate(baseline, {'lookahead_m': 3., 'cruise_thrust': 15.}) == replace(baseline, lookahead_m=3., cruise_thrust=15.)
    for changes in ({}, {'lookahead_m': 1.}, {'heading_kp': 500.}, {'heading_kd': -1.}, {'unused': 1.},
                    {'heading_kp': float('nan')}, {'heading_kp': float('inf')}, {'cruise_thrust': True},
                    {'lookahead_m': '3'}, None, ['lookahead_m']):
        with pytest.raises(ValueError):
            candidate(baseline, changes)


def test_differences_are_approved_and_typed():
    policy = build_policy(Controller())
    assert differences(policy, Controller()) == {}
    edited = differences(policy, Controller(lookahead_m=3.))
    assert edited == {'lookahead_m': {'baseline': 7., 'candidate': 3., 'unit': 'm'}}
    with pytest.raises(ValueError):
        build_policy(Controller(max_heading_rad=2.))  # outside the approved declared bounds
    identity_value = identity(policy)
    assert identity_value['source_sha256'] == policy['source']['sha256']
    assert len(identity_value['configuration_id']) == 64
    assert identity(build_policy(Controller()))['configuration_id'] == identity_value['configuration_id']
    assert identity(build_policy(Controller(lookahead_m=3.)))['configuration_id'] != identity_value['configuration_id']
