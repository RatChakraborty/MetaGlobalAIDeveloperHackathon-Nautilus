"""Public-only deterministic investigation and an auditable evidence ledger.

No oracle import, private parameters, simulator state or benchmark case labels.
Backend.execute is a capability returning only public observations. All policies
use the same diagnostic engine, allowed requests, budgets and evidence schema.
"""
from __future__ import annotations

from dataclasses import asdict
import math
import random

from .experiments import EXPERIMENT_LIBRARY, separation
from .protocol import diagnose_episodes, digest, passive, summary


def choose(outcome, remaining, protocol, strategy="greedy", rng=None):
    if outcome.kind != "ambiguous" or not remaining:
        return None, {}
    fits = [f for f in outcome.fits if f.hypothesis in outcome.competitive]
    if strategy == "fixed":
        return remaining[0], {}
    if strategy == "random":
        if rng is None:
            raise ValueError("Random policy requires a declared seeded RNG")
        return rng.choice(remaining), {}
    if strategy != "greedy":
        raise ValueError("Unknown investigation strategy")
    scores = {r.key: separation(fits, r, scales=protocol.scales, dt_s=protocol.dt_s)
              for r in remaining}
    # Stable input-order tie break. Do not use hidden labels or truth here.
    selected = max(remaining, key=lambda r: scores[r.key])
    return selected, scores


def investigate(initial, protocol, execute, *, strategy="greedy", seed=0,
                library=EXPERIMENT_LIBRARY, budget=2, time_budget_s=30.,
                initial_outcome=None, refit=diagnose_episodes):
    if (not isinstance(budget, int) or not 0 <= budget <= 2
            or not math.isfinite(time_budget_s) or not 0 <= time_budget_s <= 30):
        raise ValueError("Invalid investigation budget")
    if strategy not in ("greedy", "fixed", "random"):
        raise ValueError("Unknown strategy")
    episodes = [[dict(r) for r in initial if r["time_s"] <= protocol.duration_s + 1e-9]]
    outcome = initial_outcome or passive(episodes[0], protocol)
    ledger = []

    def record(event):
        previous = ledger[-1]["event_hash"] if ledger else None
        event = {**event, "previous_hash": previous, "index": len(ledger)}
        ledger.append({**event, "event_hash": digest(event)})

    record({"type": "initial_observation", "observations": episodes[0],
            "trace_hash": digest(episodes[0]), "diagnosis": summary(outcome),
            "protocol_fingerprint": protocol.fingerprint})
    rng = random.Random(seed)
    remaining, spent, tests = list(library), 0., 0
    while outcome.kind == "ambiguous" and tests < budget:
        affordable = [r for r in remaining if spent + r.duration_s <= time_budget_s + 1e-9]
        if not affordable:
            break
        try:
            request, scores = choose(outcome, affordable, protocol, strategy, rng)
            record({"type": "experiment_selected", "request": asdict(request),
                    "predicted_separation": scores,
                    "prediction_is_evidence": False})
            rows = execute(request)
            # Fit only after a real hidden-system call returns public evidence.
            updated = refit(episodes + [rows], protocol)
            episodes.append(rows)
            tests += 1
            spent += request.duration_s
            remaining.remove(request)
            record({"type": "experiment_observed", "request": asdict(request),
                    "observations": rows, "trace_hash": digest(rows),
                    "diagnosis": summary(updated)})
            outcome = updated
        except (ValueError, FloatingPointError, OverflowError) as exc:
            record({"type": "experiment_error", "error": f"{type(exc).__name__}: {exc}"})
            # Errors must not turn into a supported identification.
            return {"outcome": summary(outcome), "ledger": ledger, "tests": tests,
                    "time_s": spent, "error": str(exc), "decision": None}
    record({"type": "stopped", "reason": outcome.kind,
            "budget_exhausted": tests == budget, "tests": tests, "time_s": spent})
    return {"outcome": summary(outcome), "ledger": ledger, "tests": tests,
            "time_s": spent, "error": None, "decision": outcome.selected}


def verify_ledger(ledger):
    previous = None
    for i, item in enumerate(ledger):
        event = {k:v for k,v in item.items() if k != "event_hash"}
        if (event.get("previous_hash") != previous or event.get("index") != i
                or digest(event) != item.get("event_hash")):
            return False
        if "observations" in event and digest(event["observations"]) != event["trace_hash"]:
            return False
        previous = item["event_hash"]
    return True
