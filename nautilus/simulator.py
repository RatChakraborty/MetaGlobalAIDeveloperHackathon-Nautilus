


from __future__ import annotations

from dataclasses import dataclass, asdict, replace
from pathlib import Path
import csv
import json
import math

import numpy as np


def wrap_angle(value: float) -> float:
    return math.atan2(math.sin(value), math.cos(value))

@dataclass(frozen=True)
class Vehicle:
    mass_surge: float = 42.0
    mass_sway: float = 62.0
    inertia_yaw: float = 12.0

    damping_surge: float = 13.0
    damping_sway: float = 35.0
    damping_yaw: float = 18.0

    quadratic_surge: float = 4.0
    quadratic_sway: float = 15.0
    quadratic_yaw: float = 5.0

    lever_arm: float = 0.32
    max_thrust: float = 45.0


@dataclass(frozen=True)
class Faults:
    current_x: float = 0.0
    current_y: float = 0.0

    port_efficiency: float = 1.0
    starboard_efficiency: float = 1.0

    heading_bias_rad: float = 0.0


@dataclass(frozen=True)
class Controller:
    cruise_thrust: float = 13.0
    heading_kp: float = 39.0
    heading_kd: float = 18.0

    lookahead_m: float = 7.0
    max_heading_rad: float = 0.72


@dataclass(frozen=True)
class Mission:
    duration_s: float = 100.0
    dt_s: float = 0.05

    cable_length_m: float = 110.0
    cable_half_width_m: float = 1.5

    sensor_heading_std_rad: float = 0.004
    sensor_y_std_m: float = 0.035
    sensor_yaw_rate_std_radps: float = 0.003

    seed: int = 42

@dataclass(frozen=True)
class PlantConfig:

    actuator_tau_s: float = 0.0
    thrust_deadzone_n: float = 0.0
    drag_scale: float = 1.0


    drag_surge_scale: float = 1.0
    drag_sway_scale: float = 1.0
    drag_yaw_scale: float = 1.0
    uniform_drag_scale: float = 1.0

HIDDEN_PLANT = PlantConfig(
    actuator_tau_s=0.15,
    thrust_deadzone_n=0.3,
    drag_scale=1.03,
)


@dataclass(frozen=True)
class Experiment:

    cruise_thrust_n: float | None = None
    duration_s: float | None = None
    maneuver: str = "cable_follow"
    phase_s: float = 3.0
    amplitude_n: float = 8.0
    differential_n: float = 2.0
    heading_step_rad: float = 0.25
    max_abs_observed_y_m: float | None = None

@dataclass
class SimulationResult:
    truth: list[dict]
    observations: list[dict]


OBSERVATION_FIELDS = (
    "time_s",
    "observed_y_m",
    "observed_heading_rad",
    "observed_yaw_rate_radps",
    "port_command_n",
    "starboard_command_n",
)

def validate(
    vehicle: Vehicle,
    faults: Faults,
    control: Controller,
    mission: Mission,
    plant: PlantConfig = PlantConfig(),
) -> None:

    if min(
        vehicle.mass_surge,
        vehicle.mass_sway,
        vehicle.inertia_yaw,
        vehicle.lever_arm,
        vehicle.max_thrust,
    ) <= 0:
        raise ValueError(
            "Masses, yaw inertia, lever arm, and "
            "maximum thrust must be positive."
        )

    if not (
        0 <= faults.port_efficiency <= 1
        and 0 <= faults.starboard_efficiency <= 1
    ):
        raise ValueError(
            "Thruster efficiencies must be in [0, 1]."
        )

    if math.hypot(
        faults.current_x,
        faults.current_y,
    ) > 3:
        raise ValueError(
            "Current speed must not exceed 3 m/s."
        )

    if not (
        0 < mission.dt_s <= 0.2
        and 0 < mission.duration_s <= 1200
    ):
        raise ValueError(
            "Invalid mission duration or integration step."
        )

    if (
        mission.cable_length_m <= 0
        or mission.cable_half_width_m <= 0
    ):
        raise ValueError(
            "Cable length and corridor width must be positive."
        )

    noise_values = (
        mission.sensor_heading_std_rad,
        mission.sensor_y_std_m,
        mission.sensor_yaw_rate_std_radps,
    )

    if min(noise_values) < 0:
        raise ValueError(
            "Sensor noise must be nonnegative."
        )

    if (
        control.lookahead_m <= 0
        or control.max_heading_rad <= 0
    ):
        raise ValueError(
            "Invalid controller geometry."
        )

    if (
        plant.actuator_tau_s < 0
        or plant.thrust_deadzone_n < 0
        or plant.drag_scale <= 0
    ):
        raise ValueError(
            "Invalid hidden-plant parameters."
        )
    values = asdict(plant)
    if not all(math.isfinite(v) for v in values.values()) or any(
        values[k] <= 0 for k in ("drag_scale", "drag_surge_scale", "drag_sway_scale",
                                 "drag_yaw_scale", "uniform_drag_scale")
    ):
        raise ValueError("Plant scales must be finite and positive")


