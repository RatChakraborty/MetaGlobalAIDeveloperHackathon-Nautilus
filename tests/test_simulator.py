


import csv
import json
import math
from dataclasses import replace

import numpy as np
import pytest

from nautilus.simulator import (
    Vehicle,
    Faults,
    Controller,
    Mission,
    PlantConfig,
    HIDDEN_PLANT,
    Experiment,
    SimulationResult,
    OBSERVATION_FIELDS,
    wrap_angle,
    dynamics,
    command,
    actuator_step,
    simulate,
    metrics,
    save_run,
)

FAST = Mission(
    duration_s=20.0,
    dt_s=0.05,
    sensor_y_std_m=0.0,
    sensor_heading_std_rad=0.0,
    sensor_yaw_rate_std_radps=0.0,
    seed=42,
)

NOISELESS = Mission(
    duration_s=100.0,
    dt_s=0.05,
    sensor_y_std_m=0.0,
    sensor_heading_std_rad=0.0,
    sensor_yaw_rate_std_radps=0.0,
    seed=42,
)


def truth_column(result, name):
    return np.array(
        [row[name] for row in result.truth],
        dtype=float,
    )

def observed_column(result, name):
    return np.array(
        [row[name] for row in result.observations],
        dtype=float,
    )

def test_stationary_no_current_no_thrust():

    state = np.zeros(6)

    derivative = dynamics(
        state,
        0.0,
        0.0,
        Vehicle(),
        Faults(),
    )

    assert np.allclose(derivative, 0.0)


def test_stationary_current_causes_acceleration():

    state = np.zeros(6)

    derivative = dynamics(
        state,
        0.0,
        0.0,
        Vehicle(),
        Faults(current_y=0.4),
    )

    assert derivative[4] > 0


def test_current_does_not_instantly_change_position():

    state = np.zeros(6)

    derivative = dynamics(
        state,
        0.0,
        0.0,
        Vehicle(),
        Faults(current_x=0.4),
    )

    assert derivative[0] == pytest.approx(0.0)


def test_thruster_efficiency_changes_yaw_direction():

    state = np.zeros(6)

    weak_starboard = dynamics(
        state,
        10.0,
        10.0,
        Vehicle(),
        Faults(starboard_efficiency=0.4),
    )

    weak_port = dynamics(
        state,
        10.0,
        10.0,
        Vehicle(),
        Faults(port_efficiency=0.4),
    )

    assert weak_starboard[5] < 0
    assert weak_port[5] > 0


def test_current_rotation_at_ninety_degrees():

    state = np.array(
        [0, 0, math.pi / 2, 0, 0, 0],
        dtype=float,
    )

    derivative = dynamics(
        state,
        0.0,
        0.0,
        Vehicle(),
        Faults(current_x=0.4),
    )

    expected_sway_acceleration = (
        -(35.0 * 0.4 + 15.0 * 0.4**2) / 62.0
    )

    assert derivative[4] == pytest.approx(
        expected_sway_acceleration,
        rel=1e-5,
    )


def test_body_frame_current_derivative_at_nonzero_yaw_rate():

    current_x = 0.35
    current_y = -0.22

    heading = 0.6
    yaw_rate = 0.4

    epsilon = 1e-6

    def body_current(psi):
        c = math.cos(psi)
        s = math.sin(psi)

        return np.array([
            c * current_x + s * current_y,
            -s * current_x + c * current_y,
        ])

    body_velocity = body_current(heading)

    numerical_derivative = (
        body_current(heading + yaw_rate * epsilon)
        - body_current(heading - yaw_rate * epsilon)
    ) / (2 * epsilon)

    analytical_derivative = np.array([
        yaw_rate * body_velocity[1],
        -yaw_rate * body_velocity[0],
    ])

    assert np.allclose(
        numerical_derivative,
        analytical_derivative,
        atol=1e-8,
    )


