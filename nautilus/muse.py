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

    @property
    def calls(self):
        return [x for x in self.output if x['type'] == 'function_call']


def parse_reply(value, model, latency_s):
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
        return Reply(value['id'], model, output, safe, latency_s, value['status'])
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

    def __init__(self, model=None):
        self.model = model or os.environ.get('NAUTILUS_MUSE_MODEL', DEFAULT_MODEL)
        if type(self.model) is not str or not self.model or len(self.model) > 100:
            raise ValueError('Invalid nonsecret model setting')

    def generate(self, *, instructions, input, tools, previous_response_id, max_output_tokens, timeout):
        key = os.environ.get('MODEL_API_KEY')
        if not key:
            raise ProviderError('credential_unavailable')
        payload = dict(model=self.model, instructions=instructions, input=input, tools=tools,
                       stream=False, store=True, tool_choice='auto', parallel_tool_calls=False,
                       max_output_tokens=max_output_tokens)
        if previous_response_id:
            payload['previous_response_id'] = previous_response_id
        body = json.dumps(payload, allow_nan=False).encode()
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
            return parse_reply(value, self.model, time.monotonic()-start)
        except urllib.error.HTTPError as exc:
            # Provider error bodies can echo untrusted arguments/headers: never retain them.
            code = exc.code
            raise ProviderError('http_'+str(code), retryable=code in (429, 500, 502, 503, 504)) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ProviderError('network_or_timeout') from None
        except (ValueError, UnicodeError, RecursionError):
            raise ProviderError('malformed_response') from None
