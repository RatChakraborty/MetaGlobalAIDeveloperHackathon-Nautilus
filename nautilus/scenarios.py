from __future__ import annotations


import argparse
import csv
import json

from dataclasses import dataclass, asdict, replace
from pathlib import Path

import numpy as np

from .simulator import (
    Vehicle,
    Faults,
    Controller,
    Mission,
    PlantConfig,
    HIDDEN_PLANT,
    SimulationResult,
    OBSERVATION_FIELDS,
    simulate,
    metrics,
)

FAMILIES = (
    "current",
    "thruster",
    "sensor",
    "controller",
)

CASE_FAMILIES = (
    ("current",),
    ("thruster",),
    ("sensor",),
    ("controller",),
    ("current", "thruster"),
    ("current", "sensor"),
    ("current", "controller"),
    ("thruster", "sensor"),
    ("thruster", "controller"),
    ("sensor", "controller"),
)

SPLIT_SEEDS = {
    "dev": 1000,
    "heldout": 100000,
}

SEED_BLOCK_SIZE = 1000

MIN_RMS_DEGRADATION_M = 0.25
MIN_MAX_ERROR_INCREASE_M = 0.50
MIN_COMPLETION_DELAY_S = 5.0

@dataclass(frozen=True)
class Scenario:

    case_id: str
    families: tuple[str, ...]
    seed: int
    faults: Faults
    controller: Controller


@dataclass
class QualifiedCase:

    scenario: Scenario
    result: SimulationResult

    nominal_metrics: dict
    faulty_metrics: dict

    outcome: str
    qualification_reason: str

def sample_scenario(
    seed: int,
    families: tuple[str, ...],
    case_id: str | None = None,
    baseline_controller: Controller = Controller(),
) -> Scenario:

    if not families:
        raise ValueError(
            "At least one fault family is required."
        )

    if len(set(families)) != len(families):
        raise ValueError(
            "Duplicate fault families are not allowed."
        )

    if not set(families).issubset(FAMILIES):
        raise ValueError(
            f"Unsupported fault family: {families}"
        )

    if seed < 0:
        raise ValueError(
            "Seed must be nonnegative."
        )

    rng = np.random.default_rng(seed)

    fault_params = {}
    controller = baseline_controller


    sorted_families = tuple(sorted(families))

    for family in sorted_families:

        if family == "current":

            direction = float(
                rng.choice([-1.0, 1.0])
            )

            fault_params["current_y"] = float(
                direction * rng.uniform(0.30, 0.70)
            )

            fault_params["current_x"] = float(
                rng.uniform(-0.10, 0.10)
            )

        elif family == "thruster":

            efficiency = float(
                rng.uniform(0.25, 0.65)
            )

            side = str(
                rng.choice(["port", "starboard"])
            )

            fault_params[
                f"{side}_efficiency"
            ] = efficiency

        elif family == "sensor":

            direction = float(
                rng.choice([-1.0, 1.0])
            )

            fault_params["heading_bias_rad"] = float(
                direction * rng.uniform(0.25, 0.55)
            )

        elif family == "controller":

            controller = replace(
                controller,
                heading_kp=float(
                    -rng.uniform(20.0, 45.0)
                ),
            )

    return Scenario(
        case_id=(
            case_id
            if case_id is not None
            else f"case-{seed}"
        ),
        families=sorted_families,
        seed=seed,
        faults=Faults(**fault_params),
        controller=controller,
    )

