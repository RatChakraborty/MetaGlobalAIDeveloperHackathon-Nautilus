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
import json
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
from nautilus.studio_handoff import HandoffError, validate_handoff  # noqa: E402
from nautilus.studio_muse import Session, run_session  # noqa: E402
from nautilus_api.vercel_http import BodyError, preflight, read_json, send_json  # noqa: E402

MAX_POINTS = 120
DEFAULT_SCENARIOS = 4  # the full development split: no gate is hidden by a partial default


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
    if body.get("engineering_context") is not None:
        if part != "development" or requested is not None:
            raise RequestError("Linked trials use the complete development split")
        from nautilus.engineering_session import linked_trial
        trial = linked_trial(policy, body["engineering_context"], body.get("scenario_request"))
    else:
        trial = paired_trial(policy, part, scenario_ids=set(selected))
    return _trial_result(policy, trial)


def _trial_result(policy, trial):
    part = trial["part"]
    return {"policy": policy, "policy_canonical":json.dumps(policy,sort_keys=True,separators=(",",":"),allow_nan=False), "source": to_source(policy),
            "fingerprint": policy_fingerprint(policy), "part": part,
            "rows": [{k: row[k] for k in ("scenario_id", "baseline", "candidate")} for row in trial["rows"]],
            "gates": trial["decision"]["gates"], "aggregate": trial["decision"]["aggregate"],
            "outcome": trial["outcome"], "acceptance": trial["acceptance"],
            "traces": _traces(trial),
            "methodology": {"matched": True,
                            "note": "Baseline and candidate run the identical scenario, seed and noise stream.",
                            "split": part},
            "session_id": trial.get("session_id"), "evidence_hash": trial.get("evidence_hash"),
            "scenario_fingerprint": trial.get("scenario_fingerprint")}


def _muse_payload(body):
    handoff = body.get("handoff")
    if handoff is not None:
        try:
            handoff = validate_handoff(handoff)
        except HandoffError as exc:
            raise RequestError(f"invalid investigation handoff: {exc}")
    host = Session(handoff=handoff, engineering_context=body.get("engineering_context"),
                   scenario_request=body.get("scenario_request"))
    session = run_session(session=host)
    selected = (session['final'] or {}).get('candidate_id')
    selected_trial = (_trial_result(host.candidates[selected]['policy'],host.results[selected])
                      if selected in host.results else None)
    selected_robustness = None
    if selected in host.robustness:
        from nautilus.engineering_session import final_decision
        report = host.robustness[selected]
        decision = final_decision(host.results[selected],report)
        decision['model_decision'] = session['final']['decision']
        if session['final']['decision'] != 'recommend':
            decision['decision'] = 'withhold'
        selected_robustness = {'rows':[{k:r[k] for k in ('scenario_id','baseline','candidate')} for r in report['rows']],'gates':report['decision']['gates'],
                               'outcome':report['outcome'],'fingerprint':report['fingerprint'],
                               'host_decision':decision}

    return {"selected_trial":selected_trial,"selected_robustness":selected_robustness,
            "final": session["final"], "stopped": session["stopped"],
            "transcript": session["transcript"], "budget": session["budget"],
            "candidates": session["candidates"], "results": session["results"],
            "robustness": session["robustness"], "mock": True,
            "live_available": session["live_available"], "model": session["model"],
            "provider_calls": session["provider_calls"],
            "session_id": session.get("session_id"), "evidence_hash": session.get("evidence_hash"),
            "disclosure": "Deterministic mocked Muse provider. No model API call was made and no credits were spent."}


def dispatch(body):
    if type(body) is not dict:
        raise RequestError("body must be an object")
    action = body.get("action")
    allowed = {'action'} if action == 'baseline' else {'action','source','policy','params','name','scenarios','part','handoff','engineering_context','scenario_request'}
    if set(body) - allowed:
        raise RequestError('Unknown Studio request fields')
    if body.get('engineering_context') is not None:
        from nautilus.engineering_session import validate_context
        validate_context(body['engineering_context'])
    if action == "baseline":
        policy = baseline_policy()
        return {"policy": policy, "policy_canonical":json.dumps(policy,sort_keys=True,separators=(",",":"),allow_nan=False), "source": to_source(policy),
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
        from nautilus.engineering_session import linked_trial, final_decision
        development = (linked_trial(policy, body["engineering_context"], body.get("scenario_request"))
                       if body.get("engineering_context") is not None else paired_trial(policy))
        host_decision = final_decision(development, report)
        return {"policy": policy, "part": report["part"],
                "fingerprint": policy_fingerprint(policy), "host_decision": host_decision,
                "rows": [{k: row[k] for k in ("scenario_id", "baseline", "candidate")} for row in report["rows"]],
                "gates": report["decision"]["gates"], "aggregate": report["decision"]["aggregate"],
                "outcome": report["outcome"],
                "note": "Held-out split: reported as evidence, never used to select a candidate."}
    if action == "muse":
        return _muse_payload(body)
    raise RequestError("unknown action")


class handler(BaseHTTPRequestHandler):
    server_version = "NautilusStudio/1"

    def do_OPTIONS(self):
        preflight(self)

    def do_POST(self):
        try:
            body = read_json(self, limit=65536)
        except BodyError as exc:
            return send_json(self, 400, {"error": str(exc)})
        try:
            return send_json(self, 200, dispatch(body))
        except RequestError as exc:
            return send_json(self, 400, {"error": str(exc)})
        except (PolicyError, ValueError) as exc:
            return send_json(self, 422, {"error": str(exc)})
        except Exception:
            return send_json(self, 500, {"error": "Studio evaluation failed"})
