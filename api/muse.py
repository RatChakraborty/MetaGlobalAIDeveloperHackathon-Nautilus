"""Vercel Python function for live Muse investigations.

POST /api/muse  (Authorization: Bearer NAUTILUS_DEMO_TOKEN)

One request runs one investigation to completion inside this function and returns the public
result. Vercel functions have no background workers and no persistent local disk, so the
budget lives in Upstash Redis (nautilus_api/ledger.py), and the run's worst-case reservation
is settled to measured cost in a `finally` block.

Environment (server-side only):
  NAUTILUS_DEMO_TOKEN, MODEL_API_KEY, UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN,
  NAUTILUS_ALLOWED_ORIGIN (optional CORS origin), NAUTILUS_MUSE_MONTHLY_BUDGET_USD (optional)
"""
import json
import os
import secrets
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Matplotlib needs a writable config dir and a non-GUI backend on Vercel.
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ.setdefault("MPLBACKEND", "Agg")

from nautilus_api import budget, ledger  # noqa: E402
from nautilus_api.server import _authorized  # noqa: E402
from nautilus_api.schema import RequestError, scenario  # noqa: E402

MAX_BODY = 4096


def _run_live(faults, mission, request):
    """Reserve, run and settle one live run. Returns (status, payload)."""
    from nautilus_api.jobs import _settle_muse, run_muse_investigation

    run_id = secrets.token_hex(16)
    reserved = budget.rounded_up_cents(budget.reservation_usd())
    if not ledger.reserve(budget.DEMO_BUCKET, reserved, run_id=run_id,
                          daily_runs=budget.PER_USER_DAILY_RUNS,
                          daily_usd=budget.PER_USER_DAILY_USD,
                          monthly_usd=budget.monthly_budget_usd()):
        return 429, {"error": "Live-run budget reached; try again later"}
    result = None
    try:
        result = run_muse_investigation(faults, mission, request)
        return 200, {"result": result, "request": request}
    except Exception:  # public message only; provider detail never leaves the server
        return 500, {"error": "Investigation failed"}
    finally:
        # Settle to measured usage on success; keep the worst-case hold on failure.
        try:
            _settle_muse(result, run_id)
        except Exception:
            pass  # the hold stays at its worst case, which is the conservative outcome


class handler(BaseHTTPRequestHandler):
    server_version = "NautilusMuse/1"

    def _cors(self):
        allowed = os.environ.get("NAUTILUS_ALLOWED_ORIGIN", "")
        if allowed and self.headers.get("Origin", "") == allowed:
            self.send_header("Access-Control-Allow-Origin", allowed)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

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

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        if not _authorized(self.headers):
            return self._send(401, {"error": "Unauthorized"})
        try:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError as exc:
                raise RequestError("Invalid Content-Length") from exc
            if length < 0 or length > MAX_BODY:
                raise RequestError("Request body too large" if length > 0 else "Invalid Content-Length")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError as exc:
                raise RequestError("Invalid JSON") from exc
            faults, mission, request = scenario(body)
        except RequestError as exc:
            return self._send(400, {"error": str(exc)})
        try:
            status, payload = _run_live(faults, mission, request)
        except Exception:
            return self._send(503, {"error": "Budget service unavailable"})
        return self._send(status, payload)

    def log_message(self, fmt, *args):
        return
