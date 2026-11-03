"""Vercel Python function for the free deterministic simulation.

POST /api/v1/simulations  ->  200 {"request", "observations", "diagnosis"}

This is the same computation as the local `nautilus_api/server.py` route, run synchronously:
Vercel functions have no background worker and no persistent disk, so nothing is queued and no
job store is opened. No credential is read, no budget is reserved and no provider is contacted.
"""
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Matplotlib needs a writable config dir and a non-GUI backend on Vercel.
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ.setdefault("MPLBACKEND", "Agg")

from nautilus.protocol import PassiveProtocol, passive, summary  # noqa: E402
from nautilus.simulator import HIDDEN_PLANT, Controller, simulate  # noqa: E402

from nautilus_api.jobs import public_rows  # noqa: E402
from nautilus_api.schema import RequestError, scenario  # noqa: E402
from nautilus_api.vercel_http import BodyError, preflight, read_json, send_json  # noqa: E402


def run_simulation(faults, mission, request):
    """The free deterministic simulation, exactly as the local server serves it."""
    result = simulate(faults=faults, mission=mission, controller=Controller(), plant=HIDDEN_PLANT)
    observed = public_rows(result.observations)
    protocol = PassiveProtocol(duration_s=mission.duration_s, dt_s=mission.dt_s,
                               scales=(0.035, 0.004, 0.003))
    return {"request": request, "observations": observed,
            "diagnosis": summary(passive(observed, protocol))}


class handler(BaseHTTPRequestHandler):
    """Vercel invokes this class once per request."""

    server_version = "NautilusSimulation/1"

    def do_OPTIONS(self):
        preflight(self)

    def do_POST(self):
        try:
            faults, mission, request = scenario(read_json(self))
        except (BodyError, RequestError) as exc:
            return send_json(self, 400, {"error": str(exc)})
        try:
            return send_json(self, 200, run_simulation(faults, mission, request))
        except Exception:
            return send_json(self, 500, {"error": "Simulation failed"})
