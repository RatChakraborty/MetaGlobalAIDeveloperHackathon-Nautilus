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
from dataclasses import dataclass

from nautilus.studio_muse import TOOL_NAMES, TOOLS, ToolError, muse_enabled

# Ceilings for one controller-engineering session. The investigation budget ($0.41) is not
# reused: this workflow issues more calls, so it gets its own ceilings, checked before each request.
MAX_INPUT_TOKENS = 60_000       # total prompt tokens across the session
MAX_OUTPUT_TOKENS = 4_000       # total completion tokens across the session
MAX_REQUESTS = 12               # model requests per session (matches Budget.max_requests)
MAX_USD = 0.25                  # hard session spend ceiling (see docs/muse-cost-envelope.md)
MAX_OBSERVATION_CHARS = 6_000   # trimmed transcript sent to the model per request


class LiveDisabled(RuntimeError):
    pass


@dataclass
class LiveEnvelope:
    """Pre-request accounting. Raises before a request would exceed a ceiling."""
    input_tokens: int = 0
    output_tokens: int = 0
    requests: int = 0
    usd: float = 0.0
    usd_per_mtok_in: float = 0.0
    usd_per_mtok_out: float = 0.0

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
