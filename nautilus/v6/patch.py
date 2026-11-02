"""Restricted controller-source patch lab (optional, disabled by default).

A generated diff is only ever *reviewed* unless the feature flag is set and a
sandbox self-test confirms that the in-process guard actually blocks network and
filesystem access. The runner uses a fresh process, stripped environment, rlimits,
a wall-clock timeout and an injected `sitecustomize` denial guard. It is not a
kernel namespace: `certified` stays false, and an executed patch never replaces
the trusted baseline.
"""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

TARGET_PATH = 'nautilus/v6/controller_variant.py'
TARGET_FUNCTION = 'command'
FEATURE_FLAG = 'NAUTILUS_CONTROLLER_PATCH_LAB'
MAX_BYTES = 4000
MAX_HUNKS = 2
MAX_ADDED_LINES = 40
FORBIDDEN = ('import ', '__', 'eval(', 'exec(', 'open(', 'socket', 'subprocess', 'os.system', 'os.environ',
             'os.remove', 'shutil', 'pathlib', 'urllib', 'requests', 'pickle', 'ctypes', 'sys.', 'globals(',
             'locals(', 'setattr(', 'while True', 'compile(', 'input(')
GUARD = '''"""Injected denial guard for the isolated patch runner."""
import builtins, os, socket

class SandboxDenied(OSError):
    pass

def _deny(*args, **kwargs):
    raise SandboxDenied('sandbox denies network and process access')

socket.socket = _deny
socket.create_connection = _deny
socket.socketpair = _deny
os.system = _deny
os.execv = _deny
os.fork = _deny
_real_open = builtins.open

def _open(file, mode='r', *args, **kwargs):
    path = str(file)
    if path.startswith(os.environ.get('NAUTILUS_SANDBOX_DIR', '\\0')) or path.startswith('<'):
        return _real_open(file, mode, *args, **kwargs)
    raise SandboxDenied('sandbox denies filesystem access outside the evaluation directory')

builtins.open = _open
'''
HARNESS = '''import json, math, os, sys

def probe():
    import socket
    try:
        socket.socket()
    except Exception:
        network = 'blocked'
    else:
        network = 'open'
    try:
        open('/etc/passwd')
    except Exception:
        filesystem = 'blocked'
    else:
        filesystem = 'open'
    return network, filesystem

def main():
    network, filesystem = probe()
    payload = json.load(open(os.path.join(os.environ['NAUTILUS_SANDBOX_DIR'], 'samples.json')))
    from controller_candidate import command
    class Holder:
        pass
    vehicle = Holder(); vehicle.lever_arm = payload['lever_arm']; vehicle.max_thrust = payload['max_thrust']
    controller = Holder()
    for key, value in payload['controller'].items():
        setattr(controller, key, value)
    rows = []
    for sample in payload['samples']:
        first = command(sample['y'], sample['heading'], sample['rate'], vehicle, controller)
        second = command(sample['y'], sample['heading'], sample['rate'], vehicle, controller)
        rows.append({'inputs': sample, 'outputs': list(first), 'deterministic': list(first) == list(second)})
    print(json.dumps({'network': network, 'filesystem': filesystem, 'rows': rows}))

main()
'''


def enabled() -> bool:
    return os.environ.get(FEATURE_FLAG, '').strip().lower() in ('1', 'true', 'yes')


def _check_target(diff: str):
    if type(diff) is not str or not diff.strip() or len(diff.encode()) > MAX_BYTES:
        raise ValueError('Bounded unified diff required')
    lines = diff.splitlines()

    def normalize(name: str) -> str:
        name = name.split('\t')[0].strip()
        return name[2:] if name[:2] in ('a/', 'b/') else name

    files = [line.split(None, 1)[-1] for line in lines if line.startswith(('--- ', '+++ '))]
    if len(files) < 2 or any(normalize(name) != TARGET_PATH for name in files):
        raise ValueError('Patch may only target the approved controller function module')
    if len([line for line in lines if line.startswith('@@')]) > MAX_HUNKS:
        raise ValueError('Patch touches too many regions')
    added = [line for line in lines if line.startswith('+') and not line.startswith('+++')]
    if len(added) > MAX_ADDED_LINES:
        raise ValueError('Patch is larger than the approved scope')
    body = '\n'.join(line for line in lines if not line.startswith(('--- ', '+++ ')))
    lowered = body.lower()
    for token in FORBIDDEN:
        if token in lowered:
            raise ValueError('Patch contains a forbidden construct: ' + token.strip())
    removed = [line for line in lines if line.startswith('-') and not line.startswith('---')]
    if any('max_thrust' in line for line in removed) and not any('max_thrust' in line for line in added):
        raise ValueError('Patch must retain the actuator bound')
    if 'max_thrust' not in body:
        raise ValueError('Patch must retain the actuator bound')
    return lines