def test_coriolis_does_not_create_energy():

    vehicle = replace(
        Vehicle(),
        damping_surge=0.0,
        damping_sway=0.0,
        damping_yaw=0.0,
        quadratic_surge=0.0,
        quadratic_sway=0.0,
        quadratic_yaw=0.0,
    )

    state = np.array(
        [0.0, 0.0, 0.35, 1.2, -0.3, 0.25]
    )

    derivative = dynamics(
        state,
        0.0,
        0.0,
        vehicle,
        Faults(),
    )

    kinetic_energy_derivative = (
        vehicle.mass_surge * state[3] * derivative[3]
        + vehicle.mass_sway * state[4] * derivative[4]
        + vehicle.inertia_yaw * state[5] * derivative[5]
    )

    assert kinetic_energy_derivative == pytest.approx(
        0.0,
        abs=1e-9,
    )


def test_nominal_forward_speed_is_reasonable():

    result = simulate(mission=NOISELESS)

    final_u = result.truth[-1]["u_mps"]

    expected = (
        -13.0 + math.sqrt(13.0**2 + 4 * 4.0 * 26.0)
    ) / (2 * 4.0)

    assert final_u == pytest.approx(
        expected,
        abs=0.08,
    )


def test_timestep_convergence():

    faults = Faults(current_y=0.3)

    coarse = simulate(
        faults=faults,
        mission=replace(FAST, dt_s=0.05),
    )

    fine = simulate(
        faults=faults,
        mission=replace(FAST, dt_s=0.025),
    )

    coarse_xy = np.column_stack([
        truth_column(coarse, "x_m"),
        truth_column(coarse, "y_m"),
    ])

    fine_xy = np.column_stack([
        truth_column(fine, "x_m"),
        truth_column(fine, "y_m"),
    ])

    assert np.allclose(
        coarse_xy,
        fine_xy[::2],
        atol=0.05,
        rtol=0.0,
    )

def test_simulation_result_has_separate_structures():
    result = simulate(mission=FAST)

    assert isinstance(result, SimulationResult)

    assert isinstance(result.truth, list)
    assert isinstance(result.observations, list)

    assert len(result.truth) > 0

    assert len(result.truth) == len(result.observations)

    assert result.truth is not result.observations


def test_exact_observable_column_set():

    result = simulate(
        faults=Faults(
            current_y=0.4,
            starboard_efficiency=0.6,
        ),
        mission=FAST,
        plant=HIDDEN_PLANT,
    )

    expected = set(OBSERVATION_FIELDS)

    for row in result.observations:
        assert set(row.keys()) == expected

    forbidden = {
        "x_m",
        "y_m",
        "heading_rad",
        "u_mps",
        "v_mps",
        "yaw_rate_radps",
        "desired_heading_rad",
        "port_actual_n",
        "starboard_actual_n",
        "current_x_mps",
        "current_y_mps",
        "port_efficiency",
        "starboard_efficiency",
        "heading_bias_rad",
        "faults",
        "plant",
    }

    assert forbidden.isdisjoint(expected)


def test_truth_contains_required_physical_fields():
    result = simulate(mission=FAST)

    required = {
        "x_m",
        "y_m",
        "heading_rad",
        "u_mps",
        "v_mps",
        "yaw_rate_radps",
        "port_actual_n",
        "starboard_actual_n",
    }

    assert required.issubset(result.truth[0].keys())


def test_observations_include_noisy_gyro():

    mission = replace(
        FAST,
        sensor_yaw_rate_std_radps=0.02,
    )

    result = simulate(mission=mission)

    observed = observed_column(
        result,
        "observed_yaw_rate_radps",
    )

    actual = truth_column(
        result,
        "yaw_rate_radps",
    )

    assert not np.array_equal(observed, actual)


