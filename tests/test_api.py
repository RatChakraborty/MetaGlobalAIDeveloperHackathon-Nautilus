import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from nautilus_api import server
from nautilus_api.jobs import JobStore, public_rows
from nautilus_api.schema import RequestError, scenario
from nautilus.simulator import simulate, Mission, Faults

HIDDEN_KEYS = {"current_x_mps", "current_y_mps", "port_actual_n", "starboard_actual_n"}


@pytest.fixture(scope="module")
def base_url(tmp_path_factory):
    server.STORE = JobStore(tmp_path_factory.mktemp("jobs"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def _call(url, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


@pytest.mark.parametrize("body", [
    {"scenario": {"current_x": 1.0}},
    {"scenario": {"current_y": 9.0}},
    {"scenario": {"heading_bias_rad": 0.9}},
    {"seed": 1.5},
    {"duration_s": 1000.0},
    {"plant": {"drag_scale": 1.2}},
    {"hidden_truth": True},
    ["not", "an", "object"],
])
def test_scenario_rejects_hidden_or_out_of_range_inputs(body):
    with pytest.raises(RequestError):
        scenario(body)


def test_public_rows_strip_truth_columns():
    result = simulate(faults=Faults(current_y=1.0), mission=Mission(duration_s=4., seed=7))
    truth = {k for row in result.truth for k in row}
    public = set(public_rows(result.observations)[0])
    assert {"current_y_mps", "port_actual_n", "heading_rad"} <= truth
    assert {"current_y_mps", "port_actual_n", "heading_rad"}.isdisjoint(public)
    assert public == set(public_rows(result.observations)[0])


def test_simulation_endpoint_is_public_only(base_url):
    status, out = _call(base_url + "/api/v1/simulations", "POST",
                        {"scenario": {"current_y": 1.0}, "seed": 3, "duration_s": 4.0})
    assert status == 200
    text = json.dumps(out)
    assert not any(k in text for k in HIDDEN_KEYS)
    assert out["diagnosis"]["kind"] in {"identified", "ambiguous", "model_inadequate", "optimization_failure"}


def test_invalid_request_is_400(base_url):
    status, out = _call(base_url + "/api/v1/simulations", "POST", {"scenario": {"current_y": 99}})
    assert status == 400 and "current_y" in out["error"]


def test_unknown_job_is_400(base_url):
    status, _ = _call(base_url + "/api/v1/investigations/" + "a" * 32)
    assert status == 400


MUSE_BODY = {"scenario": {"current_y": 1.0}, "seed": 5, "duration_s": 4.0}
TOKEN = "demo-token-for-tests-only"


@pytest.fixture
def demo(monkeypatch, tmp_path):
    monkeypatch.setenv("NAUTILUS_DEMO_TOKEN", TOKEN)
    monkeypatch.setenv("NAUTILUS_MUSE_DAILY_LIMIT", "2")
    monkeypatch.setattr(server, "STORE", JobStore(tmp_path / "jobs"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def _muse_call(base, body=MUSE_BODY, token=TOKEN):
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base + "/api/v1/muse-investigations", data=data,
                                 method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_muse_route_is_disabled_without_demo_token(demo, monkeypatch):
    monkeypatch.delenv("NAUTILUS_DEMO_TOKEN")
    status, out = _muse_call(demo)
    assert status == 401 and out["error"] == "Unauthorized"


def test_muse_route_rejects_wrong_or_missing_token(demo):
    assert _muse_call(demo, token=None)[0] == 401
    assert _muse_call(demo, token="wrong")[0] == 401


def test_muse_route_rejects_client_supplied_key_and_hidden_fields(demo):
    status, out = _muse_call(demo, {**MUSE_BODY, "api_key": "sk-test-" + "x" * 40})
    assert status == 400
    status, out = _muse_call(demo, {**MUSE_BODY, "plant": {"drag_scale": 1.2}})
    assert status == 400 and "plant" in out["error"]


def test_muse_route_enforces_daily_cap_and_does_not_store_key(demo, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "sk-server-" + "z" * 40)
    statuses = [_muse_call(demo)[0] for _ in range(3)]
    assert statuses == [202, 202, 429]
    stored = (server.STORE.directory / "muse-quota.json").read_text()
    assert json.loads(stored)["count"] == 2
    for path in server.STORE.directory.glob("*.json"):
        assert "sk-server-" not in path.read_text()


def test_muse_run_uses_server_key_and_returns_public_record(monkeypatch):
    from nautilus import muse
    from nautilus.muse import Reply
    from nautilus_api import jobs

    seen = {}

    def fake_generate(self, **kwargs):
        seen["key"] = os.environ.get("MODEL_API_KEY")
        return Reply("r1", self.model, [], {}, 0.0, "incomplete", incomplete_reason="max_output_tokens")

    monkeypatch.setenv("MODEL_API_KEY", "sk-test-" + "y" * 40)
    monkeypatch.setattr(muse.MetaProvider, "generate", fake_generate)
    faults = Faults(current_y=1.0)
    mission = Mission(duration_s=4., seed=5)
    out = jobs.run_muse_investigation(faults, mission, {})
    assert seen["key"] == "sk-test-" + "y" * 40
    text = json.dumps(out)
    assert "sk-test-" not in text
    assert not any(k in text for k in HIDDEN_KEYS)
    assert out["provenance"]["schema_version"] == "nautilus.muse-provenance.v1"


def test_investigation_job_lifecycle(base_url):
    status, out = _call(base_url + "/api/v1/investigations", "POST",
                        {"scenario": {"current_y": 1.0}, "seed": 5, "duration_s": 4.0})
    assert status == 202
    job_id = out["job"]["id"]
    for _ in range(600):
        _, out = _call(base_url + f"/api/v1/investigations/{job_id}")
        if out["job"]["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.2)
    job = out["job"]
    assert job["status"] == "succeeded", job["error"]
    assert "ledger" not in json.dumps(job["request"])
    assert not any(k in json.dumps(job) for k in HIDDEN_KEYS)
    assert job["result"]["investigation"]["ledger"][0]["type"] == "initial_observation"
