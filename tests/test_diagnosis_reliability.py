
from dataclasses import replace
import ast
import inspect
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

import nautilus.diagnosis as module
from nautilus.diagnosis import FitConfig, diagnose, fit_hypothesis
from nautilus.simulator import Faults, HIDDEN_PLANT, Mission, simulate

MISSION = Mission(duration_s=8, dt_s=.1)
CONFIG = FitConfig(dt_s=.1, method="observer", starts=1)


@pytest.mark.parametrize("bias", [-.4, .4])
def test_both_bias_signs_recover_under_unprovided_plant_discrepancy(bias):
    rows = simulate(faults=Faults(heading_bias_rad=bias), mission=MISSION,
                    plant=HIDDEN_PLANT).observations
    result = diagnose(rows, config=CONFIG)
    assert result.fits[0].hypothesis == "heading_bias"
    assert result.fits[0].parameters["heading_bias_rad"] == pytest.approx(bias, abs=.015)
    assert not result.inadequate
    assert not result.ambiguous


@pytest.mark.parametrize("seed", [1100, 1101, 1102])
def test_nominal_remains_a_distinct_winning_hypothesis(seed):
    rows = simulate(mission=replace(MISSION, seed=seed), plant=HIDDEN_PLANT).observations
    result = diagnose(rows, config=CONFIG)
    assert result.fits[0].hypothesis == "nominal"
    assert result.fits[0].parameters == {}
    assert result.fits[0].nuisance_parameters == {}
    assert not result.inadequate


def test_predictions_are_scored_before_measured_state_correction():
    rows = simulate(faults=Faults(heading_bias_rad=.3), mission=MISSION).observations


    fit = fit_hypothesis(rows, "nominal", config=CONFIG)
    changed = [dict(r) for r in rows]
    changed[5]["observed_y_m"] += .2
    other = fit_hypothesis(changed, "nominal", config=CONFIG)
    assert other.predictions["observed_y_m"][5] == fit.predictions["observed_y_m"][5]
    assert other.residuals["observed_y_m"][5] - fit.residuals["observed_y_m"][5] == pytest.approx(-.2)
    assert other.predictions["observed_y_m"][6] != fit.predictions["observed_y_m"][6]


def test_observer_is_deterministic_and_ignores_future_samples():
    rows = simulate(mission=MISSION, plant=HIDDEN_PLANT).observations
    fit = fit_hypothesis(rows, "nominal", config=CONFIG)
    assert fit.predictions == fit_hypothesis(rows, "nominal", config=CONFIG).predictions
    changed = [dict(r) for r in rows]
    changed[-1]["observed_heading_rad"] += .4
    other = fit_hypothesis(changed, "nominal", config=CONFIG)
    assert other.predictions == fit.predictions


def test_nuisance_parameters_are_shared_counted_and_separate_from_faults():
    rows = simulate(mission=replace(MISSION, duration_s=3)).observations
    fit = fit_hypothesis(rows, "nominal",
                         config=replace(CONFIG, method="observer_discrepancy"))
    assert fit.parameters == {}
    assert set(fit.nuisance_parameters) == {"actuator_tau_s", "thrust_deadzone_n", "drag_scale"}
    assert fit.penalized_score - fit.weighted_sse == pytest.approx(3*np.log(3*fit.n_observations))
    for name, value in fit.nuisance_parameters.items():
        assert fit.nuisance_bounds[name][0] <= value <= fit.nuisance_bounds[name][1]


def test_zero_excitation_does_not_claim_thruster_identification():
    rows = simulate(mission=replace(MISSION, duration_s=2,
                                    sensor_y_std_m=0, sensor_heading_std_rad=0,
                                    sensor_yaw_rate_std_radps=0)).observations
    for r in rows:
        r["port_command_n"] = r["starboard_command_n"] = 0
    result = diagnose(rows, hypotheses=("port_degradation", "starboard_degradation"), config=CONFIG)
    assert result.ambiguous


def test_diagnosis_has_no_private_imports_or_truth_attribute_access():
    tree = ast.parse(inspect.getsource(module))
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert not imported & {"HIDDEN_PLANT", "Scenario", "simulate", "sample_scenario"}
    assert not {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} & {"truth"}
    rows = simulate(mission=MISSION).observations
    rows[0]["x_m"] = 0
    with pytest.raises(ValueError, match="public"):
        diagnose(rows, config=CONFIG)


def test_oracle_cli_refuses_in_repository_outputs_and_overwrite(tmp_path):
    root = Path(module.__file__).resolve().parents[1]
    inside = root / "evaluation" / "must-not-exist.json"
    proc = subprocess.run([sys.executable, str(root/"evaluate_diagnosis.py"), "--output", str(inside)],
                          capture_output=True, text=True)
    assert proc.returncode != 0
    assert "outside the source repository" in proc.stderr
    assert not inside.exists()
    outside = tmp_path/"existing.json"
    outside.write_text("preserve me")
    proc = subprocess.run([sys.executable, str(root/"evaluate_diagnosis.py"), "--output", str(outside)],
                          capture_output=True, text=True)
    assert proc.returncode != 0
    assert outside.read_text() == "preserve me"


def test_unknown_method_is_rejected():
    with pytest.raises(ValueError):
        fit_hypothesis(simulate(mission=MISSION).observations, "nominal",
                       config=replace(CONFIG, method="unknown"))
