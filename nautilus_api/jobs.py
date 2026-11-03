"""Durable job records and a bounded single-worker queue for investigations.

Each job is a JSON file under the job directory. Records contain only public
fields: status, public telemetry, protocol outcome and the investigation ledger.
"""
import json
import queue
import secrets
import threading
import time
from pathlib import Path

from nautilus.investigation import investigate
from nautilus.experiments import HiddenExperimentBackend
from nautilus.protocol import PassiveProtocol
from nautilus.simulator import HIDDEN_PLANT, Controller, Mission, Experiment, simulate

from nautilus_api.schema import RequestError

MAX_QUEUED = 4
# Demo-mode ceilings for one live Muse run; per-user and global limits are enforced in server.py.
DEMO_MUSE_LIMITS = dict(model_calls=6, actions=8, invalid_calls=3, retries=0,
                        output_tokens_per_call=2048, output_tokens_total=8192,
                        input_tokens_total=60000, request_bytes_total=400_000,
                        timeout_s=60., wall_s=300.)
PUBLIC_COLUMNS = ("time_s", "observed_y_m", "observed_heading_rad", "observed_yaw_rate_radps",
                  "port_command_n", "starboard_command_n")


def public_rows(rows):
    return [{k: float(r[k]) for k in PUBLIC_COLUMNS} for r in rows]


class JobStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._queue = queue.Queue(maxsize=MAX_QUEUED)
        threading.Thread(target=self._worker, daemon=True).start()

    def _path(self, job_id):
        if not isinstance(job_id, str) or not job_id.isalnum() or len(job_id) != 32:
            raise RequestError("Unknown job")
        return self.directory / f"{job_id}.json"

    def _write(self, record):
        path = self._path(record["id"])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, sort_keys=True))
        tmp.replace(path)

    def get(self, job_id):
        path = self._path(job_id)
        if not path.exists():
            raise RequestError("Unknown job")
        return json.loads(path.read_text())

    def submit(self, faults, mission, request, *, kind="scripted", api_key=None):
        with self._lock:
            if self._queue.full():
                raise RequestError("Server is busy; try again shortly")
            job_id = secrets.token_hex(16)
            record = {"id": job_id, "status": "queued", "kind": kind, "request": request,
                      "created_s": time.time(), "result": None, "error": None}
            self._write(record)
            # api_key lives only in this in-memory tuple; it is never written to the record.
            self._queue.put((record, faults, mission, api_key))
            return record

    def cancel(self, job_id):
        with self._lock:
            record = self.get(job_id)
            if record["status"] == "queued":
                record["status"] = "cancelled"
                self._write(record)
            return record

    def _worker(self):
        while True:
            record, faults, mission, api_key = self._queue.get()
            with self._lock:
                if record["status"] == "cancelled":
                    continue
                record["status"] = "running"
                self._write(record)
            try:
                if record["kind"] == "muse":
                    record["result"] = run_muse_investigation(faults, mission, record["request"], api_key)
                else:
                    record["result"] = run_investigation(faults, mission, record["request"])
                record["status"] = "succeeded"
            except Exception as exc:  # bounded, public message only
                record["status"] = "failed"
                record["error"] = "Investigation failed"
            finally:
                api_key = None
            with self._lock:
                self._write(record)


def run_muse_investigation(faults, mission, request, api_key):
    """Live Muse investigation. Uses the same hidden backend and public-only record as the scripted path."""
    from nautilus.controller_context import build_controller_context, initialize_controller_context
    from nautilus.lab_safety import SafeBackend
    from nautilus.laboratory import Laboratory
    from nautilus.muse import MetaProvider
    from nautilus.muse_investigator import Limits, run as muse_run

    result = simulate(faults=faults, mission=mission, controller=Controller(), plant=HIDDEN_PLANT)
    observed = public_rows(result.observations)
    backend = SafeBackend(faults=faults, controller=Controller(), plant=HIDDEN_PLANT,
                          seed=mission.seed, mode="simulation_advisory")
    lab = Laboratory(observed, backend, fit_budget=8, optimization_budget=16,
                     experiment_budget=1, time_budget_s=16., starts=2)
    initialize_controller_context(lab, build_controller_context())
    provider = MetaProvider(api_key=api_key)
    out = muse_run(lab, provider, limits=Limits(**DEMO_MUSE_LIMITS))
    return {"public_record": out["public_record"], "provenance": out["provenance"]}


def run_investigation(faults, mission, request):
    protocol = PassiveProtocol(duration_s=mission.duration_s, dt_s=mission.dt_s,
                               scales=(0.035, 0.004, 0.003))
    result = simulate(faults=faults, mission=mission, controller=Controller(), plant=HIDDEN_PLANT)
    observed = public_rows(result.observations)
    backend = HiddenExperimentBackend(faults=faults, controller=Controller(), plant=HIDDEN_PLANT,
                                      seed=mission.seed, dt_s=mission.dt_s)
    outcome = investigate(observed, protocol, backend.execute)
    return {"observations": observed, "investigation": outcome,
            "protocol_fingerprint": protocol.fingerprint}