def evaluate_scenario(
    scenario: Scenario,
    mission: Mission = Mission(),
    vehicle: Vehicle = Vehicle(),
    baseline_controller: Controller = Controller(),
    hidden_plant: PlantConfig = HIDDEN_PLANT,
) -> QualifiedCase:


    seeded_mission = replace(
        mission,
        seed=scenario.seed,
    )

    nominal_result = simulate(
        vehicle=vehicle,
        faults=Faults(),
        controller=baseline_controller,
        mission=seeded_mission,
        plant=hidden_plant,
    )

    faulty_result = simulate(
        vehicle=vehicle,
        faults=scenario.faults,
        controller=scenario.controller,
        mission=seeded_mission,
        plant=hidden_plant,
    )

    nominal_report = metrics(
        nominal_result,
        seeded_mission,
        vehicle,
    )

    faulty_report = metrics(
        faulty_result,
        seeded_mission,
        vehicle,
    )

    if not faulty_report["mission_success"]:

        outcome = "mission_failure"

        if not faulty_report["reached_cable_end"]:
            reason = "did_not_complete_cable"

        else:
            reason = "left_inspection_corridor"

    else:

        rms_increase = (
            faulty_report["rms_cross_track_m"]
            - nominal_report["rms_cross_track_m"]
        )

        max_error_increase = (
            faulty_report["max_abs_cross_track_m"]
            - nominal_report["max_abs_cross_track_m"]
        )

        completion_delay = (
            faulty_report["elapsed_s"]
            - nominal_report["elapsed_s"]
        )

        if rms_increase >= MIN_RMS_DEGRADATION_M:

            outcome = "performance_degradation"
            reason = "increased_rms_tracking_error"

        elif max_error_increase >= MIN_MAX_ERROR_INCREASE_M:

            outcome = "performance_degradation"
            reason = "increased_max_tracking_error"

        elif completion_delay >= MIN_COMPLETION_DELAY_S:

            outcome = "performance_degradation"
            reason = "increased_completion_time"

        else:

            outcome = "unqualified"
            reason = "effect_below_threshold"

    return QualifiedCase(
        scenario=scenario,
        result=faulty_result,
        nominal_metrics=nominal_report,
        faulty_metrics=faulty_report,
        outcome=outcome,
        qualification_reason=reason,
    )

def sample_qualified_case(
    start_seed: int,
    families: tuple[str, ...],
    case_id: str,
    mission: Mission = Mission(),
    vehicle: Vehicle = Vehicle(),
    baseline_controller: Controller = Controller(),
    hidden_plant: PlantConfig = HIDDEN_PLANT,
    max_attempts: int = 100,
    require_failure: bool = True,
) -> QualifiedCase:

    if max_attempts < 1:
        raise ValueError(
            "max_attempts must be at least 1."
        )

    if start_seed < 0:
        raise ValueError(
            "start_seed must be nonnegative."
        )

    for attempt in range(max_attempts):

        seed = start_seed + attempt

        scenario = sample_scenario(
            seed=seed,
            families=families,
            case_id=case_id,
            baseline_controller=baseline_controller,
        )

        evaluated = evaluate_scenario(
            scenario=scenario,
            mission=mission,
            vehicle=vehicle,
            baseline_controller=baseline_controller,
            hidden_plant=hidden_plant,
        )

        if require_failure:

            qualifies = (
                evaluated.outcome == "mission_failure"
            )

        else:

            qualifies = evaluated.outcome in (
                "mission_failure",
                "performance_degradation",
            )

        if qualifies:
            return evaluated

    raise RuntimeError(
        f"Could not generate a qualifying case "
        f"for {families} after {max_attempts} attempts. "
        "Check fault ranges and qualification thresholds."
    )

def write_csv(
    path: Path,
    rows: list[dict],
) -> None:

    if not rows:
        raise ValueError(
            "Cannot export an empty telemetry trace."
        )

    with path.open(
        "w",
        newline="",
    ) as handle:

        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0].keys()),
        )

        writer.writeheader()
        writer.writerows(rows)

