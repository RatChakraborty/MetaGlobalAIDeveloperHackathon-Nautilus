"""Readable controller source <-> IR.

`to_source` renders a policy as an ordered list of assignments in a small,
Python-like expression language. `from_source` compiles that text back into the
same IR using `ast.parse` only: nothing is executed, imported or evaluated by
Python. The accepted subset is deliberately narrow:

    name = expression                (names form a bounded dependency graph)
    + - * /                          arithmetic
    min(a, b) max(a, b) abs(a)       library functions
    atan2(a, b) clip(x, lo, hi)      library functions
    wrap(x)                          angle wrap to (-pi, pi]
    comparisons in if(cond, a, b)    comparison yields +1/-1 for use with if()
    if(cond, a, b)                   conditional expression
    numbers, the declared references and parameters only

There are no loops, no recursion, no imports, no attribute access, no calls to
anything but the fixed function table, and no statement other than assignment.
Anything else is rejected with a readable error. This is a policy DSL, not
Python: arbitrary Python controllers are not supported.
"""
from __future__ import annotations

import ast
import json
import re

from nautilus.policy_ir import CONSTANTS, INPUTS, MAX_DEPTH, MAX_NODES, PARAM_LIMITS, PolicyError, validate

FUNCTIONS = {'min': 'min', 'max': 'max', 'abs': 'abs', 'atan2': 'atan2', 'wrap': 'wrap_angle'}
ASSIGNMENT_TARGETS = ('desired', 'error', 'moment', 'port', 'starboard')
REFERENCE_NAMES = set(INPUTS) | set(CONSTANTS) | set(PARAM_LIMITS)
PRELUDE = (
    '# Nautilus controller policy (nautilus.policy-ir.v1).',
    '# Readable source of a validated IR policy: no imports, I/O, loops or hidden state.',
    '# References: y_m heading_rad yaw_rate_radps integral_y filtered_yaw_rate',
    '#             lookahead_m max_heading_rad cruise_thrust_n max_thrust_n lever_arm_m',
)


def _walk(node):
    if type(node) is dict:
        yield node
        for child in node.get('args', []):
            yield from _walk(child)


def _size(node) -> int:
    return sum(1 for _ in _walk(node))


def _shared(port, starboard):
    """Largest structurally identical subtree in both command expressions."""
    best = None
    for node in _walk(port):
        if node in list(_walk(starboard)) and (best is None or _size(node) > _size(best)):
            best = node
    return best if best is not None and _size(best) > 1 else None


def _canonical(node) -> str:
    return json.dumps(node, sort_keys=True, separators=(',', ':'))


def _render(node, named=None) -> str:
    if named and _canonical(node) in named:
        return named[_canonical(node)]
    if type(node) in (int, float):
        return repr(float(node))
    if type(node) is str:
        return node
    op = node['op']
    args = node.get('args', [])
    if op == 'const':
        return repr(float(node['value']))
    if op == 'param':
        return node['name']
    render = lambda child: _render(child, named)  # noqa: E731
    if op == 'neg':
        return f'-({render(args[0])})'
    if op == 'sat':
        return f'sat({render(args[0])})'
    if op == 'wrap_angle':
        return f'wrap({render(args[0])})'
    if op == 'abs':
        return f'abs({render(args[0])})'
    if op == 'if':
        return f'if({render(args[0])}, {render(args[1])}, {render(args[2])})'
    symbol = {'add': '+', 'sub': '-', 'mul': '*', 'div': '/', 'lt': '<', 'gt': '>'}.get(op)
    if symbol:
        return f'({render(args[0])} {symbol} {render(args[1])})'
    return f'{op}({", ".join(render(a) for a in args)})'


def to_source(policy: dict) -> str:
    """Render a validated policy as readable source with an explicit parameter block."""
    validate(policy)
    lines = list(PRELUDE)
    lines.append('')
    lines.append('# parameters')
    for name, value in sorted(policy.get('params', {}).items()):
        lines.append(f'# {name} = {float(value)!r}   bounds {PARAM_LIMITS[name]}')
    lines.append('')
    lines.append('# control law')
    named = {}
    if 'desired_heading' in policy:
        lines.append(f'desired = {_render(policy["desired_heading"])}')
        named[_canonical(policy['desired_heading'])] = 'desired'
    moment = _shared(policy['port'], policy['starboard'])
    if moment is not None:
        lines.append(f'moment = {_render(moment, dict(named))}')
        named[_canonical(moment)] = 'moment'
    lines.append(f'port = {_render(policy["port"], named)}')
    lines.append(f'starboard = {_render(policy["starboard"], named)}')
    return '\n'.join(lines) + '\n'