def effective_vehicle(vehicle: Vehicle, plant: PlantConfig) -> Vehicle:

    changes = {}
    for axis in ("surge", "sway", "yaw"):
        scale = plant.uniform_drag_scale * getattr(plant, "drag_"+axis+"_scale")
        changes["damping_"+axis] = getattr(vehicle, "damping_"+axis)*plant.drag_scale*scale
        changes["quadratic_"+axis] = getattr(vehicle, "quadratic_"+axis)*scale
    return replace(vehicle, **changes)

def dynamics(
    state: np.ndarray,
    port_cmd: float,
    starboard_cmd: float,
    vehicle: Vehicle,
    faults: Faults,
) -> np.ndarray:

    x, y, psi, u, v, r = state

    c = math.cos(psi)
    s = math.sin(psi)

    vc_u = c * faults.current_x + s * faults.current_y
    vc_v = -s * faults.current_x + c * faults.current_y

    ur = u - vc_u
    vr = v - vc_v

    coriolis = np.array([
        -vehicle.mass_sway * vr * r,
        vehicle.mass_surge * ur * r,
        (vehicle.mass_sway - vehicle.mass_surge) * ur * vr,
    ])

    relative = np.array([ur, vr, r])

    dlin = np.array([
        vehicle.damping_surge,
        vehicle.damping_sway,
        vehicle.damping_yaw,
    ])

    dquad = np.array([
        vehicle.quadratic_surge,
        vehicle.quadratic_sway,
        vehicle.quadratic_yaw,
    ])

    damping = (
        dlin * relative
        + dquad * np.abs(relative) * relative
    )

    port_force = (
        faults.port_efficiency
        * float(
            np.clip(
                port_cmd,
                -vehicle.max_thrust,
                vehicle.max_thrust,
            )
        )
    )

    star_force = (
        faults.starboard_efficiency
        * float(
            np.clip(
                starboard_cmd,
                -vehicle.max_thrust,
                vehicle.max_thrust,
            )
        )
    )

    tau = np.array([
        port_force + star_force,
        0.0,
        vehicle.lever_arm * (
            star_force - port_force
        ),
    ])

    nudot_rel = (
        tau - coriolis - damping
    ) / np.array([
        vehicle.mass_surge,
        vehicle.mass_sway,
        vehicle.inertia_yaw,
    ])

    nudot = nudot_rel + np.array([
        r * vc_v,
        -r * vc_u,
        0.0,
    ])

    return np.array([
        c * u - s * v,
        s * u + c * v,
        r,
        *nudot,
    ])