def validate_patch(diff: str) -> list:
    """Validate patch scope without applying it."""
    return _check_target(diff)


def apply_patch(diff: str, source: str | None = None) -> str:
    lines = _check_target(diff)
    source = Path(source).read_text() if isinstance(source, (str, Path)) and source else \
        Path(__file__).with_name('controller_variant.py').read_text()
    target = source.splitlines()
    out, cursor = [], 0
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.startswith('@@'):
            index += 1
            continue
        match = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
        if not match:
            raise ValueError('Malformed patch hunk header')
        start, length = int(match.group(1)), int(match.group(2) or 1)
        if start - 1 < cursor:
            raise ValueError('Patch hunks overlap or are out of order')
        out.extend(target[cursor:start - 1])
        cursor = start - 1
        index += 1
        consumed = 0
        while index < len(lines) and not lines[index].startswith('@@'):
            entry = lines[index]
            if entry.startswith(' '):
                if cursor >= len(target) or target[cursor] != entry[1:]:
                    raise ValueError('Patch context does not match the approved module')
                out.append(target[cursor]); cursor += 1; consumed += 1
            elif entry.startswith('-'):
                if cursor >= len(target) or target[cursor] != entry[1:]:
                    raise ValueError('Patch removal does not match the approved module')
                cursor += 1; consumed += 1
            elif entry.startswith('+'):
                out.append(entry[1:])
            elif entry.strip() == '':
                pass
            else:
                raise ValueError('Unsupported patch line')
            index += 1
        if consumed != length:
            raise ValueError('Patch hunk length mismatch')
    out.extend(target[cursor:])
    return '\n'.join(out) + '\n'


def structural_checks(patched: str) -> list:
    try:
        tree = ast.parse(patched)
    except SyntaxError as exc:
        raise ValueError('Patched module does not parse') from exc
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if [node.name for node in functions] != ['wrap_angle', TARGET_FUNCTION]:
        raise ValueError('Patch may only change the approved controller function')
    target = functions[-1]
    if [arg.arg for arg in target.args.args] != ['observed_y', 'observed_heading', 'observed_yaw_rate', 'vehicle', 'controller']:
        raise ValueError('Patched function signature changed')
    if len(target.args.args) != len(target.args.args) or target.args.vararg or target.args.kwarg:
        raise ValueError('Patched function must keep a fixed signature')
    text = ast.dump(target)
    if 'max_thrust' not in text:
        raise ValueError('Patched function must retain the actuator bound')
    returns = [node for node in ast.walk(target) if isinstance(node, ast.Return)]
    if not returns or not isinstance(returns[-1].value, ast.Tuple) or len(returns[-1].value.elts) != 3:
        raise ValueError('Patched function must return the documented triple')
    if 'limit' not in ast.dump(returns[-1].value):
        raise ValueError('Patched function must bound returned commands')
    def imports(parsed):
        return [ast.dump(node) for node in ast.walk(parsed) if isinstance(node, (ast.Import, ast.ImportFrom))]

    approved = ast.parse(Path(__file__).with_name('controller_variant.py').read_text())
    if imports(tree) != imports(approved):
        raise ValueError('Patched module may not add imports')
    return [{'check': 'syntax', 'passed': True}, {'check': 'single_target_function', 'passed': True},
            {'check': 'signature_unchanged', 'passed': True}, {'check': 'actuator_bound_retained', 'passed': True},
            {'check': 'return_contract', 'passed': True}, {'check': 'no_imports', 'passed': True}]


def _limits():
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (512 << 20, 512 << 20))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 20, 1 << 20))
    try:
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    except (ValueError, OSError):
        pass


def sandbox_status(runner=subprocess.run) -> dict:
    if not sys.platform.startswith('linux'):
        return {'available': False, 'reason': 'process isolation with rlimits is only implemented on Linux'}
    try:
        import resource  # noqa: F401
    except Exception:
        return {'available': False, 'reason': 'resource limits unavailable'}
    try:
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'sitecustomize.py').write_text(GUARD)
            script = Path(directory, 'probe.py')
            script.write_text('import json\ntry:\n import socket\n socket.socket()\nexcept Exception:\n print(json.dumps({"blocked": True}))\nelse:\n print(json.dumps({"blocked": False}))\n')
            completed = runner([sys.executable, '-s', str(script)], cwd=directory, timeout=20,
                               env={'PATH': '/usr/bin:/bin', 'PYTHONPATH': directory, 'HOME': directory,
                                    'TMPDIR': directory, 'NAUTILUS_SANDBOX_DIR': directory},
                               capture_output=True, text=True, preexec_fn=_limits)
            if completed.returncode != 0 or '"blocked": true' not in (completed.stdout or '').lower():
                return {'available': False, 'reason': 'guard self-test did not confirm denial'}
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {'available': False, 'reason': 'sandbox self-test failed: ' + type(exc).__name__}
    return {'available': True, 'guard': 'sitecustomize denial for socket, subprocess, os.exec and open',
            'limits': 'RLIMIT_AS 512 MiB, CPU 10 s, 64 descriptors, 1 MiB file writes',
            'network_namespace': False, 'certified': False,
            'qualification': 'Best-effort process isolation with an in-process denial guard; not a kernel namespace.'}


