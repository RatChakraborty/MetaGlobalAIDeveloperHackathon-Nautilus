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

    def submit(self, faults, mission, request):
        with self._lock:
            if self._queue.full():
                raise RequestError("Server is busy; try again shortly")
            job_id = secrets.token_hex(16)
            record = {"id": job_id, "status": "queued", "request": request,
                      "created_s": time.time(), "result": None, "error": None}
            self._write(record)
            self._queue.put((record, faults, mission))
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
            record, faults, mission = self._queue.get()
            with self._lock:
                if record["status"] == "cancelled":
                    continue
                record["status"] = "running"
                self._write(record)
            try:
                record["result"] = run_investigation(faults, mission, record["request"])
                record["status"] = "succeeded"
            except Exception as exc:  # bounded, public message only
                record["status"] = "failed"
                record["error"] = f"{type(exc).__name__}: {exc}"
            with self._lock:
                self._write(record)


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
