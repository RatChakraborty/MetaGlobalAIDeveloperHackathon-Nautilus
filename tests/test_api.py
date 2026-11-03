import json
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


def test_muse_route_requires_key_and_never_persists_it(base_url, tmp_path):
    status, out = _call(base_url + "/api/v1/muse-investigations", "POST",
                        {"scenario": {"current_y": 1.0}, "seed": 5, "duration_s": 4.0})
    assert status == 400 and "api_key" in out["error"]
    secret = "sk-test-" + "x" * 40
    status, out = _call(base_url + "/api/v1/muse-investigations", "POST",
                        {"scenario": {"current_y": 1.0}, "seed": 5, "duration_s": 4.0,
                         "api_key": secret})
    assert status == 202 and out["job"]["status"] == "queued"
    assert secret not in json.dumps(out)
    job_id = out["job"]["id"]
    stored = server.STORE.get(job_id)
    assert secret not in json.dumps(stored)
    assert secret not in (server.STORE.directory / f"{job_id}.json").read_text()
    _call(base_url + f"/api/v1/investigations/{job_id}/cancel", "POST")


def test_muse_route_rejects_hidden_fields(base_url):
    status, out = _call(base_url + "/api/v1/muse-investigations", "POST",
                        {"api_key": "sk-test-" + "x" * 40, "plant": {"drag_scale": 1.2}})
    assert status == 400 and "plant" in out["error"]


def test_muse_run_uses_fake_provider_and_returns_public_record(monkeypatch):
    from nautilus import muse
    from nautilus.muse import Reply
    from nautilus_api import jobs

    seen = {}

    def fake_generate(self, **kwargs):
        seen["key"] = self._api_key
        return Reply("r1", self.model, [], {}, 0.0, "incomplete", incomplete_reason="max_output_tokens")

    monkeypatch.setattr(muse.MetaProvider, "generate", fake_generate)
    faults = Faults(current_y=1.0)
    mission = Mission(duration_s=4., seed=5)
    out = jobs.run_muse_investigation(faults, mission, {}, "sk-test-" + "y" * 40)
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
