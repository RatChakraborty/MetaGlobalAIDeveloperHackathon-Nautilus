import difflib
from pathlib import Path

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
    defaulted = SOURCE.replace('def command(observed_y, observed_heading, observed_yaw_rate, vehicle, controller):',
                               'def command(observed_y, observed_heading, observed_yaw_rate, vehicle, controller=None):')
    with pytest.raises(ValueError):
        patch.structural_checks(defaulted)
    unbounded = SOURCE.replace('max(-limit, min(limit, port))', 'port').replace('max(-limit, min(limit, starboard))', 'starboard')
    with pytest.raises(ValueError):
        patch.structural_checks(unbounded)


def test_review_is_always_static_and_never_executes():
    record = patch.review(small_change())
    assert record['status'] == 'review_only'
    assert record['certified'] is False
    assert record['sandbox']['available'] is False
    assert record['sandbox']['execution'] == 'unavailable'
    assert record['diff'].startswith('--- a/nautilus/v6/controller_variant.py')
    assert [check['check'] for check in record['checks']] == [
        'syntax', 'single_target_function', 'signature_unchanged', 'actuator_bound_retained',
        'return_contract', 'no_imports']
    assert any('not executed' in note for note in record['notes'])
    assert patch.EXECUTION == 'unavailable'


def test_the_module_contains_no_execution_machinery():
    import ast
    source = Path(patch.__file__).read_text()
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or '')
    assert imported <= {'__future__', 'ast', 'pathlib', 're'}
    calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert not calls & {'eval', 'exec', 'compile', '__import__'}
    for token in ('subprocess.run(', 'tempfile.', 'setrlimit', 'sitecustomize', 'os.system(', 'socket.socket'):
        assert token not in source
    for removed in ('sandbox_status', 'enabled', 'FEATURE_FLAG', '_limits', 'HARNESS'):
        assert not hasattr(patch, removed)
