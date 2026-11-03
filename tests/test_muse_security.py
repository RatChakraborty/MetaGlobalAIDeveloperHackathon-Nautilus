"""Unauthenticated security tests for api/muse.py. No paid provider call is possible here.

The provider run is replaced by a recorder, and the budget ledger is never reached for rejected
requests. These tests cover the public attack surface: missing, malformed and wrong credentials,
an unset server token, CORS origin handling, and absence of secrets in responses.
"""
import importlib
import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SERVER_TOKEN = "server-only-demo-token-xyz"
MODEL_KEY = "model-key-should-never-leak"
BODY = {"scenario": {"current_y": 1.0}, "seed": 5, "duration_s": 4.0}


@pytest.fixture()
def server(monkeypatch):
    monkeypatch.setenv("NAUTILUS_DEMO_TOKEN", SERVER_TOKEN)
    monkeypatch.setenv("MODEL_API_KEY", MODEL_KEY)
    monkeypatch.setenv("NAUTILUS_ALLOWED_ORIGIN", "https://app.example")
    # Redis is deliberately unset: any request that reaches the ledger would fail with 503.
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_TOKEN", raising=False)
    muse = importlib.import_module("api.muse")
    import nautilus_api.jobs as jobs

    calls = []
    monkeypatch.setattr(jobs, "run_muse_investigation", lambda *a: calls.append(a) or {})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), muse.handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield {"base": f"http://127.0.0.1:{httpd.server_address[1]}", "calls": calls}
    httpd.shutdown()


def _request(base, method="POST", headers=None, data=None):
    req = urllib.request.Request(base + "/api/muse", data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


JSON = {"Content-Type": "application/json"}


@pytest.mark.parametrize("auth", [
    None,
    "",
    "Bearer",
    "Bearer ",
    "Basic " + SERVER_TOKEN,
    "bearer " + SERVER_TOKEN,
    "Bearer wrong",
    "Bearer " + SERVER_TOKEN + "x",
    "Bearer " + SERVER_TOKEN[:-1],
])
def test_unauthenticated_or_malformed_auth_gets_401_without_a_run(server, auth):
    headers = dict(JSON)
    if auth is not None:
        headers["Authorization"] = auth
    status, body, _ = _request(server["base"], headers=headers, data=json.dumps(BODY).encode())
    assert status == 401
    assert json.loads(body) == {"error": "Unauthorized"}
    assert server["calls"] == []


def test_no_authorization_at_all_is_401_even_with_valid_body(server):
    status, body, _ = _request(server["base"], headers=JSON, data=json.dumps(BODY).encode())
    assert status == 401 and b"Investigation" not in body


def test_unset_server_token_fails_closed_for_every_credential(server, monkeypatch):
    monkeypatch.delenv("NAUTILUS_DEMO_TOKEN")
    for auth in ["Bearer ", "Bearer " + SERVER_TOKEN, "Bearer "]:
        status, _, _ = _request(server["base"], headers={**JSON, "Authorization": auth},
                                data=json.dumps(BODY).encode())
        assert status == 401
    assert server["calls"] == []


def test_unauthenticated_get_is_rejected(server):
    status, _, _ = _request(server["base"], method="GET")
    assert status in (401, 405, 501)
    assert server["calls"] == []


def test_responses_never_contain_secrets(server):
    for auth in [None, "Bearer wrong"]:
        headers = dict(JSON)
        if auth:
            headers["Authorization"] = auth
        status, body, hdrs = _request(server["base"], headers=headers, data=b"{}")
        text = body.decode() + json.dumps(hdrs)
        assert SERVER_TOKEN not in text and MODEL_KEY not in text
        assert hdrs.get("Cache-Control") == "no-store"
        assert hdrs.get("X-Content-Type-Options") == "nosniff"


def test_cors_allows_only_the_configured_origin(server):
    req = urllib.request.Request(server["base"] + "/api/muse", method="OPTIONS",
                                 headers={"Origin": "https://evil.example"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert "Access-Control-Allow-Origin" not in resp.headers

    req = urllib.request.Request(server["base"] + "/api/muse", method="OPTIONS",
                                 headers={"Origin": "https://app.example"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 204
        assert resp.headers["Access-Control-Allow-Origin"] == "https://app.example"
        assert "Authorization" in resp.headers["Access-Control-Allow-Headers"]
        assert resp.headers["Vary"] == "Origin"


def test_cors_never_uses_wildcard_even_for_unauthenticated_preflight(server):
    req = urllib.request.Request(server["base"] + "/api/muse", method="OPTIONS",
                                 headers={"Origin": "https://evil.example"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.headers.get("Access-Control-Allow-Origin") != "*"


def test_cross_origin_post_without_token_is_401_not_a_run(server):
    headers = {**JSON, "Origin": "https://evil.example"}
    status, _, hdrs = _request(server["base"], headers=headers, data=json.dumps(BODY).encode())
    assert status == 401
    assert "Access-Control-Allow-Origin" not in hdrs
    assert server["calls"] == []
