"""Restricted controller-source patch review (static only).

A generated diff is validated, applied in memory and structurally checked. It is
**never executed**: this project has no trustworthy isolation boundary, so the
execution milestone is reported as unavailable rather than attempted. The module
imports no process, network or temporary-directory machinery, and nothing here can
run model-supplied code.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re

TARGET_PATH = 'nautilus/v6/controller_variant.py'
TARGET_FUNCTION = 'command'
MAX_BYTES = 4000
MAX_HUNKS = 2
MAX_ADDED_LINES = 40
EXECUTION = 'unavailable'
SANDBOX_REASON = ('No trustworthy isolation boundary exists in this project, so a patch is '
                  'validated statically and never executed.')
FORBIDDEN = ('import ', '__', 'eval(', 'exec(', 'open(', 'socket', 'subprocess', 'os.system', 'os.environ',
             'os.remove', 'shutil', 'pathlib', 'urllib', 'requests', 'pickle', 'ctypes', 'sys.', 'globals(',
             'locals(', 'setattr(', 'while True', 'compile(', 'input(')


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
    """Apply a validated diff in memory. Nothing is written to disk or executed."""
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
    """Parse the patched module and confirm the fixed controller contract."""
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
    if target.args.vararg or target.args.kwarg or target.args.defaults or target.args.kwonlyargs:
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


def review(diff: str) -> dict:
    """Validate, apply in memory and structurally check a diff. Never executes it."""
    lines = _check_target(diff)
    patched = apply_patch(diff)
    checks = structural_checks(patched)
    return {'status': 'review_only', 'diff': '\n'.join(lines) + '\n', 'certified': False,
            'sandbox': {'available': False, 'execution': EXECUTION, 'certified': False,
                        'reason': SANDBOX_REASON},
            'checks': checks,
            'notes': ['Diff validated and structurally checked; it is not executed anywhere in this repository.',
                      'Execution is reported unavailable rather than attempted because no isolation is trustworthy.',
                      'A patch never replaces the trusted baseline; human review is required.']}
