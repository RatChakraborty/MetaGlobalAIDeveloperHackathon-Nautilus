"""Stdlib HTTP server exposing bounded simulation and investigation endpoints.

Routes:
  POST /api/v1/simulations            run a simulation, return public telemetry
  POST /api/v1/investigations         queue a scripted investigation job
  POST /api/v1/muse-investigations    queue a live Muse job (demo token + daily cap)
  GET  /api/v1/investigations/{id}    job status and public result
  POST /api/v1/investigations/{id}/cancel

Environment (all optional unless noted):
  NAUTILUS_DEMO_TOKEN        required for live Muse runs; without it the route is disabled
  NAUTILUS_MUSE_DAILY_LIMIT  live runs allowed per UTC day (default 10)
  NAUTILUS_ALLOWED_ORIGIN    the one browser origin allowed to call the API (CORS)
  MODEL_API_KEY              read by nautilus/muse.py on the server only; never sent to clients
"""
import hmac
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from nautilus.protocol import PassiveProtocol, passive, summary
from nautilus.simulator import HIDDEN_PLANT, Controller, simulate

from nautilus_api.jobs import JobStore, public_rows
from nautilus_api.schema import RequestError, scenario

MAX_BODY = 4096
STORE = None
_QUOTA_LOCK = threading.Lock()


def _daily_limit():
    try:
        return max(0, int(os.environ.get("NAUTILUS_MUSE_DAILY_LIMIT", "10")))
    except ValueError:
        return 0


def _reserve_live_run():
    """Count one live run against today's UTC quota. Persisted so a restart cannot reset it."""
    limit = _daily_limit()
    path = Path(STORE.directory) / "muse-quota.json"
    day = time.strftime("%Y-%m-%d", time.gmtime())
    with _QUOTA_LOCK:
        state = json.loads(path.read_text()) if path.exists() else {}
        used = state.get("count", 0) if state.get("day") == day else 0
        if used >= limit:
            return False
        path.write_text(json.dumps({"day": day, "count": used + 1}))
        return True


def _release_live_run():
    path = Path(STORE.directory) / "muse-quota.json"
    day = time.strftime("%Y-%m-%d", time.gmtime())
    with _QUOTA_LOCK:
        state = json.loads(path.read_text()) if path.exists() else {}
        if state.get("day") == day and state.get("count", 0) > 0:
            path.write_text(json.dumps({"day": day, "count": state["count"] - 1}))


def _authorized(headers):
    expected = os.environ.get("NAUTILUS_DEMO_TOKEN", "")
    if not expected:
        return False
    supplied = headers.get("Authorization", "")
    if not supplied.startswith("Bearer "):
        return False
    return hmac.compare_digest(supplied[len("Bearer "):].encode(), expected.encode())


class Handler(BaseHTTPRequestHandler):
    server_version = "NautilusAPI/1"

    def _cors(self):
        allowed = os.environ.get("NAUTILUS_ALLOWED_ORIGIN", "")
        origin = self.headers.get("Origin", "")
        if allowed and origin == allowed:
            self.send_header("Access-Control-Allow-Origin", allowed)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _send(self, status, payload):
        body = json.dumps(payload, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise RequestError("Request body too large")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw or b"{}")
        except json.JSONDecodeError as exc:
            raise RequestError("Invalid JSON") from exc

    def _route(self, method):
        parts = [p for p in self.path.split("?")[0].split("/") if p]
        if parts[:2] != ["api", "v1"]:
            return self._send(404, {"error": "Not found"})
        try:
            if method == "POST" and parts[2:] == ["simulations"]:
                faults, mission, request = scenario(self._body())
                result = simulate(faults=faults, mission=mission, controller=Controller(),
                                  plant=HIDDEN_PLANT)
                observed = public_rows(result.observations)
                protocol = PassiveProtocol(duration_s=mission.duration_s, dt_s=mission.dt_s,
                                           scales=(0.035, 0.004, 0.003))
                return self._send(200, {"request": request, "observations": observed,
                                        "diagnosis": summary(passive(observed, protocol))})
            if method == "POST" and parts[2:] == ["investigations"]:
                faults, mission, request = scenario(self._body())
                return self._send(202, {"job": _public_job(STORE.submit(faults, mission, request))})
            if method == "POST" and parts[2:] == ["muse-investigations"]:
                if not _authorized(self.headers):
                    return self._send(401, {"error": "Unauthorized"})
                faults, mission, request = scenario(self._body())
                if not _reserve_live_run():
                    return self._send(429, {"error": "Daily live-run limit reached; try again tomorrow"})
                try:
                    job = STORE.submit(faults, mission, request, kind="muse")
                except RequestError:
                    _release_live_run()
                    raise
                return self._send(202, {"job": _public_job(job)})
            if method == "GET" and len(parts) == 4 and parts[2] == "investigations":
                return self._send(200, {"job": _public_job(STORE.get(parts[3]))})
            if method == "POST" and len(parts) == 5 and parts[2] == "investigations" and parts[4] == "cancel":
                return self._send(200, {"job": _public_job(STORE.cancel(parts[3]))})
            return self._send(404, {"error": "Not found"})
        except RequestError as exc:
            return self._send(400, {"error": str(exc)})

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def log_message(self, fmt, *args):
        return


def _public_job(record):
    return {k: record[k] for k in ("id", "status", "request", "result", "error")}


def serve(host="127.0.0.1", port=8000, job_dir="api-jobs"):
    global STORE
    STORE = JobStore(job_dir)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    serve(port=int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
