import csv
import json
from dataclasses import replace

import pytest

from nautilus.simulator import (
    Controller,
    Faults,
    Mission,
    HIDDEN_PLANT,
    OBSERVATION_FIELDS,
    metrics,
    simulate,
)

from nautilus.scenarios import (
    FAMILIES,
    CASE_FAMILIES,
    SPLIT_SEEDS,
    sample_scenario,
    evaluate_scenario,
    sample_qualified_case,
    export_case,
    generate_split,
)


def test_all_four_fault_families_are_supported():
    assert set(FAMILIES) == {
        "current",
        "thruster",
        "sensor",
        "controller",
    }


def test_all_single_and_pair_combinations_exist():
    assert len(CASE_FAMILIES) == 10
    assert sum(len(x) == 1 for x in CASE_FAMILIES) == 4
    assert sum(len(x) == 2 for x in CASE_FAMILIES) == 6


def test_sampling_is_deterministic():
    a = sample_scenario(
        1234,
        ("current", "thruster"),
    )

    b = sample_scenario(
        1234,
        ("current", "thruster"),
    )

    assert a == b


def test_family_order_does_not_change_sample():
    a = sample_scenario(
        1234,
        ("current", "thruster"),
    )

    b = sample_scenario(
        1234,
        ("thruster", "current"),
    )

    assert a.faults == b.faults


def test_dev_and_heldout_seeds_are_separate():
    assert abs(
        SPLIT_SEEDS["heldout"]
        - SPLIT_SEEDS["dev"]
    ) >= 10000


@pytest.mark.parametrize(
    "families",
    CASE_FAMILIES,
)
def test_each_single_and_pair_can_generate_failure(families):


    case = sample_qualified_case(
        start_seed=20000 + CASE_FAMILIES.index(families) * 1000,
        families=families,
        case_id="qualification-test",
        max_attempts=30,
        require_failure=True,
    )

    assert case.outcome == "mission_failure"
    assert not case.faulty_metrics["mission_success"]


def test_qualification_uses_candidate_sensor_seed():
    scenario = sample_scenario(
        2345,
        ("current",),
    )

    evaluated = evaluate_scenario(
        scenario,
    )

    mission = replace(
        Mission(),
        seed=scenario.seed,
    )

    rerun = simulate(
        faults=scenario.faults,
        controller=scenario.controller,
        mission=mission,
        plant=HIDDEN_PLANT,
    )

    assert evaluated.faulty_metrics == metrics(
        rerun,
        mission,
    )


def test_controller_fault_changes_gain():
    scenario = sample_scenario(
        1234,
        ("controller",),
    )

    assert scenario.controller.heading_kp < 0
    assert scenario.controller.heading_kp != Controller().heading_kp


def test_sensor_fault_changes_heading_bias():
    scenario = sample_scenario(
        1234,
        ("sensor",),
    )

    assert abs(scenario.faults.heading_bias_rad) >= 0.25


def test_thruster_fault_reduces_one_side():
    scenario = sample_scenario(
        1234,
        ("thruster",),
    )

    efficiencies = (
        scenario.faults.port_efficiency,
        scenario.faults.starboard_efficiency,
    )

    assert min(efficiencies) < 1.0
    assert max(efficiencies) == 1.0


def test_invalid_family_is_rejected():
    with pytest.raises(ValueError):
        sample_scenario(
            1234,
            ("unknown_fault",),
        )


def test_empty_family_list_is_rejected():
    with pytest.raises(ValueError):
        sample_scenario(
            1234,
            (),
        )


def test_qualified_case_is_reproducible():
    kwargs = {
        "start_seed": 30000,
        "families": ("current",),
        "case_id": "repeatable",
        "max_attempts": 20,
    }

    a = sample_qualified_case(**kwargs)
    b = sample_qualified_case(**kwargs)

    assert a.scenario == b.scenario
    assert a.faulty_metrics == b.faulty_metrics
    assert a.result.observations == b.result.observations


def test_public_export_does_not_expose_faults(tmp_path):
    case = sample_qualified_case(
        start_seed=31000,
        families=("current",),
        case_id="privacy-test",
        max_attempts=20,
    )

    export_case(case, tmp_path)

    public_dir = tmp_path / "public" / "privacy-test"
    private_dir = tmp_path / "private" / "privacy-test"

    assert (public_dir / "case.json").exists()
    assert (public_dir / "observations.csv").exists()
    assert (private_dir / "ground_truth.json").exists()
    assert (private_dir / "truth.csv").exists()

    public = json.loads(
        (public_dir / "case.json").read_text()
    )

    assert "faults" not in public
    assert "fault_families" not in public
    assert "hidden_plant" not in public
    assert "seed" not in public
    assert "actual_controller" not in public

    with (
        public_dir / "observations.csv"
    ).open(newline="") as handle:
        reader = csv.DictReader(handle)

        assert set(reader.fieldnames) == set(
            OBSERVATION_FIELDS
        )

    private = json.loads(
        (private_dir / "ground_truth.json").read_text()
    )

    assert "faults" in private
    assert "hidden_plant" in private
    assert "fault_families" in private


def test_export_refuses_overwriting_case(tmp_path):
    case = sample_qualified_case(
        start_seed=32000,
        families=("current",),
        case_id="no-overwrite",
        max_attempts=20,
    )

    export_case(case, tmp_path)

    with pytest.raises(FileExistsError):
        export_case(case, tmp_path)


def test_generate_dev_split(tmp_path):
    records = generate_split(
        split="dev",
        output=tmp_path,
        max_attempts=30,
    )

    assert len(records) == 10

    for record in records:
        assert record["outcome"] == "mission_failure"

        case_id = record["case_id"]

        assert (
            tmp_path
            / "dev"
            / "public"
            / case_id
            / "observations.csv"
        ).exists()

    assert (
        tmp_path
        / "dev"
        / "private"
        / "manifest.json"
    ).exists()