def command(
    observed_y: float,
    observed_heading: float,
    observed_yaw_rate: float,
    vehicle: Vehicle,
    controller: Controller,
    target_heading: float | None = None,
) -> tuple[float, float, float]:

    wanted_heading = math.atan2(
        -observed_y,
        controller.lookahead_m,
    )
    if target_heading is not None:
        wanted_heading = target_heading

    wanted_heading = float(
        np.clip(
            wanted_heading,
            -controller.max_heading_rad,
            controller.max_heading_rad,
        )
    )

    error = wrap_angle(
        wanted_heading - observed_heading
    )

    moment = (
        controller.heading_kp * error
        - controller.heading_kd * observed_yaw_rate
    )

    port = (
        controller.cruise_thrust
        - moment / (2 * vehicle.lever_arm)
    )

    starboard = (
        controller.cruise_thrust
        + moment / (2 * vehicle.lever_arm)
    )

    return (
        float(
            np.clip(
                port,
                -vehicle.max_thrust,
                vehicle.max_thrust,
            )
        ),
        float(
            np.clip(
                starboard,
                -vehicle.max_thrust,
                vehicle.max_thrust,
            )
        ),
        wanted_heading,
    )

def actuator_step(
    actual: np.ndarray,
    commanded: np.ndarray,
    dt: float,
    plant: PlantConfig,
) -> np.ndarray:

    target = (
        np.sign(commanded)
        * np.maximum(
            np.abs(commanded)
            - plant.thrust_deadzone_n,
            0.0,
        )
    )

    if plant.actuator_tau_s == 0:
        return target.copy()

    alpha = (
        1.0
        - math.exp(
            -dt / plant.actuator_tau_s
        )
    )

    return (
        actual
        + alpha * (target - actual)
    )

def experiment_command(t, observed_y, observed_heading, observed_yaw_rate,
                       vehicle, controller, experiment):

    mode = experiment.maneuver
    if mode == "cable_follow":
        return command(observed_y, observed_heading, observed_yaw_rate, vehicle, controller)
    if mode == "heading_response":
        target = experiment.heading_step_rad if t >= experiment.phase_s else 0.
        return command(observed_y, observed_heading, observed_yaw_rate, vehicle, controller, target)
    if mode == "thrust_step":
        mean, differential = (experiment.amplitude_n if t >= experiment.phase_s else 0.), 0.
    elif mode == "coast_down":
        mean = experiment.amplitude_n if t < experiment.phase_s else 0.
        differential = experiment.differential_n if t < experiment.phase_s else 0.
    elif mode == "differential_step":
        mean = controller.cruise_thrust
        differential = experiment.differential_n if t >= experiment.phase_s else 0.
    elif mode == "amplitude_ramp":
        mean = 0.
        differential = experiment.amplitude_n*min(1., max(0., t/experiment.phase_s))
    else:
        raise ValueError("Unsupported experiment mode")
    return float(np.clip(mean-differential,-vehicle.max_thrust,vehicle.max_thrust)), float(np.clip(mean+differential,-vehicle.max_thrust,vehicle.max_thrust)), 0.


