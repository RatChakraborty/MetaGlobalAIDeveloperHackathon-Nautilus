"""Vercel Python function for the free, deterministic Control Policy Studio.

POST /api/v1/studio  {"action": ...}

Actions (all free, deterministic, no credential, no provider contact):
  baseline                                   -> the reference controller IR and readable source
  validate   {"source": "..."} | {"policy": {...}}  -> compiled IR, source, validity
  trial      {"policy"|"source", "scenarios": [...]}-> matched paired trial vs baseline
  robustness {"policy"|"source"}             -> held-out split evidence (not used for selection)
  muse       {}                              -> mocked Muse engineering session (offline provider)

Every number is produced by the real simulator through nautilus.studio. Nothing here executes
untrusted Python: policies are JSON IR compiled by nautilus.policy_source from a whitelisted
expression subset, or validated IR documents, and interpreted by nautilus.policy_ir.
"""
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ.setdefault("MPLBACKEND", "Agg")

from nautilus.policy_ir import PolicyError, baseline_policy, validate  # noqa: E402
from nautilus.policy_source import from_source, to_source  # noqa: E402
from nautilus.studio import cases, paired_trial, policy_fingerprint, robustness  # noqa: E402
from nautilus.studio_muse import run_session  # noqa: E402
from nautilus_api.vercel_http import BodyError, preflight, read_json, send_json  # noqa: E402

MAX_POINTS = 120
DEFAULT_SCENARIOS = 2


class RequestError(ValueError):
    pass


def _policy(body):
    if "source" in body:
        params = body.get("params") or {}
        if type(params) is not dict:
            raise RequestError("params must be an object")
        return from_source(body["source"], params=params, name=str(body.get("name", "candidate"))[:40])
    if "policy" in body:
        return validate(body["policy"])
    raise RequestError("provide controller source or policy")


def _traces(trial):
    """Downsampled public trajectories for plotting; truth rows only for display."""
    out = {}
    for scenario_id, result in trial["traces"].items():
        truth, observed = result.truth, result.observations
        stride = max(1, -(-len(truth) // MAX_POINTS))
        out[scenario_id] = {
            "time_s": [round(truth[i]["time_s"], 3) for i in range(0, len(truth), stride)],
            "y_m": [round(truth[i]["y_m"], 4) for i in range(0, len(truth), stride)],
            "heading_rad": [round(truth[i]["heading_rad"], 4) for i in range(0, len(truth), stride)],
            "port_command_n": [round(observed[i]["port_command_n"], 3) for i in range(0, len(observed), stride)],
            "starboard_command_n": [round(observed[i]["starboard_command_n"], 3)
                                    for i in range(0, len(observed), stride)],
        }
    return out


def _trial_payload(body):
    policy = _policy(body)
    part = body.get("part", "development")
    if part not in ("development", "held_out"):
        raise RequestError("unsupported evaluation split")
    requested = body.get("scenarios")
    if requested is not None and (type(requested) is not list or len(requested) > 4
                                  or not all(isinstance(item, str) for item in requested)):
        raise RequestError("scenarios must be a list of at most four identifiers")
    available = [case.identifier for case in cases(part)]
    selected = list(requested or available[:DEFAULT_SCENARIOS])
    if not set(selected) <= set(available):
        raise RequestError("unknown scenario identifier for this split")
    trial = paired_trial(policy, part, scenario_ids=set(selected))
    return {"policy": policy, "source": to_source(policy),
            "fingerprint": policy_fingerprint(policy), "part": part,
            "rows": [{k: row[k] for k in ("scenario_id", "baseline", "candidate")} for row in trial["rows"]],
            "gates": trial["decision"]["gates"], "aggregate": trial["decision"]["aggregate"],
            "outcome": trial["outcome"], "acceptance": trial["acceptance"],
            "traces": _traces(trial),
            "methodology": {"matched": True,
                            "note": "Baseline and candidate run the identical scenario, seed and noise stream.",
                            "split": part}}


def _muse_payload():
    session = run_session()
    return {"final": session["final"], "stopped": session["stopped"],
            "transcript": session["transcript"], "budget": session["budget"],
            "candidates": session["candidates"], "results": session["results"],
            "robustness": session["robustness"], "mock": True,
            "live_available": session["live_available"], "model": session["model"],
            "provider_calls": session["provider_calls"],
            "disclosure": "Deterministic mocked Muse provider. No model API call was made and no credits were spent."}


def dispatch(body):
    if type(body) is not dict:
        raise RequestError("body must be an object")
    action = body.get("action")
    if action == "baseline":
        policy = baseline_policy()
        return {"policy": policy, "source": to_source(policy),
                "fingerprint": policy_fingerprint(policy),
                "supported": {"references": ["y_m", "heading_rad", "yaw_rate_radps", "integral_y",
                                             "filtered_yaw_rate", "lookahead_m", "max_heading_rad",
                                             "cruise_thrust_n", "max_thrust_n", "lever_arm_m"],
                              "functions": ["min", "max", "abs", "atan2", "clip", "wrap", "if", "sat"],
                              "limits": {"nodes": 96, "depth": 14}},
                "live_muse": False}
    if action == "validate":
        try:
            policy = _policy(body)
        except PolicyError as exc:
            return {"valid": False, "error": str(exc)}
        return {"valid": True, "policy": policy, "source": to_source(policy),
                "fingerprint": policy_fingerprint(policy)}
    if action == "trial":
        return _trial_payload(body)
    if action == "robustness":
        policy = _policy(body)
        report = robustness(policy)
        report.pop("traces", None)
        return {"policy": policy, "part": report["part"],
                "rows": [{k: row[k] for k in ("scenario_id", "baseline", "candidate")} for row in report["rows"]],
                "gates": report["decision"]["gates"], "aggregate": report["decision"]["aggregate"],
                "outcome": report["outcome"],
                "note": "Held-out split: reported as evidence, never used to select a candidate."}
    if action == "muse":
        return _muse_payload()
    raise RequestError("unknown action")


class handler(BaseHTTPRequestHandler):
    server_version = "NautilusStudio/1"

    def do_OPTIONS(self):
        preflight(self)

    def do_POST(self):
        try:
            body = read_json(self, limit=16384)
        except BodyError as exc:
            return send_json(self, 400, {"error": str(exc)})
        try:
            return send_json(self, 200, dispatch(body))
        except RequestError as exc:
            return send_json(self, 400, {"error": str(exc)})
        except PolicyError as exc:
            return send_json(self, 422, {"error": str(exc)})
        except Exception:
            return send_json(self, 500, {"error": "Studio evaluation failed"})