def test_controller_uses_observed_yaw_rate():

    zero_rate = command(
        observed_y=0.3,
        observed_heading=0.1,
        observed_yaw_rate=0.0,
        vehicle=Vehicle(),
        controller=Controller(),
    )

    nonzero_rate = command(
        observed_y=0.3,
        observed_heading=0.1,
        observed_yaw_rate=0.2,
        vehicle=Vehicle(),
        controller=Controller(),
    )

    assert zero_rate[0] != nonzero_rate[0]
    assert zero_rate[1] != nonzero_rate[1]


def test_truth_and_observations_share_timestamps():
    result = simulate(mission=FAST)

    truth_times = truth_column(
        result,
        "time_s",
    )

    observed_times = observed_column(
        result,
        "time_s",
    )

    assert np.array_equal(
        truth_times,
        observed_times,
    )

    assert np.all(np.diff(truth_times) > 0)

def test_actuator_lag_slows_force_response():

    actual = np.zeros(2)

    commanded = np.array([10.0, 10.0])

    ideal = actuator_step(
        actual,
        commanded,
        0.05,
        PlantConfig(),
    )

    lagged = actuator_step(
        actual,
        commanded,
        0.05,
        PlantConfig(actuator_tau_s=0.15),
    )

    assert np.allclose(ideal, commanded)

    assert np.all(lagged < ideal)

    assert np.all(lagged > 0)


def test_actuator_deadzone_reduces_force():
    actual = np.zeros(2)

    output = actuator_step(
        actual,
        np.array([10.0, -10.0]),
        0.05,
        PlantConfig(
            thrust_deadzone_n=0.5,
        ),
    )

    assert output[0] == pytest.approx(9.5)
    assert output[1] == pytest.approx(-9.5)


def test_actuator_deadzone_suppresses_small_commands():
    output = actuator_step(
        np.zeros(2),
        np.array([0.2, -0.2]),
        0.05,
        PlantConfig(thrust_deadzone_n=0.5),
    )

    assert np.allclose(output, 0.0)


def test_hidden_plant_changes_trajectory():

    ideal = simulate(
        mission=FAST,
        plant=PlantConfig(),
    )

    hidden = simulate(
        mission=FAST,
        plant=HIDDEN_PLANT,
    )

    ideal_x = truth_column(ideal, "x_m")
    hidden_x = truth_column(hidden, "x_m")

    assert not np.allclose(
        ideal_x,
        hidden_x,
    )


def test_hidden_plant_does_not_leak_its_parameters():
    result = simulate(
        mission=FAST,
        plant=HIDDEN_PLANT,
    )

    for row in result.observations:
        assert "actuator_tau_s" not in row
        assert "thrust_deadzone_n" not in row
        assert "drag_scale" not in row

def test_experiment_changes_commands():

    low = simulate(
        mission=FAST,
        experiment=Experiment(cruise_thrust_n=10.0),
    )

    high = simulate(
        mission=FAST,
        experiment=Experiment(cruise_thrust_n=20.0),
    )

    low_commands = observed_column(
        low,
        "port_command_n",
    )

    high_commands = observed_column(
        high,
        "port_command_n",
    )

    assert not np.allclose(
        low_commands,
        high_commands,
    )


def test_experiment_changes_physical_trajectory():

    fault = Faults(current_y=0.3)

    low = simulate(
        faults=fault,
        mission=FAST,
        experiment=Experiment(cruise_thrust_n=10.0),
    )

    high = simulate(
        faults=fault,
        mission=FAST,
        experiment=Experiment(cruise_thrust_n=20.0),
    )

    assert not np.allclose(
        truth_column(low, "x_m"),
        truth_column(high, "x_m"),
    )


def test_experiment_duration_override():
    result = simulate(
        mission=FAST,
        experiment=Experiment(duration_s=8.0),
    )

    assert result.truth[-1]["time_s"] == pytest.approx(
        8.0,
        abs=1e-8,
    )


def test_unsupported_maneuver_is_rejected():
    with pytest.raises(ValueError):
        simulate(
            mission=FAST,
            experiment=Experiment(
                maneuver="reciprocal_heading",
            ),
        )


