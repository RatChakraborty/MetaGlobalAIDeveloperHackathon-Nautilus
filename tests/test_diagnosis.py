from dataclasses import replace

import numpy as np
import pytest

from nautilus.diagnosis import CHANNELS, FitConfig, diagnose, fit_hypothesis
from nautilus.simulator import Faults, HIDDEN_PLANT, Mission, simulate


MISSION = Mission(duration_s=6, dt_s=0.1, sensor_y_std_m=0,
                  sensor_heading_std_rad=0, sensor_yaw_rate_std_radps=0)
CONFIG = FitConfig(dt_s=0.1, starts=1)


@pytest.mark.parametrize("hypothesis,param,value", [
    ("lateral_current", "current_y", -0.45),
    ("port_degradation", "port_efficiency", 0.4),
    ("starboard_degradation", "starboard_efficiency", 0.55),
    ("heading_bias", "heading_bias_rad", 0.37),
])
def test_ideal_closed_loop_recovery(hypothesis, param, value):
    rows = simulate(faults=Faults(**{param: value}), mission=MISSION).observations
    fit = fit_hypothesis(rows, hypothesis, config=CONFIG)
    assert fit.converged
    assert fit.parameters[param] == pytest.approx(value, abs=1e-5)
    assert fit.weighted_rmse < 1e-5
    assert fit.bounds[param][0] <= fit.parameters[param] <= fit.bounds[param][1]
    assert fit.channels == CHANNELS
    assert fit.evaluations > 0


def test_noisy_bias_conditions_on_actual_actions_and_is_deterministic():
    mission = replace(MISSION, sensor_y_std_m=.035,
                      sensor_heading_std_rad=.004, sensor_yaw_rate_std_radps=.003)
    rows = simulate(faults=Faults(heading_bias_rad=-.4), mission=mission).observations
    first = fit_hypothesis(rows, "heading_bias", config=CONFIG)
    second = fit_hypothesis(rows, "heading_bias", config=CONFIG)
    assert first.parameters["heading_bias_rad"] == pytest.approx(-.4, abs=.003)
    assert first.predictions == second.predictions
    assert first.weighted_sse == second.weighted_sse
    # Replayed noisy commands make physical y and rate exact for the ideal plant.
    assert first.rmse[CHANNELS[0]] < .05
    assert first.rmse[CHANNELS[2]] < .005


def test_fractional_endpoint_does_not_require_x_or_candidate_termination():
    rows = simulate(faults=Faults(current_y=.4),
                    mission=replace(MISSION, cable_length_m=1.1)).observations
    assert rows[-1]["time_s"] < MISSION.duration_s
    fit = fit_hypothesis(rows, "lateral_current", config=CONFIG)
    assert fit.n_observations == len(rows) - 1
    assert fit.fit_window_s[1] == rows[-2]["time_s"]
    assert fit.parameters["current_y"] == pytest.approx(.4, abs=1e-5)
    assert any("fractional" in w for w in fit.warnings)


@pytest.mark.parametrize("mutation", ["truth", "missing", "gap", "duplicate", "nan", "offset"])
def test_invalid_or_privileged_trace_rejected(mutation):
    rows = simulate(mission=MISSION).observations
    if mutation == "truth":
        rows[0]["x_m"] = 0
    elif mutation == "missing":
        del rows[0]["port_command_n"]
    elif mutation == "gap":
        del rows[3]
    elif mutation == "duplicate":
        rows[2]["time_s"] = rows[1]["time_s"]
    elif mutation == "nan":
        rows[0]["observed_y_m"] = float("nan")
    else:
        for row in rows:
            row["time_s"] += 1
    with pytest.raises(ValueError):
        fit_hypothesis(rows, "heading_bias", config=CONFIG)


def test_common_window_and_ambiguity_without_excitation():
    rows = simulate(mission=MISSION).observations
    for row in rows:
        row["port_command_n"] = row["starboard_command_n"] = 0
    d = diagnose(rows, hypotheses=("port_degradation", "starboard_degradation"),
                 config=replace(CONFIG, end_s=2))
    assert d.ambiguous
    assert len(d.competitive) == 2
    assert all(f.fit_window_s == (0, 2) for f in d.fits)


def test_heading_wrap_is_not_a_two_pi_error():
    rows = simulate(faults=Faults(heading_bias_rad=.35), mission=MISSION).observations
    for row in rows:
        row["observed_heading_rad"] += 2 * np.pi
    fit = fit_hypothesis(rows, "heading_bias", config=CONFIG)
    assert fit.parameters["heading_bias_rad"] == pytest.approx(.35, abs=1e-5)


def test_missing_family_and_failed_optimizer_do_not_force_conclusion():
    rows = simulate(faults=Faults(heading_bias_rad=.5), mission=MISSION,
                    plant=HIDDEN_PLANT).observations
    d = diagnose(rows, hypotheses=("nominal", "port_degradation"), config=CONFIG)
    assert d.inadequate
    failed = fit_hypothesis(rows, "heading_bias", config=replace(CONFIG, max_nfev=1))
    assert not failed.converged
    assert any("did not converge" in w for w in failed.warnings)


def test_hidden_plant_recovery_is_approximate_and_reports_misfit():
    # This is a mismatch/abstention check, not a claim of calibrated accuracy.
    rows = simulate(faults=Faults(heading_bias_rad=.4),
                    mission=replace(MISSION, duration_s=8,
                                    sensor_y_std_m=.035,
                                    sensor_heading_std_rad=.004,
                                    sensor_yaw_rate_std_radps=.003),
                    plant=HIDDEN_PLANT).observations
    result = diagnose(rows, config=CONFIG)
    assert result.fits[0].hypothesis == "heading_bias"
    assert result.fits[0].parameters["heading_bias_rad"] == pytest.approx(.4, abs=.05)
    assert result.inadequate
    assert any("abstain" in w for w in result.warnings)


@pytest.mark.parametrize("config", [replace(CONFIG, scales=(0,.1,.1)),
                                   replace(CONFIG, dt_s=float("nan")),
                                   replace(CONFIG, end_s=.01),
                                   replace(CONFIG, starts=0)])
def test_configuration_validation(config):
    with pytest.raises(ValueError):
        diagnose(simulate(mission=MISSION).observations, config=config)
