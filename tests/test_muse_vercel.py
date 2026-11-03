"""End-to-end tests for the Vercel live-Muse handler (api/muse.py).

The handler runs behind a real HTTP server. The budget ledger is a real Redis (redislite, test-only)
behind a local shim that speaks Upstash's REST protocol. The provider run is mocked, so no test
makes a paid Muse call.
"""
import importlib
import io
import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

redislite = pytest.importorskip("redislite")
import redis  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nautilus_api import budget, ledger  # noqa: E402

TOKEN = "test-demo-token"
BODY = {"scenario": {"current_y": 1.0}, "seed": 5, "duration_s": 4.0}
DAY = f"nautilus:demo:day:{budget.day_key()}"


def _shim(server):
    class Shim(BaseHTTPRequestHandler):
        def do_POST(self):
            args = json.loads(self.rfile.read(int(self.headers["Content-Length"])))

            def plain(value):
                if isinstance(value, bytes):
                    return value.decode()
                if isinstance(value, list):
                    return [plain(v) for v in value]
                return value

            try:
                body = {"result": plain(server.execute_command(*args))}
            except redis.ResponseError as exc:
                body = {"error": str(exc)}
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            return

    return Shim


@pytest.fixture()
def env(monkeypatch, tmp_path):
    """Set up Redis, env vars and a live HTTP server for api/muse.py."""
    store = redislite.Redis(str(tmp_path / "redis.db"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _shim(store))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", f"http://127.0.0.1:{httpd.server_address[1]}")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "redis-token")
    monkeypatch.setenv("NAUTILUS_DEMO_TOKEN", TOKEN)
    monkeypatch.delenv("NAUTILUS_MUSE_MONTHLY_BUDGET_USD", raising=False)

    muse = importlib.import_module("api.muse")
    calls = []
    outcome = {"raise": False, "usage": {"input_tokens": 1000, "output_tokens": 500}}

    def fake_run(faults, mission, request):
        calls.append(request)
        if outcome["raise"]:
            raise RuntimeError("provider exploded with secret detail")
        body = {"model_requests": [{"usage": outcome["usage"]}]}
        return {"public_record": {"ok": True},
                "provenance": {"body_canonical": json.dumps(body)}}

    import nautilus_api.jobs as jobs
    monkeypatch.setattr(jobs, "run_muse_investigation", fake_run)

    server = ThreadingHTTPServer(("127.0.0.1", 0), muse.handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    yield {"base": base, "redis": store, "calls": calls, "outcome": outcome}
    server.shutdown()
    httpd.shutdown()
    store.close()


def _post(base, body=BODY, token=TOKEN, raw=None):
    data = raw if raw is not None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base + "/api/muse", data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.load(resp), resp.headers
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}"), exc.headers


def _daily_usd(store):
    value = store.hget(DAY, "usd")
    return int(value) if value is not None else 0


def test_missing_or_wrong_token_is_rejected_before_any_run(env):
    status, body, _ = _post(env["base"], token=None)
    assert status == 401 and body == {"error": "Unauthorized"}
    status, _, _ = _post(env["base"], token="wrong")
    assert status == 401
    assert env["calls"] == [] and env["redis"].keys("nautilus:*") == []


def test_invalid_json_and_oversized_body_are_400(env):
    status, body, _ = _post(env["base"], raw=b"{not json")
    assert status == 400 and body["error"] == "Invalid JSON"
    status, body, _ = _post(env["base"], raw=b"{" + b" " * 5000 + b"}")
    assert status == 400 and body["error"] == "Request body too large"
    assert env["calls"] == []


def test_successful_run_settles_to_measured_cost_not_worst_case(env):
    status, body, headers = _post(env["base"])
    assert status == 200 and body["result"]["public_record"] == {"ok": True}
    assert headers["Cache-Control"] == "no-store"
    assert len(env["calls"]) == 1
    # 1000 input at $4/M + 500 output at $20/M = $0.014, settled to micro-dollars.
    assert _daily_usd(env["redis"]) == 14_000


def test_missing_usage_is_priced_at_its_share_of_the_worst_case(env):
    """A call that reports no usage must not settle to free, or spend would be undercounted."""
    env["outcome"]["usage"] = {}
    status, _, _ = _post(env["base"])
    assert status == 200
    assert _daily_usd(env["redis"]) > 0


def test_negative_content_length_cannot_bypass_the_body_cap(monkeypatch):
    """int() accepts a negative Content-Length, so the cap must reject it before rfile.read()."""
    monkeypatch.setenv("NAUTILUS_DEMO_TOKEN", TOKEN)
    muse = importlib.import_module("api.muse")
    handler = muse.handler.__new__(muse.handler)
    handler.headers = {"Content-Length": "-1", "Authorization": f"Bearer {TOKEN}"}
    handler.rfile = io.BytesIO(b"{" + b" " * 5000 + b"}")
    sent = {}
    handler._send = lambda status, payload: sent.update(status=status, payload=payload)
    handler.do_POST()
    assert sent["status"] == 400


def test_non_numeric_content_length_is_400_not_500(monkeypatch):
    monkeypatch.setenv("NAUTILUS_DEMO_TOKEN", TOKEN)
    muse = importlib.import_module("api.muse")
    handler = muse.handler.__new__(muse.handler)
    handler.headers = {"Content-Length": "abc", "Authorization": f"Bearer {TOKEN}"}
    handler.rfile = io.BytesIO(b"{}")
    sent = {}
    handler._send = lambda status, payload: sent.update(status=status, payload=payload)
    handler.do_POST()
    assert sent["status"] == 400 and sent["payload"]["error"] == "Invalid Content-Length"


def test_failed_run_keeps_worst_case_hold_and_hides_detail(env):
    env["outcome"]["raise"] = True
    status, body, _ = _post(env["base"])
    assert status == 500 and body == {"error": "Investigation failed"}
    assert "secret detail" not in json.dumps(body)
    assert _daily_usd(env["redis"]) == 410_000


def test_budget_exhaustion_returns_429_without_a_run(env, monkeypatch):
    monkeypatch.setenv("NAUTILUS_MUSE_MONTHLY_BUDGET_USD", "0")
    status, body, _ = _post(env["base"])
    assert status == 429
    assert env["calls"] == []


def test_daily_run_limit_enforced_across_requests(env):
    for _ in range(budget.PER_USER_DAILY_RUNS):
        env["outcome"]["usage"] = {"input_tokens": 0, "output_tokens": 0}
        assert _post(env["base"])[0] == 200
    status, _, _ = _post(env["base"])
    assert status == 429
    assert len(env["calls"]) == budget.PER_USER_DAILY_RUNS


def test_concurrent_requests_never_exceed_daily_usd_cap(env):
    """Parallel requests on separate connections: only the number of worst-case holds that fit run."""
    env["outcome"]["raise"] = True  # failures keep their holds, so the test measures reservation only
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(lambda _: _post(env["base"])[0], range(8)))
    # $1.00 daily cap / $0.41 hold = 2 runs. The rest are refused before the provider.
    assert statuses.count(500) == 2 and statuses.count(429) == 6
    assert len(env["calls"]) == 2
    assert _daily_usd(env["redis"]) == 820_000


def test_redis_outage_fails_closed_with_503(env, monkeypatch):
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL")
    status, body, _ = _post(env["base"])
    assert status == 503 and body == {"error": "Budget service unavailable"}
    assert env["calls"] == []
