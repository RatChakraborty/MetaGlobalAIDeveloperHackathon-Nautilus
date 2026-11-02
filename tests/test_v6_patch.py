import difflib
import json
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys

import pytest

import nautilus.v6.patch as patch
from nautilus.simulator import Controller, Vehicle, command as classical_command
from nautilus.v6 import controller_variant

SOURCE = Path(patch.__file__).with_name('controller_variant.py').read_text()
HEADERS = ('--- a/nautilus/v6/controller_variant.py\n', '+++ b/nautilus/v6/controller_variant.py\n')


def diff_for(original: str, updated: str) -> str:
    body = list(difflib.unified_diff(original.splitlines(True), updated.splitlines(True), n=3))
    return ''.join(HEADERS) + ''.join(body[2:])


def small_change() -> str:
    return diff_for(SOURCE, SOURCE.replace('moment = controller.heading_kp * error',
                                           'moment = controller.heading_kp * error * 1.05'))


@dataclass
class Completed:
    returncode: int = 0
    stdout: str = ''
    stderr: str = ''


def payload(outputs=(13., 13., 0.)):
    return json.dumps({'network': 'blocked', 'filesystem': 'blocked',
                       'rows': [{'inputs': {'y': 0., 'heading': 0., 'rate': 0.}, 'outputs': list(outputs),
                                 'deterministic': True} for _ in range(4)]})


def test_isolated_variant_matches_the_trusted_command_law():
    vehicle, controller = Vehicle(), Controller()
    for y in (-2., -.4, 0., .7, 2.4):
        for heading in (-.6, -.1, 0., .3, .8):
            for rate in (-.2, 0., .15):
                expected = classical_command(y, heading, rate, vehicle, controller)
                actual = controller_variant.command(y, heading, rate, vehicle, controller)
                assert actual[0] == pytest.approx(expected[0], abs=1e-12)
                assert actual[1] == pytest.approx(expected[1], abs=1e-12)
                assert actual[2] == pytest.approx(expected[2], abs=1e-12)
    for extreme in (50., -50.):
        outputs = controller_variant.command(extreme, 0., 0., vehicle, controller)
        assert all(-45. <= value <= 45. for value in outputs[:2])
        assert classical_command(extreme, 0., 0., vehicle, controller)[:2] == pytest.approx(outputs[:2])


def test_patch_applies_only_to_the_approved_module():
    patched = patch.apply_patch(small_change())
    assert patched.count('* 1.05') == 1
    assert patched.splitlines()[:-1] == SOURCE.splitlines()[:-1] or len(patched.splitlines()) == len(SOURCE.splitlines())
    assert patch.structural_checks(patched)


@pytest.mark.parametrize('mutate,message', [
    (lambda d: d.replace('b/nautilus/v6/controller_variant.py', 'b/nautilus/simulator.py'), 'approved controller function module'),
    (lambda d: d.replace('+++ b/nautilus/v6/controller_variant.py', '+++ b/tests/test_simulator.py'), 'approved controller function module'),
    (lambda d: d + '+import os\n', 'forbidden construct'),
    (lambda d: d + '+subprocess.run(["ls"])\n', 'forbidden construct'),
    (lambda d: d.replace(' limit = vehicle.max_thrust', ' limit = 1e9'), 'actuator bound'),
])
def test_patch_scope_rules_reject_unsafe_edits(mutate, message):
    with pytest.raises(ValueError, match=message):
        patch.validate_patch(mutate(small_change()))
    with pytest.raises(ValueError):
        patch.apply_patch(mutate(small_change()))


def test_oversized_patches_and_context_mismatch_are_rejected():
    many = diff_for(SOURCE, SOURCE.replace('def wrap_angle', '\n' * 45 + 'def wrap_angle'))
    with pytest.raises(ValueError, match='larger than the approved scope'):
        patch.validate_patch(many)
    wrong = small_change().replace(' wanted = math.atan2(-observed_y, controller.lookahead_m)',
                                   ' wanted = math.atan2(observed_y, controller.lookahead_m)')
    with pytest.raises(ValueError, match='context does not match'):
        patch.apply_patch(wrong)
    with pytest.raises(ValueError):
        patch.validate_patch('not a diff')


def test_structural_checks_reject_a_changed_signature_or_missing_bound():
    longer = SOURCE.replace('def command(observed_y, observed_heading, observed_yaw_rate, vehicle, controller):',
                            'def command(observed_y, observed_heading, observed_yaw_rate, vehicle, controller, extra):')
    with pytest.raises(ValueError, match='signature'):
        patch.structural_checks(longer)
    unbounded = SOURCE.replace('max(-limit, min(limit, port))', 'port').replace('max(-limit, min(limit, starboard))', 'starboard')
    with pytest.raises(ValueError):
        patch.structural_checks(unbounded)


def test_sandbox_status_requires_a_confirming_guard(monkeypatch):
    assert patch.sandbox_status(lambda *a, **k: Completed(stdout='{"blocked": true}'))['available'] is True
    open_guard = patch.sandbox_status(lambda *a, **k: Completed(stdout='{"blocked": false}'))
    assert open_guard['available'] is False and 'self-test' in open_guard['reason']
    monkeypatch.setattr(patch.sys, 'platform', 'win32')
    assert patch.sandbox_status()['available'] is False


def test_review_is_diff_only_by_default(monkeypatch):
    monkeypatch.delenv(patch.FEATURE_FLAG, raising=False)
    record = patch.review(small_change())
    assert record['status'] == 'review_only'
    assert record['certified'] is False
    assert record['sandbox']['available'] is False
    assert record['diff'].startswith('--- a/nautilus/v6/controller_variant.py')


def test_flag_without_a_trustworthy_sandbox_never_executes(monkeypatch):
    monkeypatch.setenv(patch.FEATURE_FLAG, '1')
    monkeypatch.setattr(patch, 'sandbox_status', lambda runner=None: {'available': False, 'reason': 'guard self-test did not confirm denial'})
    record = patch.review(small_change(), runner=lambda *a, **k: Completed())
    assert record['status'] == 'unavailable'
    assert any('execution unavailable' in note.lower() for note in record['notes'])


def test_timeout_and_guard_failure_are_recorded_without_results(monkeypatch):
    monkeypatch.setenv(patch.FEATURE_FLAG, '1')
    monkeypatch.setattr(patch, 'sandbox_status', lambda runner=None: {'available': True, 'certified': False})

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('harness', 1)

    record = patch.review(small_change(), runner=timeout)
    assert record['status'] == 'unavailable'
    assert any('timed out' in note for note in record['notes'])

    blocked = patch.review(small_change(), runner=lambda *a, **k: Completed(stdout=payload()))
    assert blocked['status'] == 'executed' and blocked['certified'] is False
    assert any('not certified isolation' in note for note in blocked['notes'])

    open_network = patch.review(small_change(), runner=lambda *a, **k: Completed(stdout=payload()))
    assert open_network['status'] == 'executed'
    escaped = patch.review(small_change(), runner=lambda *a, **k: Completed(
        stdout=json.dumps({'network': 'open', 'filesystem': 'blocked', 'rows': []})))
    assert escaped['status'] == 'unavailable'
    unbounded = patch.review(small_change(), runner=lambda *a, **k: Completed(stdout=payload(outputs=(999., 13., 0.))))
    assert unbounded['status'] == 'unavailable'