def test_experiment_rejects_invalid_cruise_thrust():
    with pytest.raises(ValueError):
        simulate(
            mission=FAST,
            experiment=Experiment(
                cruise_thrust_n=1000.0,
            ),
        )

def test_nominal_reaches_cable_endpoint():
    result = simulate()

    report = metrics(
        result,
        Mission(),
        Vehicle(),
    )

    assert report["reached_cable_end"]
    assert report["mission_success"]

    assert result.truth[-1]["x_m"] == pytest.approx(
        110.0,
        abs=0.15,
    )


def test_nominal_stops_around_expected_time():

    result = simulate()

    elapsed = result.truth[-1]["time_s"]

    assert 75.0 < elapsed < 90.0


def test_no_samples_after_endpoint():
    result = simulate()

    x = truth_column(result, "x_m")

    assert x[-1] <= Mission().cable_length_m + 1e-6

    assert np.all(
        x[:-1] < Mission().cable_length_m
    )


def test_mission_timeout():
    mission = replace(
        FAST,
        duration_s=5.0,
    )

    result = simulate(mission=mission)

    report = metrics(
        result,
        mission,
        Vehicle(),
    )

    assert not report["reached_cable_end"]
    assert not report["mission_success"]

    assert report["elapsed_s"] == pytest.approx(
        5.0,
        abs=1e-8,
    )


def test_metrics_use_custom_vehicle_limits():

    vehicle = replace(
        Vehicle(),
        max_thrust=8.0,
    )

    controller = replace(
        Controller(),
        cruise_thrust=8.0,
    )

    result = simulate(
        vehicle=vehicle,
        controller=controller,
        mission=FAST,
    )

    report = metrics(
        result,
        FAST,
        vehicle,
    )

    assert (
        report["command_saturation_fraction"]
        > 0.0
    )


def test_mission_failure_for_cross_current():
    faults = Faults(current_y=0.48)

    result = simulate(faults=faults)

    report = metrics(
        result,
        Mission(),
        Vehicle(),
    )

    assert not report["mission_success"]

    assert (
        report["max_abs_cross_track_m"]
        > Mission().cable_half_width_m
    )


def test_mission_failure_for_weak_starboard():
    faults = Faults(
        starboard_efficiency=0.42,
    )

    result = simulate(faults=faults)

    report = metrics(
        result,
        Mission(),
        Vehicle(),
    )

    assert not report["mission_success"]


def test_mission_failure_for_compound_fault():
    faults = Faults(
        current_y=0.35,
        starboard_efficiency=0.65,
    )

    result = simulate(faults=faults)

    report = metrics(
        result,
        Mission(),
        Vehicle(),
    )

    assert not report["mission_success"]

def test_heading_bias_changes_observed_heading():

    bias = 0.2

    result = simulate(
        faults=Faults(
            heading_bias_rad=bias,
        ),
        mission=FAST,
    )

    true_heading = result.truth[0]["heading_rad"]

    observed_heading = result.observations[0][
        "observed_heading_rad"
    ]

    assert wrap_angle(
        observed_heading - true_heading
    ) == pytest.approx(bias)


def test_heading_bias_changes_vehicle_behavior():
    nominal = simulate(
        mission=FAST,
    )

    biased = simulate(
        mission=FAST,
        faults=Faults(
            heading_bias_rad=0.2,
        ),
    )

    assert not np.allclose(
        truth_column(nominal, "y_m"),
        truth_column(biased, "y_m"),
    )


def test_port_efficiency_fault_is_active():
    nominal = simulate(mission=FAST)

    weak_port = simulate(
        mission=FAST,
        faults=Faults(
            port_efficiency=0.5,
        ),
    )

    assert not np.allclose(
        truth_column(nominal, "heading_rad"),
        truth_column(weak_port, "heading_rad"),
    )


def test_same_seed_reproduces_results():
    a = simulate(mission=FAST)
    b = simulate(mission=FAST)

    assert a.truth == b.truth

    assert a.observations == b.observations