def _samples(rows):
    return {'lever_arm': .32, 'max_thrust': 45., 'controller': {
        'lookahead_m': 7., 'heading_kp': 39., 'heading_kd': 18., 'cruise_thrust': 13., 'max_heading_rad': .72},
        'samples': rows}


def review(diff: str, *, runner=subprocess.run, timeout_s: float = 20.) -> dict:
    """Validate a diff; execute only behind the flag with a passing guard self-test."""
    lines = _check_target(diff)
    patched = apply_patch(diff)
    checks = structural_checks(patched)
    record = {'status': 'review_only', 'diff': '\n'.join(lines) + '\n', 'certified': False,
              'sandbox': None, 'checks': checks,
              'notes': ['Diff validated but not executed; review required.',
                        'A patch never replaces the trusted baseline.']}
    if not enabled():
        record['sandbox'] = {'available': False, 'reason': FEATURE_FLAG + ' is not enabled'}
        record['notes'].append('Controller patch execution is disabled by default.')
        return record
    status = sandbox_status(runner)
    record['sandbox'] = status
    if not status.get('available'):
        record['status'] = 'unavailable'
        record['notes'].append('Source-patch execution unavailable: ' + str(status.get('reason')))
        return record
    samples = [{'y': y, 'heading': h, 'rate': r} for y, h, r in
               ((0., 0., 0.), (.4, .05, .01), (-.9, -.2, .03), (1.2, .3, -.02))]
    try:
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'sitecustomize.py').write_text(GUARD)
            Path(directory, 'controller_candidate.py').write_text(patched)
            Path(directory, 'samples.json').write_text(json.dumps(_samples(samples)))
            harness = Path(directory, 'harness.py')
            harness.write_text(HARNESS)
            completed = runner([sys.executable, '-s', str(harness)], cwd=directory, timeout=timeout_s,
                               env={'PATH': '/usr/bin:/bin', 'PYTHONPATH': directory, 'HOME': directory,
                                    'TMPDIR': directory, 'NAUTILUS_SANDBOX_DIR': directory},
                               capture_output=True, text=True, preexec_fn=_limits)
            if completed.returncode != 0:
                record.update(status='unavailable', notes=['Sandboxed run failed: ' + (completed.stderr or '')[-400:]])
                return record
            payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except subprocess.TimeoutExpired:
        record.update(status='unavailable', notes=['Sandboxed run timed out; no result accepted.'])
        return record
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        record.update(status='unavailable', notes=['Sandboxed run failed: ' + type(exc).__name__])
        return record
    if payload.get('network') != 'blocked' or payload.get('filesystem') != 'blocked':
        record.update(status='unavailable', sandbox={**status, 'available': False},
                      notes=['Sandbox guard did not block network and filesystem access; execution rejected.'])
        return record
    rows = payload.get('rows')
    if type(rows) is not list or len(rows) != len(samples):
        record.update(status='unavailable', notes=['Sandboxed output failed validation.'])
        return record
    bounded = True
    for row in rows:
        outputs = row.get('outputs')
        if type(outputs) is not list or len(outputs) != 3 or not row.get('deterministic'):
            bounded = False
            break
        if any(type(value) not in (int, float) or not (-45. - 1e-9 <= value <= 45. + 1e-9) for value in outputs[:2]):
            bounded = False
            break
    if not bounded:
        record.update(status='unavailable', notes=['Patched controller violated finiteness, determinism or actuator bounds.'])
        return record
    record.update(status='executed', certified=False,
                  checks=checks + [{'check': 'sandbox_denial_guard', 'passed': True},
                                   {'check': 'deterministic_outputs', 'passed': True},
                                   {'check': 'actuator_bounds', 'passed': True}],
                  notes=['Executed in best-effort process isolation; not certified isolation.',
                         'Matched-suite regression is still required before any recommendation.',
                         'The patched module is never installed as the trusted controller.'])
    return record
