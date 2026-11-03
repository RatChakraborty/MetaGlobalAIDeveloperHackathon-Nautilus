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
