"""Frozen public-only passive outcomes; no oracle imports or private labels."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from .diagnosis import FitConfig, HYPOTHESES, fit_evidence


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class PassiveProtocol:
    name: str = "observer-v1"
    duration_s: float = 30.0
    dt_s: float = 0.05
    scales: tuple[float, float, float] = (0.035, 0.004, 0.003)
    starts: int = 3
    max_nfev: int = 60
    adequacy_wrms: float = 2.0
    gap: float = 6.0
    hypotheses: tuple[str, ...] = tuple(HYPOTHESES)

    def __post_init__(self):
        if (not math.isfinite(self.duration_s) or self.duration_s < 2*self.dt_s
                or not 0 < self.dt_s <= .2 or self.starts < 1 or self.max_nfev < 1
                or not math.isfinite(self.gap) or self.gap < 0
                or not math.isfinite(self.adequacy_wrms) or self.adequacy_wrms <= 0
                or len(self.scales) != 3 or any(not math.isfinite(x) or x <= 0 for x in self.scales)
                or not self.hypotheses or len(set(self.hypotheses)) != len(self.hypotheses)
                or any(h not in HYPOTHESES for h in self.hypotheses)):
            raise ValueError("Invalid passive protocol")

    def config(self):
        return FitConfig(method="observer", dt_s=self.dt_s, scales=self.scales,
                         starts=self.starts, max_nfev=self.max_nfev,
                         inadequacy_wrms=self.adequacy_wrms, ambiguity_delta=self.gap)

    @property
    def fingerprint(self):
        return digest(asdict(self))


@dataclass
class Outcome:
    kind: str
    selected: str | None
    competitive: list[str]
    fits: list
    reasons: list[str]


def classify(fits, protocol):
    """Any missing/failed comparison blocks identification or ambiguity.

    Ambiguity is only among converged, individually adequate explanations.
    Private correctness is deliberately not a public outcome category.
    """
    if (len(fits) != len(protocol.hypotheses)
            or {f.hypothesis for f in fits} != set(protocol.hypotheses)
            or any(not f.converged or not math.isfinite(f.penalized_score)
                   or not math.isfinite(f.weighted_rmse) for f in fits)):
        return Outcome("optimization_failure", None, [], fits, ["Incomplete or nonconverged comparison"])
    adequate = sorted([f for f in fits if f.weighted_rmse <= protocol.adequacy_wrms],
                      key=lambda f: (f.penalized_score, f.hypothesis))
    if not adequate:
        return Outcome("model_inadequate", None, [], fits, ["No individually adequate explanation"])
    competitive = [f.hypothesis for f in adequate
                   if f.penalized_score <= adequate[0].penalized_score + protocol.gap]
    ambiguous = len(competitive) >= 2
    return Outcome("ambiguous" if ambiguous else "identified",
                   None if ambiguous else competitive[0], competitive, fits,
                   ["Score gap is a frozen heuristic, not a calibrated physical noise floor."])


def diagnose_episodes(episodes, protocol):
    try:
        episodes = sorted(episodes, key=digest)
        fits = [fit_evidence(episodes, h, config=protocol.config()) for h in protocol.hypotheses]
        return classify(fits, protocol)
    except (ValueError, FloatingPointError, OverflowError, np.linalg.LinAlgError) as exc:
        return Outcome("optimization_failure", None, [], [], [f"{type(exc).__name__}: {exc}"])


def passive(observations, protocol):
    window = [dict(r) for r in observations if r["time_s"] <= protocol.duration_s + 1e-9]
    return diagnose_episodes([window], protocol)


def summary(outcome):
    """Compact public output: fitted estimates are evidence, never oracle labels."""
    return {"kind": outcome.kind, "selected": outcome.selected,
            "competitive": outcome.competitive, "reasons": outcome.reasons,
            "fits": [{"hypothesis": f.hypothesis, "parameters": f.parameters,
                      "converged": f.converged, "score": f.penalized_score,
                      "wrms": f.weighted_rmse, "warnings": f.warnings,
                      "evaluations": f.evaluations,
                      "episode_lengths": f.episode_lengths} for f in outcome.fits]}


def source_fingerprint(root):
    root = Path(root)
    paths = sorted((root/"nautilus").glob("*.py")) + [root/"evaluate_active.py"]
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
