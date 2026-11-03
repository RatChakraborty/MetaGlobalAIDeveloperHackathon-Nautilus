"""Stdlib HTTP server exposing bounded simulation and investigation endpoints.

Routes:
  POST /api/v1/simulations            run a simulation, return public telemetry
  POST /api/v1/investigations         queue an investigation job
  GET  /api/v1/investigations/{id}    job status and public result
  POST /api/v1/investigations/{id}/cancel
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from nautilus.protocol import PassiveProtocol, passive, summary
from nautilus.simulator import HIDDEN_PLANT, Controller, simulate

from nautilus_api.jobs import JobStore, public_rows
from nautilus_api.schema import RequestError, scenario

MAX_BODY = 4096
STORE = None


class Handler(BaseHTTPRequestHandler):
    server_version = "NautilusAPI/1"

    def _send(self, status, payload):
        body = json.dumps(payload, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
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
                body = self._body()
                if not isinstance(body, dict):
                    raise RequestError("Request body must be a JSON object")
                # The key is the only non-scenario field. It is removed before validation and never stored.
                api_key = body.pop("api_key", None)
                if not isinstance(api_key, str) or not api_key:
                    raise RequestError("api_key is required")
                faults, mission, request = scenario(body)
                return self._send(202, {"job": _public_job(STORE.submit(
                    faults, mission, request, kind="muse", api_key=api_key))})
            if method == "GET" and len(parts) == 4 and parts[2] == "investigations":
                return self._send(200, {"job": _public_job(STORE.get(parts[3]))})
            if method == "POST" and len(parts) == 5 and parts[2] == "investigations" and parts[4] == "cancel":
                return self._send(200, {"job": _public_job(STORE.cancel(parts[3]))})
            return self._send(404, {"error": "Not found"})
        except RequestError as exc:
            return self._send(400, {"error": str(exc)})

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
