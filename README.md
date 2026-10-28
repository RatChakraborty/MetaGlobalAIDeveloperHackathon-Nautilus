# Nautilius · Day 1 scientific foundation

Nautilius is intended to be a domain-extensible forensic investigator for robot failures. **This repository is only milestone 1: the marine simulation.** No Meta agent, fault inference, or verified repair is implemented yet.

## Run

Requires Python 3.10+.

```bash
python -m pip install -e '.[dev]'
python run_day1.py --output outputs
python -m pytest -q
```

Output: `outputs/comparison.png`, and one `outputs/<case>/telemetry.csv` plus `observed_telemetry.csv` and `run.json` for each of nominal, cross-current, weak-starboard, and compound faults.

## Model and scientific limitations

- Fixed-depth planar 3-DOF toy marine vehicle; **not** a calibrated digital twin and **not** a realistic cable-repair robot.
- Effective diagonal inertia, approximate skew-symmetric Coriolis, linear+quadratic water-relative damping, differential thrusters, spatially uniform constant current, simple heading/cross-track feedback.
- Cross-current is represented through relative hydrodynamic flow; earth-frame kinematics use absolute body velocity. This prevents incorrectly adding current speed directly to position *and* applying hydrodynamic current forces.
- No vertical motion, tether, sonar imaging, pressure effects, flexible cable physics, collision detection, or ocean turbulence. Coefficients are illustrative, not empirical.
- `telemetry.csv` and `run.json` are **developer/evaluator artifacts** and reveal actuator truth or fault parameters. A separate `observed_telemetry.csv` excludes these explicit truth columns; use only the latter as the starting observation interface for future agents. Note that this file still includes idealized onboard position/velocity channels; sensor realism comes later.
- **Day 1 does not establish confounding or identifiability.** Cross-current and weak-thruster experiments are separate sanity checks. Next milestone must construct truly ambiguous telemetry and use new hidden-system observations to resolve it.

## Physics reference

Model form and water-relative flow handling are adapted conceptually from Thor I. Fossen's marine craft formulation:
https://www.fossen.biz/html/marineCraftModel.html

The equations and implementation here are newly written simplified code; no external simulator code copied. The precise diagonal coefficients are chosen for an illustrative stable experiment, not identified from field observations.

## What to inspect first

1. `nautilius/simulator.py` — `dynamics()` and `command()`.
2. `run_day1.py` — fault scenarios and output plot.
3. `tests/test_simulator.py` — simple invariants, repeatability and sign conventions.
4. `outputs/comparison.png` — inspect actual traces and whether faults matter.

## Next phase, NOT built

Separate diagnostic twin and hidden plant; construct confounded faults; Meta Muse agent experiment loop; validated parameter repairs and independent verification; benchmark vs greedy / log-only baselines.

## Day 1 mission criteria

Reach 110 m along the straight cable within 100 s while never leaving a ±1.5 m lateral corridor. This is an illustrative engineering test chosen so nominal succeeds and three injected-fault scenarios fail; it is **not** an externally validated requirement.