def simulate(
    vehicle: Vehicle = Vehicle(),
    faults: Faults = Faults(),
    controller: Controller = Controller(),
    mission: Mission = Mission(),
    plant: PlantConfig = PlantConfig(),
    experiment: Experiment = Experiment(),
    policy=None,
) -> SimulationResult:

    if experiment.maneuver not in ("cable_follow", "heading_response", "thrust_step",
                                    "coast_down", "differential_step", "amplitude_ramp"):
        raise ValueError(
            "Only cable_follow is implemented. "
            "Other maneuvers are not available yet."
        )
    if (not all(math.isfinite(v) for v in (experiment.phase_s, experiment.amplitude_n,
                                          experiment.differential_n, experiment.heading_step_rad))
            or experiment.phase_s <= 0 or not 0 <= experiment.amplitude_n <= vehicle.max_thrust
            or abs(experiment.differential_n) > vehicle.max_thrust
            or abs(experiment.heading_step_rad) > .72
            or (experiment.max_abs_observed_y_m is not None and
                (not math.isfinite(experiment.max_abs_observed_y_m) or experiment.max_abs_observed_y_m <= 0))):
        raise ValueError("Invalid waveform or observation-based stop limit")

    if experiment.cruise_thrust_n is not None:

        if not (
            (0 < experiment.cruise_thrust_n <= vehicle.max_thrust
             if experiment.maneuver == "cable_follow"
             else 0 <= experiment.cruise_thrust_n <= vehicle.max_thrust)
        ):
            raise ValueError(
                "Experiment cruise thrust must be "
                "within (0, max_thrust]."
            )

        controller = replace(
            controller,
            cruise_thrust=experiment.cruise_thrust_n,
        )

    if experiment.duration_s is not None:
        mission = replace(
            mission,
            duration_s=experiment.duration_s,
        )

    validate(
        vehicle,
        faults,
        controller,
        mission,
        plant,
    )

    rng = np.random.default_rng(mission.seed)

    state = np.zeros(6, dtype=float)
    actuator_state = np.zeros(2, dtype=float)
    plant_vehicle = effective_vehicle(vehicle, plant)

    truth_rows = []
    observation_rows = []

    t = 0.0
    while True:

        obs_y = float(
            state[1]
            + rng.normal(
                0,
                mission.sensor_y_std_m,
            )
        )

        obs_heading = wrap_angle(
            float(state[2])
            + faults.heading_bias_rad
            + rng.normal(
                0,
                mission.sensor_heading_std_rad,
            )
        )

        obs_yaw_rate = float(
            state[5]
            + rng.normal(
                0,
                mission.sensor_yaw_rate_std_radps,
            )
        )

        if policy is not None and experiment.maneuver == "cable_follow":
            # Structural policy path: the interpreter sees only public observations and
            # its own bounded state. Physics below is untouched.
            port, starboard, desired = policy(
                t, obs_y, obs_heading, obs_yaw_rate, vehicle, controller)
        else:
            port, starboard, desired = experiment_command(
                t,
                obs_y,
                obs_heading,
                obs_yaw_rate,
                vehicle,
                controller,
                experiment,
            )

        truth_rows.append({
            "time_s": t,

            "x_m": float(state[0]),
            "y_m": float(state[1]),
            "heading_rad": float(state[2]),

            "u_mps": float(state[3]),
            "v_mps": float(state[4]),
            "yaw_rate_radps": float(state[5]),

            "desired_heading_rad": desired,

            "port_actual_n": float(
                actuator_state[0]
                * faults.port_efficiency
            ),

            "starboard_actual_n": float(
                actuator_state[1]
                * faults.starboard_efficiency
            ),

            "current_x_mps": faults.current_x,
            "current_y_mps": faults.current_y,
        })

        observation_rows.append({
            "time_s": t,

            "observed_y_m": obs_y,
            "observed_heading_rad": obs_heading,
            "observed_yaw_rate_radps": obs_yaw_rate,

            "port_command_n": port,
            "starboard_command_n": starboard,
        })

        if (
            state[0] >= mission.cable_length_m
            or t >= mission.duration_s - 1e-10
            or (experiment.max_abs_observed_y_m is not None and abs(obs_y) > experiment.max_abs_observed_y_m)
        ):
            break


        dt = min(
            mission.dt_s,
            mission.duration_s - t,
        )

        actuator_state = actuator_step(
            actual=actuator_state,
            commanded=np.array(
                [port, starboard]
            ),
            dt=dt,
            plant=plant,
        )

        a = dynamics(
            state,
            actuator_state[0],
            actuator_state[1],
            plant_vehicle,
            faults,
        )

        b = dynamics(
            state + 0.5 * dt * a,
            actuator_state[0],
            actuator_state[1],
            plant_vehicle,
            faults,
        )

        c = dynamics(
            state + 0.5 * dt * b,
            actuator_state[0],
            actuator_state[1],
            plant_vehicle,
            faults,
        )

        d = dynamics(
            state + dt * c,
            actuator_state[0],
            actuator_state[1],
            plant_vehicle,
            faults,
        )

        next_state = (
            state
            + dt / 6.0
            * (a + 2 * b + 2 * c + d)
        )

        if not np.all(
            np.isfinite(next_state)
        ):
            raise FloatingPointError(
                f"Non-finite state at t={t}"
            )

        if (
            state[0] < mission.cable_length_m
            <= next_state[0]
        ):

            fraction = float(
                (
                    mission.cable_length_m
                    - state[0]
                )
                / (
                    next_state[0]
                    - state[0]
                )
            )

            next_state = (
                state
                + fraction
                * (next_state - state)
            )

            next_state[0] = (
                mission.cable_length_m
            )

            dt *= fraction

        state = next_state

        state[2] = wrap_angle(
            float(state[2])
        )

        t = round(
            t + dt,
            12,
        )

    return SimulationResult(
        truth=truth_rows,
        observations=observation_rows,
    )

