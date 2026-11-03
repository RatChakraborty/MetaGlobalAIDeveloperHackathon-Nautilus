"""Vercel Python function for the free deterministic investigation.

POST /api/v1/investigations  ->  200 {"job": {...status "succeeded"...}}

The local `nautilus_api/server.py` route queues this work in a background thread and lets the
client poll. A Vercel function has no worker that outlives the response, so the investigation runs
to completion inside the request and the returned job is already terminal: the client's poll loop
exits on the first status check without a second round trip.

This route is deterministic and free. It reads no credential, reserves no budget, and never calls
Muse; live runs live at /api/muse behind the operator token and the Redis ledger.
"""
import os
import secrets
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Matplotlib needs a writable config dir and a non-GUI backend on Vercel.
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ.setdefault("MPLBACKEND", "Agg")

from nautilus_api.schema import RequestError, scenario  # noqa: E402
from nautilus_api.vercel_http import BodyError, preflight, read_json, send_json  # noqa: E402


def completed_job(faults, mission, request):
    """Run one deterministic investigation and shape it like a finished job record."""
    from nautilus_api.jobs import run_investigation

    return {"id": f"sync-{secrets.token_hex(8)}",
            "status": "succeeded",
            "request": request,
            "result": run_investigation(faults, mission, request),
            "error": None}


class handler(BaseHTTPRequestHandler):
    """Vercel invokes this class once per request."""

    server_version = "NautilusInvestigation/1"

    def do_OPTIONS(self):
        preflight(self)

    def do_POST(self):
        try:
            faults, mission, request = scenario(read_json(self))
        except (BodyError, RequestError) as exc:
            return send_json(self, 400, {"error": str(exc)})
        try:
            return send_json(self, 200, {"job": completed_job(faults, mission, request)})
        except Exception:
            return send_json(self, 500, {"error": "Investigation failed"})