def _constant(value):
    return {'op': 'const', 'value': float(value)}


def _compile(node, env, depth, counter):
    counter[0] += 1
    if counter[0] > MAX_NODES:
        raise PolicyError('source exceeds node limit')
    if depth > MAX_DEPTH:
        raise PolicyError('source exceeds depth limit')
    if isinstance(node, ast.Constant):
        if type(node.value) not in (int, float) or type(node.value) is bool:
            raise PolicyError('only numeric literals are allowed')
        return _constant(node.value)
    if isinstance(node, ast.Name):
        if node.id in env:
            return env[node.id]
        if node.id in INPUTS or node.id in CONSTANTS:
            return node.id
        if node.id in PARAM_LIMITS:
            return {'op': 'param', 'name': node.id}
        raise PolicyError(f'unknown name: {node.id}')
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return {'op': 'neg', 'args': [_compile(node.operand, env, depth + 1, counter)]}
    if isinstance(node, ast.BinOp):
        op = {ast.Add: 'add', ast.Sub: 'sub', ast.Mult: 'mul', ast.Div: 'div'}.get(type(node.op))
        if op is None:
            raise PolicyError(f'unsupported operator: {type(node.op).__name__}')
        return {'op': op, 'args': [_compile(node.left, env, depth + 1, counter),
                                   _compile(node.right, env, depth + 1, counter)]}
    if isinstance(node, ast.Compare):
        if len(node.ops) != 1 or type(node.ops[0]) not in (ast.Lt, ast.Gt):
            raise PolicyError('only single < or > comparisons are allowed')
        op = 'lt' if isinstance(node.ops[0], ast.Lt) else 'gt'
        return {'op': op, 'args': [_compile(node.left, env, depth + 1, counter),
                                   _compile(node.comparators[0], env, depth + 1, counter)]}
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.keywords:
            raise PolicyError('only direct calls to the policy library are allowed')
        name = node.func.id
        args = [_compile(arg, env, depth + 1, counter) for arg in node.args]
        if name == 'clip':
            if len(args) != 3:
                raise PolicyError('clip takes value, low, high')
            return {'op': 'max', 'args': [args[1], {'op': 'min', 'args': [args[2], args[0]]}]}
        if name == 'if':
            if len(args) != 3:
                raise PolicyError('if takes condition, then, else')
            return {'op': 'if', 'args': args}
        if name == 'sat':
            if len(args) != 1:
                raise PolicyError('sat takes one argument')
            return {'op': 'sat', 'args': args}
        op = FUNCTIONS.get(name)
        arity = {'min': 2, 'max': 2, 'atan2': 2, 'abs': 1, 'wrap': 1}.get(name)
        if op is None or len(args) != arity:
            raise PolicyError(f'unsupported function: {name}')
        return {'op': op, 'args': args}
    raise PolicyError(f'unsupported syntax: {type(node).__name__}')


def from_source(text: str, *, params: dict | None = None, name: str = 'candidate') -> dict:
    """Compile readable source into a validated policy document."""
    if type(text) is not str or len(text) > 4000:
        raise PolicyError('source must be text under 4000 characters')
    try:
        tree = ast.parse(text, mode='exec')
    except SyntaxError as exc:
        raise PolicyError(f'syntax error at line {exc.lineno}: {exc.msg}') from None
    if len(tree.body) > 12:
        raise PolicyError('too many statements')
    env = {}
    counter = [0]
    for statement in tree.body:
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
            continue  # bare string/documentation literal
        if not (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)):
            raise PolicyError('only simple assignments are allowed')
        target = statement.targets[0].id
        if target not in ASSIGNMENT_TARGETS:
            raise PolicyError(f'unknown assignment target: {target}')
        if target in env:
            raise PolicyError(f'{target} assigned twice')
        env[target] = _compile(statement.value, env, 0, counter)
    if 'port' not in env or 'starboard' not in env:
        raise PolicyError('source must define port and starboard')
    # Parameters the source declares (its readable header) are the base; caller overrides
    # replace only the keys they name. Dropping the declared ones would zero unrelated gains.
    declared = {m.group(1): float(m.group(2))
                for m in re.finditer(r'^#\s*([a-z_]+)\s*=\s*(-?[0-9.]+)', text, re.MULTILINE)}
    policy = {'schema': 'nautilus.policy-ir.v1', 'name': name,
              'params': {**declared, **dict(params or {})}, 'port': env['port'], 'starboard': env['starboard']}
    if 'desired' in env:
        policy['desired_heading'] = env['desired']
    return validate(policy)
