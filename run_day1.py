


import argparse
from pathlib import Path

import matplotlib


matplotlib.use("Agg")

import matplotlib.pyplot as plt

from nautilus import (
    Vehicle,
    Faults,
    Controller,
    Mission,
    simulate,
    save_run,
)


def main():
    parser = argparse.ArgumentParser(
        description="Run Nautilus Day 1 simulations."
    )

    parser.add_argument(
        "--output",
        default="outputs",
        help="Directory to save simulation results.",
    )

    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)


    vehicle = Vehicle()
    controller = Controller()
    mission = Mission()


    cases = {
        "nominal": Faults(),

        "cross_current": Faults(
            current_y=0.48,
        ),

        "weak_starboard": Faults(
            starboard_efficiency=0.42,
        ),

        "compound": Faults(
            current_y=0.35,
            starboard_efficiency=0.65,
        ),
    }

    trajectories = {}

    print("\nNautilus — Day 1 Simulation Results")
    print("-" * 65)


    for name, faults in cases.items():



        result = simulate(
            vehicle=vehicle,
            faults=faults,
            controller=controller,
            mission=mission,
        )


        data = save_run(
            result=result,
            path=output / name,
            faults=faults,
            mission=mission,
            control=controller,
            vehicle=vehicle,
        )



        trajectories[name] = result.truth

        report = data["metrics"]

        status = (
            "PASS"
            if report["mission_success"]
            else "FAIL"
        )

        print(
            f"{name:17s} "
            f"{status:5s} "
            f"distance={report['final_x_m']:7.2f} m  "
            f"max_error={report['max_abs_cross_track_m']:6.2f} m  "
            f"time={report['elapsed_s']:6.2f} s"
        )





    fig, axes = plt.subplots(
        2,
        1,
        figsize=(10, 8),
        constrained_layout=True,
    )


    for name, rows in trajectories.items():

        x = [row["x_m"] for row in rows]
        y = [row["y_m"] for row in rows]
        t = [row["time_s"] for row in rows]

        axes[0].plot(
            x,
            y,
            label=name,
            linewidth=2,
        )

        axes[1].plot(
            t,
            y,
            label=name,
            linewidth=2,
        )


    axes[0].axhline(
        0,
        color="black",
        linestyle="--",
        linewidth=1,
        label="Cable / desired path",
    )

    axes[0].axhspan(
        -mission.cable_half_width_m,
        mission.cable_half_width_m,
        alpha=0.06,
    )

    axes[0].set(
        xlabel="Along cable x (m)",
        ylabel="Lateral error y (m)",
        title="AUV Inspection — Simulated Trajectories",
    )


    axes[1].axhline(
        0,
        color="black",
        linestyle="--",
        linewidth=1,
    )

    axes[1].axhspan(
        -mission.cable_half_width_m,
        mission.cable_half_width_m,
        alpha=0.06,
    )

    axes[1].set(
        xlabel="Time (s)",
        ylabel="Cross-track error (m)",
        title="Tracking Error Over Time",
    )


    for axis in axes:
        axis.legend(loc="best")
        axis.grid(alpha=0.2)


    plot_path = output / "comparison.png"

    fig.savefig(
        plot_path,
        dpi=160,
    )

    plt.close(fig)

    print("-" * 65)
    print(f"Results saved to: {output.resolve()}")
    print(f"Comparison plot: {plot_path.resolve()}")


if __name__ == "__main__":
    main()
