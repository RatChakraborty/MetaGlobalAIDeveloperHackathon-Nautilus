"""Tests for the free hosted routes: api/v1/simulations.py and api/v1/investigations.py.

These run the real handlers behind a real HTTP server. The point is that the hosted free paths
execute genuine Nautilus numerics: the responses are compared against direct library calls, and no
credential, provider or budget path is involved. `MODEL_API_KEY` is never read.
"""
import importlib.util
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

from nautilus.protocol import PassiveProtocol, passive, summary  # noqa: E402
from nautilus.simulator import HIDDEN_PLANT, Controller, simulate  # noqa: E402

from nautilus_api.jobs import public_rows, run_investigation  # noqa: E402
from nautilus_api.schema import scenario  # noqa: E402

BODY = {"scenario": {"current_y": 1.0}, "seed": 5, "duration_s": 4.0}
SCALES = (0.035, 0.004, 0.003)


def _serve(name):
    path = ROOT / "api" / "v1" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"vercel_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), module.handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/api/v1/{name}"


@pytest.fixture(scope="module")
def simulations():
    httpd, url = _serve("simulations")
    try:
        yield url
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture(scope="module")
def investigations():
    httpd, url = _serve("investigations")
    try:
        yield url
    finally:
        httpd.shutdown()
        httpd.server_close()


def _post(url, body=None, raw=None, headers=None):
    data = raw if raw is not None else json.dumps(BODY if body is None else body).encode()
    request = urllib.request.Request(url, data=data, method="POST",
                                     headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _expected():
    faults, mission, request = scenario(BODY)
    result = simulate(faults=faults, mission=mission, controller=Controller(), plant=HIDDEN_PLANT)
    observed = public_rows(result.observations)
    protocol = PassiveProtocol(duration_s=mission.duration_s, dt_s=mission.dt_s, scales=SCALES)
    return observed, summary(passive(observed, protocol))


def test_simulation_returns_the_library_result(simulations):
    status, body = _post(simulations)
    assert status == 200
    observed, diagnosis = _expected()
    assert body["observations"] == observed
    assert body["diagnosis"] == diagnosis
    assert body["request"] == scenario(BODY)[2], "the normalized request echoes back"
    assert body["observations"], "real telemetry is required"


def test_investigation_returns_a_finished_job_with_a_ledger(investigations):
    status, body = _post(investigations)
    assert status == 200
    job = body["job"]
    assert job["status"] == "succeeded"
    assert job["error"] is None
    assert job["id"].startswith("sync-")
    faults, mission, request = scenario(BODY)
    assert job["result"] == run_investigation(faults, mission, request)
    assert job["result"]["observations"] == _expected()[0]
    assert job["result"]["investigation"]["ledger"], "the evidence ledger must be populated"
    assert job["result"]["protocol_fingerprint"]


def test_investigation_is_deterministic(investigations):
    first = _post(investigations)[1]["job"]["result"]
    second = _post(investigations)[1]["job"]["result"]
    assert first["investigation"] == second["investigation"]
    assert first["protocol_fingerprint"] == second["protocol_fingerprint"]


def test_malformed_json_is_400(simulations, investigations):
    for url in (simulations, investigations):
        status, body = _post(url, raw=b"{oops")
        assert status == 400
        assert body["error"] == "Invalid JSON"


def test_oversized_body_is_400(simulations, investigations):
    for url in (simulations, investigations):
        status, body = _post(url, body={"scenario": {"current_y": "x" * 5000}})
        assert status == 400
        assert "exceeds" in body["error"]


def test_negative_content_length_is_400(simulations, investigations):
    for url in (simulations, investigations):
        status, body = _post(url, raw=b"", headers={"Content-Length": "-1"})
        assert status == 400
        assert body["error"] == "Invalid Content-Length"


def test_preflight_is_allowed_for_the_configured_origin(simulations, monkeypatch):
    monkeypatch.setenv("NAUTILUS_ALLOWED_ORIGIN", "https://lab.example")
    request = urllib.request.Request(simulations, method="OPTIONS",
                                     headers={"Origin": "https://lab.example"})
    with urllib.request.urlopen(request, timeout=60) as response:
        assert response.status == 204
        assert response.headers["Access-Control-Allow-Origin"] == "https://lab.example"