def test_different_seed_changes_sensor_noise():
    mission = replace(
        FAST,
        sensor_y_std_m=0.03,
    )

    a = simulate(mission=mission)

    b = simulate(
        mission=replace(
            mission,
            seed=123,
        ),
    )

    assert (
        a.observations[0]["observed_y_m"]
        != b.observations[0]["observed_y_m"]
    )

def test_reject_invalid_thruster_efficiency():
    with pytest.raises(ValueError):
        simulate(
            mission=FAST,
            faults=Faults(
                port_efficiency=1.2,
            ),
        )


def test_reject_invalid_noise():
    with pytest.raises(ValueError):
        simulate(
            mission=replace(
                FAST,
                sensor_yaw_rate_std_radps=-0.01,
            ),
        )


def test_reject_invalid_plant_parameters():
    with pytest.raises(ValueError):
        simulate(
            mission=FAST,
            plant=PlantConfig(
                actuator_tau_s=-0.2,
            ),
        )


def test_reject_excessive_current():
    with pytest.raises(ValueError):
        simulate(
            mission=FAST,
            faults=Faults(
                current_y=4.0,
            ),
        )

def test_public_csv_has_exact_observation_columns(tmp_path):
    result = simulate(
        mission=FAST,
        plant=HIDDEN_PLANT,
        faults=Faults(
            current_y=0.4,
            starboard_efficiency=0.6,
        ),
    )

    save_run(
        result,
        tmp_path,
        Faults(
            current_y=0.4,
            starboard_efficiency=0.6,
        ),
        FAST,
        Controller(),
        Vehicle(),
        plant=HIDDEN_PLANT,
    )

    public_csv = tmp_path / "observed_telemetry.csv"

    assert public_csv.exists()

    with public_csv.open(newline="") as handle:
        reader = csv.DictReader(handle)

        assert set(reader.fieldnames) == set(
            OBSERVATION_FIELDS
        )

        rows = list(reader)

    assert len(rows) == len(result.observations)


def test_private_and_public_exports_are_distinct(tmp_path):
    result = simulate(
        mission=FAST,
        plant=HIDDEN_PLANT,
    )

    save_run(
        result,
        tmp_path,
        Faults(),
        FAST,
        Controller(),
        Vehicle(),
        plant=HIDDEN_PLANT,
    )

    assert (tmp_path / "telemetry.csv").exists()
    assert (tmp_path / "observed_telemetry.csv").exists()
    assert (tmp_path / "run.json").exists()

    with (
        tmp_path / "telemetry.csv"
    ).open(newline="") as handle:

        private_columns = set(
            csv.DictReader(handle).fieldnames
        )

    with (
        tmp_path / "observed_telemetry.csv"
    ).open(newline="") as handle:

        public_columns = set(
            csv.DictReader(handle).fieldnames
        )

    assert "x_m" in private_columns
    assert "x_m" not in public_columns

    assert "port_actual_n" in private_columns
    assert "port_actual_n" not in public_columns


def test_private_metadata_contains_plant_configuration(tmp_path):
    result = simulate(
        mission=FAST,
        plant=HIDDEN_PLANT,
    )

    save_run(
        result,
        tmp_path,
        Faults(),
        FAST,
        Controller(),
        Vehicle(),
        plant=HIDDEN_PLANT,
    )

    metadata = json.loads(
        (tmp_path / "run.json").read_text()
    )

    assert metadata["plant"]["actuator_tau_s"] == (
        HIDDEN_PLANT.actuator_tau_s
    )

    assert metadata["plant"]["drag_scale"] == (
        HIDDEN_PLANT.drag_scale
    )


def test_metrics_are_consistent_with_saved_run(tmp_path):
    result = simulate(mission=FAST)

    metadata = save_run(
        result,
        tmp_path,
        Faults(),
        FAST,
        Controller(),
        Vehicle(),
    )

    expected = metrics(
        result,
        FAST,
        Vehicle(),
    )

    assert metadata["metrics"] == expected
