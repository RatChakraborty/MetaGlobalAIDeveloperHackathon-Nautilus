"""Live Muse provider for the controller-engineering loop.

The provider only proposes the next tool call. Every call still goes through the trusted
`call()` dispatcher, so Muse never executes code, never reads hidden truth and never bypasses
the IR validator or the simulator gates.

Paid execution is blocked in three independent places, each checked before any request:
1. `muse_enabled()` must be exactly 'true' (NAUTILUS_MUSE_ENABLED).
2. `LiveEnvelope` must pass: token, request, and wall-clock ceilings are enforced per session.
3. `live_available()` in `studio_muse` stays False, so `run_session` never selects this provider
   from the public API. Only an explicit caller can construct it, and tests use a scripted transport.

No API key is read here. The transport is injected by the operator and is never invoked by tests.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from nautilus.studio_muse import TOOL_NAMES, TOOLS, ToolError, muse_enabled

# Ceilings for one controller-engineering session. The investigation budget ($0.41) is not
# reused: this workflow issues more calls, so it gets its own ceilings, checked before each request.
MAX_INPUT_TOKENS = 60_000       # total prompt tokens across the session
MAX_OUTPUT_TOKENS = 4_000       # total completion tokens across the session
MAX_REQUESTS = 12               # model requests per session (matches Budget.max_requests)
MAX_USD = 0.25                  # hard session spend ceiling (see docs/muse-cost-envelope.md)
MAX_OBSERVATION_CHARS = 6_000   # trimmed transcript sent to the model per request
# Published muse-spark-1.3 prices, USD per million tokens (https://dev.meta.ai/products/meta-model-api).
SPARK_USD_PER_MTOK_IN = 1.25
SPARK_USD_PER_MTOK_OUT = 4.25


class LiveDisabled(RuntimeError):
    pass


@dataclass
class LiveEnvelope:
    """Pre-request accounting. Raises before a request would exceed a ceiling."""
    input_tokens: int = 0
    output_tokens: int = 0
    requests: int = 0
    usd: float = 0.0
    usd_per_mtok_in: float = SPARK_USD_PER_MTOK_IN
    usd_per_mtok_out: float = SPARK_USD_PER_MTOK_OUT

    def reserve(self, est_input: int, est_output: int):
        if not muse_enabled():
            raise LiveDisabled('NAUTILUS_MUSE_ENABLED is not true; no provider request was made')
        if self.usd_per_mtok_in <= 0 or self.usd_per_mtok_out <= 0:
            # Without verified prices the spend ceiling cannot be computed, so no request is allowed.
            raise LiveDisabled('no verified price configured; spend ceiling cannot be enforced')
        if self.requests + 1 > MAX_REQUESTS:
            raise ToolError('live request ceiling reached')
        if self.input_tokens + est_input > MAX_INPUT_TOKENS or self.output_tokens + est_output > MAX_OUTPUT_TOKENS:
            raise ToolError('live token ceiling reached')
        projected = (self.usd + est_input * self.usd_per_mtok_in / 1e6 + est_output * self.usd_per_mtok_out / 1e6)
        if projected > MAX_USD:
            raise ToolError('live spend ceiling reached')
        self.requests += 1

    def record(self, used_in: int, used_out: int):
        self.input_tokens += used_in
        self.output_tokens += used_out
        self.usd += used_in * self.usd_per_mtok_in / 1e6 + used_out * self.usd_per_mtok_out / 1e6


def _trim(observations: list) -> str:
    """Keep the newest transcript entries within a fixed character budget."""
    text = json.dumps(observations, default=str, sort_keys=True)
    return text[-MAX_OBSERVATION_CHARS:]


def _strict_schema(schema):
    """Strict Responses mode requires every property to be listed as required.

    Optional fields become required nullable fields. The trusted validator still sees the
    original schema: `_drop_nulls` removes null optional arguments before dispatch.
    """
    properties = schema.get('properties', {})
    if not properties:
        return schema
    wrapped = {}
    for key, spec in properties.items():
        wrapped[key] = _nullable_spec(spec)
    return {'type': 'object', 'properties': wrapped, 'required': list(properties),
            'additionalProperties': False}


def _drop_nulls(arguments):
    """Remove null optionals. Strict mode forces `params` to appear, so an empty one beside a
    source is only the schema placeholder and is removed. Non-empty params beside a source
    still reach the trusted validator, which refuses them."""
    cleaned = {key: value for key, value in arguments.items() if value is not None}
    if cleaned.get('source') is not None and cleaned.get('params') == {}:
        del cleaned['params']
    return cleaned


WIRE_ALIASES = {'propose_parameter_revision': 'propose_controller_revision',
                'propose_source_revision': 'propose_controller_revision'}


def _closed_params_spec():
    """Strict mode needs a closed object: list the IR parameter names the validator accepts."""
    from nautilus.policy_ir import PARAM_LIMITS
    return {'type': 'object', 'description': 'IR parameter overrides. Send only one of params or source; never both.',
            'properties': {name: {'type': 'number'} for name in PARAM_LIMITS},
            'required': list(PARAM_LIMITS), 'additionalProperties': False}


def _nullable_spec(spec):
    """Add null to a field's type, keeping its items, description and other keys."""
    kind = spec.get('type')
    if not kind:
        return spec
    if isinstance(kind, list):
        return spec
    return {**spec, 'type': [kind, 'null']}


