"""Development-only oracle evaluation. Private truth stays on this side.

Run: python evaluate_diagnosis.py --output ../private-results/day2_dev.json
No held-out seeds, failure conditioning, or tuning from held-out results.
The caller chooses a fixed duration; this is not the Day 1 qualified benchmark.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path

from nautilus.diagnosis import FitConfig, diagnose, fit_hypothesis
from nautilus.scenarios import SPLIT_SEEDS, sample_scenario
from nautilus.simulator import Faults, HIDDEN_PLANT, Mission, PlantConfig, simulate


def evaluate_ablations(duration_s=30.0, starts=3):

    cases = [("nominal", Faults(), "nominal"),
             ("sensor", Faults(heading_bias_rad=.4), "heading_bias"),
             ("current", Faults(current_y=.45), "lateral_current")]
    report = []
    for name, faults, hypothesis in cases:
        for label, plant in (("ideal", PlantConfig()), ("perturbed", HIDDEN_PLANT)):
            rows = simulate(faults=faults, mission=Mission(duration_s=duration_s, seed=1020),
                            plant=plant).observations
            fit = fit_hypothesis(rows, hypothesis, config=FitConfig(starts=starts))
            report.append({"case": name, "plant_label": label,
                           "injected_faults": asdict(faults), "fit": asdict(fit),
                           "absolute_parameter_errors": {
                               p: abs(v - getattr(faults, p)) for p, v in fit.parameters.items()}})
            print(name, label, fit.parameters, fit.weighted_rmse, flush=True)
    return report


def evaluate(duration_s=30.0, starts=3):
    config = FitConfig(starts=starts)
    mission = Mission(duration_s=duration_s)
    records = []
    cases = [("nominal", SPLIT_SEEDS["dev"], Faults(), "nominal")]
    for family, offset in (("current", 0), ("thruster", 10), ("sensor", 20)):
        for repeat in range(2):
            seed = SPLIT_SEEDS["dev"] + offset + repeat
            scenario = sample_scenario(seed, (family,))
            faults = scenario.faults
            hypothesis = {"current": "lateral_current", "sensor": "heading_bias"}.get(family)
            if family == "thruster":
                hypothesis = ("port_degradation" if faults.port_efficiency < 1
                              else "starboard_degradation")
            cases.append((f"{family}-{seed}", seed, faults, hypothesis))
    for case_id, seed, faults, true_hypothesis in cases:
        public = simulate(faults=faults, mission=replace(mission, seed=seed),
                          plant=HIDDEN_PLANT).observations

        result = diagnose(public, config=config)
        true_fit = next(f for f in result.fits if f.hypothesis == true_hypothesis)
        errors = {p: abs(v - getattr(faults, p)) for p, v in true_fit.parameters.items()}
        record = {
            "case_id": case_id, "seed": seed, "injected_faults": asdict(faults),
            "true_hypothesis": true_hypothesis,
            "true_family_rank": 1 + result.fits.index(true_fit),
            "absolute_parameter_errors": errors,
            "diagnosis": asdict(result),
        }
        records.append(record)
        print(f"{case_id}: best={result.fits[0].hypothesis}, true_rank="
              f"{record['true_family_rank']}, errors={errors}, "
              f"WRMS={result.fits[0].weighted_rmse:.3f}, inadequate={result.inadequate}",
              flush=True)
    return {"split": "development", "mission": asdict(mission),
            "fit_config": asdict(config), "hidden_plant": asdict(HIDDEN_PLANT),
            "notes": ["Not failure-conditioned; not a held-out accuracy benchmark.",
                      "Current cases include unmodeled longitudinal current.",
                      "Ground truth appears only in this private evaluation report."],
            "cases": records}


def compare_methods(duration_s=30.0, starts=3, methods=("replay", "observer"),
                    nominal_controls=10):

    if not 1 <= nominal_controls <= 50:
        raise ValueError("Use 1..50 development nominal controls")
    configs = {m: FitConfig(method=m, starts=starts) for m in methods}
    cases = [("nominal", 1000, Faults(), "nominal")]
    for family, offset in (("current", 0), ("thruster", 10), ("sensor", 20)):
        for repeat in range(2):
            seed = SPLIT_SEEDS["dev"] + offset + repeat
            faults = sample_scenario(seed, (family,)).faults
            true = {"current": "lateral_current", "sensor": "heading_bias"}.get(family)
            if family == "thruster":
                true = ("port_degradation" if faults.port_efficiency < 1
                        else "starboard_degradation")
            cases.append((f"{family}-{seed}", seed, faults, true))
    cases.extend((f"nominal-{1100+i}", 1100+i, Faults(), "nominal")
                 for i in range(nominal_controls - 1))
    records = []
    for case_id, seed, faults, true in cases:
        observations = simulate(faults=faults, mission=Mission(duration_s=duration_s, seed=seed),
                                plant=HIDDEN_PLANT).observations
        comparisons = {}
        for method, config in configs.items():
            diagnosis = diagnose(observations, config=config)
            true_fit = next(f for f in diagnosis.fits if f.hypothesis == true)
            serialized = asdict(diagnosis)
            for fit in serialized["fits"]:


                for key in ("time_s", "predictions", "residuals"):
                    fit.pop(key)
            comparisons[method] = {
                "true_family_rank": 1 + diagnosis.fits.index(true_fit),
                "absolute_parameter_errors": {
                    p: abs(v-getattr(faults, p)) for p, v in true_fit.parameters.items()},
                "decision": (None if diagnosis.ambiguous or diagnosis.inadequate
                             else diagnosis.fits[0].hypothesis),
                "diagnosis": serialized,
            }
            print(case_id, method, "best", diagnosis.fits[0].hypothesis,
                  "true_rank", comparisons[method]["true_family_rank"],
                  "WRMS", round(diagnosis.fits[0].weighted_rmse, 4),
                  "inadequate", diagnosis.inadequate, flush=True)
        records.append({"case_id": case_id, "seed": seed, "true_hypothesis": true,
                        "injected_faults": asdict(faults), "methods": comparisons})
    summary = {}
    for method in methods:
        controls = [c["methods"][method] for c in records if c["true_hypothesis"] == "nominal"]
        faults = [c["methods"][method] for c in records if c["true_hypothesis"] != "nominal"]
        summary[method] = {
            "nominal_controls": len(controls),
            "raw_fault_winners": sum(c["diagnosis"]["fits"][0]["hypothesis"] != "nominal"
                                     for c in controls),
            "nonabstaining_false_positives": sum(c["decision"] not in (None, "nominal")
                                                for c in controls),
            "nominal_abstentions": sum(c["decision"] is None for c in controls),
            "fault_cases": len(faults),
            "true_family_first": sum(c["true_family_rank"] == 1 for c in faults),
            "fault_abstentions": sum(c["decision"] is None for c in faults),
        }
    return {"split": "development", "duration_s": duration_s,
            "configs": {m: asdict(c) for m, c in configs.items()},
            "notes": ["Private oracle output: do not commit.",
                      "Scores compare models within one method, not across prediction tasks.",
                      "No held-out data used. Raw ranking errors and abstentions are separate."],
            "summary": summary, "cases": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--starts", type=int, default=3)
    parser.add_argument("--ablations", action="store_true")
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--methods", nargs="+", default=["replay", "observer"],
                        choices=["replay", "observer", "observer_discrepancy"])
    parser.add_argument("--nominal-controls", type=int, default=10)
    args = parser.parse_args()
    if Path(__file__).resolve().parent in args.output.resolve().parents:
        parser.error("Private oracle output must be outside the source repository")
    if args.output.exists():
        parser.error("Refusing to overwrite an existing evaluation; choose a new output path")
    report = (compare_methods(args.duration, args.starts, tuple(args.methods), args.nominal_controls)
              if args.compare else evaluate_ablations(args.duration, args.starts) if args.ablations
              else evaluate(args.duration, args.starts))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
