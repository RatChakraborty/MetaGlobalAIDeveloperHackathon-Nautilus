"""Bounded Meta Responses transport. No SDK retries, redirects or credential persistence."""
from dataclasses import dataclass
import json
import os
import time
import urllib.error
import urllib.request
from .v2_tools import parse_json

ENDPOINT = 'https://api.meta.ai/v1/responses'
DEFAULT_MODEL = 'muse-wonder-1.0'


def encode_request(*, model, reasoning_effort, instructions, input, tools,
                   previous_response_id, max_output_tokens):
    """Exact JSON request serialization shared by byte admission and transport."""
    payload = dict(model=model, instructions=instructions, input=input, tools=tools,
                   stream=False, store=True, tool_choice='auto', parallel_tool_calls=False,
                   max_output_tokens=max_output_tokens)
    if reasoning_effort is not None: payload['reasoning'] = {'effort':reasoning_effort}
    if previous_response_id: payload['previous_response_id'] = previous_response_id
    return json.dumps(payload, allow_nan=False).encode()


class ProviderError(Exception):
    def __init__(self, code, *, retryable=False):
        super().__init__(code)
        self.code, self.retryable = code, retryable


@dataclass(frozen=True)
class Reply:
    response_id: str
    model: str
    output: list
    usage: dict
    latency_s: float
    status: str
    http_status: int | None = None
    incomplete_reason: str | None = None
    reasoning_effort: str | None = None

    @property
    def has_text(self):
        return any(item.get('type') == 'message' and any(
            c.get('type') == 'output_text' and isinstance(c.get('text'), str) and bool(c['text'].strip())
            for c in (item.get('content') or []) if isinstance(c, dict)) for item in self.output)

    @property
    def calls(self):
        return [x for x in self.output if x['type'] == 'function_call']


def parse_reply(value, model, latency_s, http_status=None):
    try:
        if type(value) is not dict or value.get('model') != model:
            raise ValueError()
        if value.get('status') not in ('completed', 'incomplete') or not isinstance(value.get('id'), str):
            raise ValueError()
        output = value['output']
        if type(output) is not list or len(output) > 16:
            raise ValueError()
        ids = set()
        for item in output:
            if type(item) is not dict or item.get('type') not in ('function_call', 'message', 'reasoning'):
                raise ValueError()
            if item['type'] == 'message':
                if type(item.get('content')) is not list or any(type(c) is not dict for c in item['content']):
                    raise ValueError()
                if any(c.get('type') == 'output_text' and type(c.get('text')) is not str for c in item['content']):
                    raise ValueError()
            if item['type'] == 'function_call':
                for key in ('name', 'arguments', 'call_id'):
                    if type(item.get(key)) is not str or not 0 < len(item[key]) <= 20000:
                        raise ValueError()
                if item['call_id'] in ids:
                    raise ValueError()
                ids.add(item['call_id'])
        usage = value.get('usage') or {}
        if type(usage) is not dict:
            raise ValueError()
        # Only measured token counters survive. Never persist reasoning or provider internals.
        safe = {}
        for key in ('input_tokens', 'output_tokens', 'total_tokens'):
            if key in usage:
                if type(usage[key]) is not int or usage[key] < 0:
                    raise ValueError()
                safe[key] = usage[key]
        for detail_key, source_key, counter in (
                ('reasoning_tokens', 'output_tokens_details', 'reasoning_tokens'),
                ('cached_input_tokens', 'input_tokens_details', 'cached_tokens')):
            detail = usage.get(source_key)
            if detail is not None:
                if type(detail) is not dict:
                    raise ValueError()
                if counter in detail:
                    count = detail[counter]
                    if type(count) is not int or count < 0:
                        raise ValueError()
                    safe[detail_key] = count
        if safe.get('reasoning_tokens', 0) > safe.get('output_tokens', float('inf')) or safe.get('cached_input_tokens', 0) > safe.get('input_tokens', float('inf')):
            raise ValueError()
        reported = value.get('reasoning')
        effort = None
        if type(reported) is dict and reported.get('effort') is not None:
            effort = reported['effort'] if reported['effort'] in ('low','medium','high','max') else 'other'
        details = value.get('incomplete_details')
        reason = None
        if value['status'] == 'incomplete' and type(details) is dict and details.get('reason') is not None:
            reason = details['reason'] if details['reason'] in ('max_output_tokens','max_tokens','content_filter') else 'other'
        return Reply(value['id'], model, output, safe, latency_s, value['status'], http_status, reason, effort)
    except (ValueError, TypeError, KeyError):
        raise ProviderError('malformed_response') from None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class MetaProvider:
    """Continuation uses previous_response_id plus matching function_call_output items.

    Instructions and tools are resent on every turn. Stored responses are required
    for this mode. Reasoning items are never copied to local records. Each generate
    invokes exactly one HTTP request; retries belong exclusively to the host.
    """
    provider = 'meta'

    def __init__(self, model=None, *, reasoning_effort=None, api_key=None):
        # Per-run key held in memory only; never stored, logged or serialized.
        if api_key is not None and (type(api_key) is not str or not 20 <= len(api_key) <= 512 or any(c.isspace() for c in api_key)):
            raise ValueError('Invalid credential format')
        self._api_key = api_key
        self.model = model or os.environ.get('NAUTILUS_MUSE_MODEL', DEFAULT_MODEL)
        # Empty string explicitly omits the override, including environment defaults.
        effort = os.environ.get('NAUTILUS_MUSE_REASONING_EFFORT') if reasoning_effort is None else reasoning_effort
        if effort not in (None, '', 'low') or (effort is not None and type(effort) is not str):
            raise ValueError('Only documented low reasoning effort or omission is permitted')
        self.reasoning_effort = effort or None
        if type(self.model) is not str or not self.model or len(self.model) > 100:
            raise ValueError('Invalid nonsecret model setting')

    def request_size(self, *, instructions, input, tools, previous_response_id, max_output_tokens, timeout):
        return len(encode_request(model=self.model, reasoning_effort=self.reasoning_effort,
            instructions=instructions, input=input, tools=tools, previous_response_id=previous_response_id,
            max_output_tokens=max_output_tokens))

    def generate(self, *, instructions, input, tools, previous_response_id, max_output_tokens, timeout):
        key = self._api_key or os.environ.get('MODEL_API_KEY')
        if not key:
            raise ProviderError('credential_unavailable')
        body = encode_request(model=self.model, reasoning_effort=self.reasoning_effort,
            instructions=instructions, input=input, tools=tools, previous_response_id=previous_response_id,
            max_output_tokens=max_output_tokens)
        if len(body) > 2_000_000:
            raise ProviderError('request_size_limit')
        request = urllib.request.Request(ENDPOINT, data=body, method='POST',
            headers={'Authorization': 'Bearer '+key, 'Content-Type': 'application/json'})
        start = time.monotonic()
        try:
            with urllib.request.build_opener(_NoRedirect).open(request, timeout=timeout) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ProviderError('response_size_limit')
                decoded = raw.decode()
                if key in decoded:
                    raise ProviderError('credential_echo')
                value = parse_json(decoded)
                http_status = response.status
            return parse_reply(value, self.model, time.monotonic()-start, http_status)
        except urllib.error.HTTPError as exc:
            # Provider error bodies can echo untrusted arguments/headers: never retain them.
            code = exc.code
            raise ProviderError('http_'+str(code), retryable=code in (429, 500, 502, 503, 504)) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ProviderError('network_or_timeout') from None
        except (ValueError, UnicodeError, RecursionError):
            raise ProviderError('malformed_response') from None