def export_case(
    case: QualifiedCase,
    root: Path,
    mission: Mission = Mission(),
    vehicle: Vehicle = Vehicle(),
    baseline_controller: Controller = Controller(),
    hidden_plant: PlantConfig = HIDDEN_PLANT,
) -> None:

    root = Path(root)

    public_dir = (
        root
        / "public"
        / case.scenario.case_id
    )

    private_dir = (
        root
        / "private"
        / case.scenario.case_id
    )

    if public_dir.exists() or private_dir.exists():
        raise FileExistsError(
            f"Case already exists: {case.scenario.case_id}"
        )

    observations = case.result.observations

    if not observations:
        raise ValueError(
            "Cannot export empty observations."
        )

    expected_fields = set(OBSERVATION_FIELDS)

    for row in observations:

        if set(row.keys()) != expected_fields:
            raise ValueError(
                "Observation contains unexpected fields."
            )

    if not case.result.truth:
        raise ValueError(
            "Cannot export empty ground truth."
        )

    if len(observations) != len(case.result.truth):
        raise ValueError(
            "Truth and observation lengths do not match."
        )

    public_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    private_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    write_csv(
        public_dir / "observations.csv",
        observations,
    )

    public_case = {
        "case_id": case.scenario.case_id,
        "domain": "marine",
        "mission_type": "cable_follow",

        "cable_length_m": mission.cable_length_m,
        "cable_half_width_m": mission.cable_half_width_m,

        "nominal_controller": asdict(
            baseline_controller
        ),

        "observation_fields": list(
            OBSERVATION_FIELDS
        ),
    }

    (
        public_dir / "case.json"
    ).write_text(
        json.dumps(
            public_case,
            indent=2,
        ),
        encoding="utf-8",
    )

    write_csv(
        private_dir / "truth.csv",
        case.result.truth,
    )

    private_case = {
        "case_id": case.scenario.case_id,
        "seed": case.scenario.seed,

        "fault_families": list(
            case.scenario.families
        ),

        "faults": asdict(
            case.scenario.faults
        ),

        "actual_controller": asdict(
            case.scenario.controller
        ),

        "baseline_controller": asdict(
            baseline_controller
        ),

        "vehicle": asdict(vehicle),

        "mission": asdict(
            replace(
                mission,
                seed=case.scenario.seed,
            )
        ),

        "hidden_plant": asdict(
            hidden_plant
        ),

        "outcome": case.outcome,

        "qualification_reason": (
            case.qualification_reason
        ),

        "nominal_metrics": case.nominal_metrics,
        "faulty_metrics": case.faulty_metrics,
    }

    (
        private_dir / "ground_truth.json"
    ).write_text(
        json.dumps(
            private_case,
            indent=2,
        ),
        encoding="utf-8",
    )

def generate_split(
    split: str,
    output: Path,
    require_failure: bool = True,
    max_attempts: int = 100,
) -> list[dict]:

    if split not in SPLIT_SEEDS:
        raise ValueError(
            f"Unknown dataset split: {split}"
        )

    if not (
        1 <= max_attempts <= SEED_BLOCK_SIZE
    ):
        raise ValueError(
            f"max_attempts must be between "
            f"1 and {SEED_BLOCK_SIZE}."
        )

    output = Path(output)

    split_root = output / split

    if split_root.exists():
        raise FileExistsError(
            f"Split already exists: {split_root}"
        )

    base_seed = SPLIT_SEEDS[split]

    split_root.mkdir(
        parents=True,
        exist_ok=False,
    )

    records = []

    for index, families in enumerate(CASE_FAMILIES):

        case_id = f"{split}-{index:02d}"

        start_seed = (
            base_seed + index * SEED_BLOCK_SIZE
        )

        case = sample_qualified_case(
            start_seed=start_seed,
            families=families,
            case_id=case_id,
            max_attempts=max_attempts,
            require_failure=require_failure,
        )

        export_case(
            case=case,
            root=split_root,
        )

        records.append({
            "case_id": case_id,
            "families": list(families),
            "seed": case.scenario.seed,
            "outcome": case.outcome,
            "reason": case.qualification_reason,
        })

    private_dir = split_root / "private"

    (
        private_dir / "manifest.json"
    ).write_text(
        json.dumps(
            records,
            indent=2,
        ),
        encoding="utf-8",
    )

    return records

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Generate synthetic Nautilus "
            "robot-failure benchmark cases."
        )
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark_cases"),
        help="Benchmark output directory.",
    )

    parser.add_argument(
        "--split",
        choices=(
            "dev",
            "heldout",
            "both",
        ),
        default="dev",
    )

    parser.add_argument(
        "--allow-degradation",
        action="store_true",
        help=(
            "Accept measurable performance degradation "
            "as well as mission failures."
        ),
    )

    parser.add_argument(
        "--max-attempts",
        type=int,
        default=100,
    )

    args = parser.parse_args()

    splits = (
        ("dev", "heldout")
        if args.split == "both"
        else (args.split,)
    )

    for split in splits:

        records = generate_split(
            split=split,
            output=args.output,
            require_failure=(
                not args.allow_degradation
            ),
            max_attempts=args.max_attempts,
        )

        print(
            f"\nGenerated {split}: "
            f"{len(records)} cases"
        )

        for record in records:

            print(
                record["case_id"],
                record["families"],
                record["outcome"],
            )

    print(
        f"\nArtifacts saved to: "
        f"{args.output.resolve()}"
    )


if __name__ == "__main__":
    main()


