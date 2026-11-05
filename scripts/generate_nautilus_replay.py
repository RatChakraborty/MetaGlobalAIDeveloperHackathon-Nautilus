#!/usr/bin/env python3
"""Export aligned, actual Nautilus simulator observations and pose for 3D replay."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from nautilus.simulator import Faults, Mission, simulate

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")

def export_run(name, faults, mission, output):
    result = simulate(faults=faults, mission=mission)
    fields = ("time_s", "observed_y_m", "observed_heading_rad", "observed_yaw_rate_radps", "port_command_n", "starboard_command_n")
    obs = [{k: float(row[k]) for k in fields} for row in result.observations]
    poses = [{k: float(row[k]) for k in ("time_s", "x_m", "y_m", "heading_rad")} for row in result.truth]
    if len(obs) < 2 or len(obs) != len(poses) or obs[0]["time_s"] != 0:
        raise ValueError("Invalid simulator observation and pose lengths")
    if any(a["time_s"] != b["time_s"] for a, b in zip(obs, poses)):
        raise ValueError("Mismatched public and spatial timestamps")
    if any(not math.isfinite(v) for row in obs + poses for v in row.values()):
        raise ValueError("Nonfinite simulator output")
    event = {"index": 0, "type": "observation", "previous_hash": None,
             "origin": "Actual local Nautilus simulator run; observations only", "observations": obs}
    body = canonical(event)
    h = hashlib.sha256(body.encode("utf-8")).hexdigest()
    run_id = hashlib.sha256((name + ":" + h).encode("utf-8")).hexdigest()
    public = {"schema_version": "nautilus.public-investigation.v1",
              "run_id": run_id, "source_kind": "local_deterministic_simulation_export",
              "disclosure": "Public observations only. No diagnosis or verified controller repair.",
              "ledger": [{"hash": h, "body_canonical": body}]}
    visual = {"schema_version": "nautilus.visualization-only.v1",
              "run_id": run_id, "label": name + " actual simulated pose, visualization only",
              "reference": {"cable_length_m": float(mission.cable_length_m),
                            "cable_half_width_m": float(mission.cable_half_width_m),
                            "source": "Simulator mission, cable centerline y=0"},
              "samples": poses}
    write(output / (name + ".public.json"), public)
    write(output / (name + ".visualization.json"), visual)
    return {"name": name, "run_id": run_id, "samples": len(poses)}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path.home() / "Downloads" / "nautilus-replay")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--current-y", type=float, default=-0.3)
    parser.add_argument("--duration", type=float, default=80.0)
    args = parser.parse_args()
    if not -2.5 <= args.current_y <= 2.5:
        parser.error("--current-y must be between -2.5 and 2.5")
    if not 5 <= args.duration <= 1200:
        parser.error("--duration must be between 5 and 1200")
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    mission = Mission(seed=args.seed, duration_s=args.duration)
    runs = [export_run("disturbance", Faults(current_y=args.current_y), mission, output),
            export_run("reference", Faults(), mission, output)]
    write(output / "replay_manifest.json", {
        "source": "Actual local Nautilus simulator", "seed": args.seed,
        "current_y_mps": args.current_y, "runs": runs,
        "notice": "Spatial truth is visualization only, not public diagnostic input"})
    for run in runs:
        print(run["name"], run["samples"], "samples", run["run_id"][:12])
    print("Replay files written to", output)

if __name__ == "__main__":
    main()