def _nullable_except(props, keep):
    """Strict wire variant: the chosen field stays required; the other field is always null.
    `_drop_nulls` removes the null, so the trusted validator sees only the chosen field."""
    out = {}
    for key, spec in props.items():
        if key == keep:
            out[key] = spec
        else:
            out[key] = _nullable_spec(spec)
    return out


def meta_transport(provider=None):
    """Adapt MetaProvider to the transport contract: one HTTP request, one tool call per reply."""
    from nautilus.muse import MetaProvider
    provider = provider or MetaProvider(model=os.environ.get('NAUTILUS_STUDIO_MUSE_MODEL', 'muse-spark-1.3'))
    strict_tools = []
    for t in TOOLS:
        if t['name'] == 'propose_controller_revision':
            # Strict mode cannot express "params or source", so the wire offers two fixed variants.
            # Both map back to the one trusted proposal tool in `to_trusted_call`.
            for wire, field, kind in (('propose_parameter_revision', 'params', 'object'),
                                      ('propose_source_revision', 'source', 'string')):
                raw = t['parameters']['properties']
                props = {k: v for k, v in raw.items() if k not in ('params', 'source')}
                props[field] = _closed_params_spec() if field == 'params' else raw[field]
                strict_tools.append({'type': 'function', 'name': wire,
                                     'description': t['description'] + f' Send only the {field} field.',
                                     'strict': True,
                                     'parameters': {'type': 'object', 'properties': _nullable_except(props, field),
                                                    'required': list(props), 'additionalProperties': False}})
        else:
            strict_tools.append({'type': 'function', 'name': t['name'], 'description': t['description'],
                                 'strict': True, 'parameters': _strict_schema(t['parameters'])})
    state = {'previous': None, 'pending': None}

    def transport(*, system, transcript, tools, last=None):
        if state['pending'] is None:
            payload = [{'role': 'user', 'content': transcript}]
        else:
            # Return the trusted result (or refusal) of the previous call so Muse reasons on real numbers.
            body = last.get('result') if last and 'result' in last else {'error': (last or {}).get('error', 'no result')}
            payload = [{'type': 'function_call_output', 'call_id': state['pending'],
                        'output': json.dumps(body, default=str, sort_keys=True)[:MAX_OBSERVATION_CHARS]}]
        reply = provider.generate(instructions=system, input=payload, tools=strict_tools,
                                  previous_response_id=state['previous'],
                                  max_output_tokens=MAX_OUTPUT_TOKENS, timeout=60)
        if reply.status != 'completed' or len(reply.calls) != 1:
            raise ToolError('model returned no supported tool call')
        call = reply.calls[0]
        state['previous'] = reply.response_id
        state['pending'] = call['call_id']
        return {'usage': {'input_tokens': reply.usage.get('input_tokens', 0),
                          'output_tokens': reply.usage.get('output_tokens', 0)},
                'tool_call': {'name': WIRE_ALIASES.get(call['name'], call['name']),
                              'arguments': _drop_nulls(json.loads(call['arguments']))}}
    return transport


class LiveMuse:
    """Provider that asks a model for the next tool call, using the fixed tool schema only."""

    name = 'muse-live'

    def __init__(self, transport, envelope: LiveEnvelope | None = None):
        if not callable(transport):
            raise TypeError('a transport callable is required; no default network transport exists')
        self.transport = transport
        self.envelope = envelope or LiveEnvelope()

    def next_call(self, session, observations) -> dict:
        est_in = (len(_trim(observations)) + 2_000) // 4
        self.envelope.reserve(est_in, 600)
        reply = self.transport(
            system=('You engineer a marine controller through the listed tools only. '
                    'Abstain when evidence is inconclusive. Candidate hypotheses are not proven causes.'),
            transcript=_trim(observations),
            tools=TOOLS,
            last=observations[-1] if observations else None,
        )
        used = reply.get('usage', {})
        self.envelope.record(int(used.get('input_tokens', est_in)), int(used.get('output_tokens', 0)))
        call = reply.get('tool_call') or {}
        if call.get('name') not in TOOL_NAMES:
            raise ToolError('model returned no supported tool call')
        arguments = call.get('arguments') or {}
        if not isinstance(arguments, dict):
            raise ToolError('tool arguments must be an object')
        return {'tool': call['name'], 'arguments': arguments}