def metrics(
    result: SimulationResult,
    mission: Mission = Mission(),
    vehicle: Vehicle = Vehicle(),
) -> dict:

    if (
        not result.truth
        or len(result.truth)
        != len(result.observations)
    ):
        raise ValueError(
            "Missing or mismatched simulation traces."
        )

    x = np.array([
        row["x_m"]
        for row in result.truth
    ])

    y = np.array([
        row["y_m"]
        for row in result.truth
    ])

    times = np.array([
        row["time_s"]
        for row in result.truth
    ])

    commands = np.array([
        [
            row["port_command_n"],
            row["starboard_command_n"],
        ]
        for row in result.observations
    ])

    crossing = np.flatnonzero(
        x >= mission.cable_length_m - 1e-9
    )

    end_idx = (
        int(crossing[0]) + 1
        if len(crossing)
        else len(x)
    )

    x = x[:end_idx]
    y = y[:end_idx]
    times = times[:end_idx]
    commands = commands[:end_idx]

    reached = bool(
        len(crossing)
    )

    max_error = float(
        np.max(np.abs(y))
    )

    return {
        "final_x_m": float(x[-1]),

        "final_y_m": float(y[-1]),

        "elapsed_s": float(
            times[-1]
        ),

        "rms_cross_track_m": float(
            np.sqrt(
                np.mean(y * y)
            )
        ),

        "max_abs_cross_track_m": max_error,

        "fraction_outside_corridor": float(
            np.mean(
                np.abs(y)
                > mission.cable_half_width_m
            )
        ),

        "reached_cable_end": reached,

        "mission_success": bool(
            reached
            and max_error
            <= mission.cable_half_width_m
        ),

        "command_saturation_fraction": float(
            np.mean(
                np.abs(commands)
                >= vehicle.max_thrust - 1e-6
            )
        ),
    }

def save_run(
    result: SimulationResult,
    path: Path,
    faults: Faults,
    mission: Mission,
    control: Controller,
    vehicle: Vehicle,
    plant: PlantConfig = PlantConfig(),
    experiment: Experiment = Experiment(),
) -> dict:


    path = Path(path)

    path.mkdir(
        parents=True,
        exist_ok=True,
    )

    def write_csv(
        filename: str,
        rows: list[dict],
    ) -> None:

        with (
            path / filename
        ).open(
            "w",
            newline="",
        ) as handle:

            writer = csv.DictWriter(
                handle,
                fieldnames=list(
                    rows[0].keys()
                ),
            )

            writer.writeheader()
            writer.writerows(rows)

    write_csv(
        "telemetry.csv",
        result.truth,
    )

    write_csv(
        "observed_telemetry.csv",
        result.observations,
    )


    effective_mission = (
        replace(
            mission,
            duration_s=experiment.duration_s,
        )
        if experiment.duration_s is not None
        else mission
    )

    meta = {
        "vehicle": asdict(vehicle),
        "faults": asdict(faults),
        "controller": asdict(control),
        "mission": asdict(effective_mission),

        "plant": asdict(plant),
        "experiment": asdict(experiment),

        "metrics": metrics(
            result,
            effective_mission,
            vehicle,
        ),
    }


    (
        path / "run.json"
    ).write_text(
        json.dumps(
            meta,
            indent=2,
        )
    )

    return meta

