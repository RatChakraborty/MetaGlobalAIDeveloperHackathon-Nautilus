# Nautilus

Nautilus is an offline simulation laboratory for investigating marine robot failures.
It combines a simplified planar AUV simulator, bounded hypothesis fitting, diagnostic
experiments, and an auditable interface for interchangeable investigators.

## Install and run

Requires Python 3.10 or newer.

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
python run_day1.py
```

`run_day1.py` writes simulation results and a comparison plot to `outputs/`.

## Capabilities and limitations

- Fits requested physical hypotheses using public lateral position, heading,
  yaw rate and command telemetry. Longitudinal position and speed are unobserved.
- Provides residuals, convergence and local sensitivity diagnostics. Low residuals
  and heuristic score gaps do not establish physical correctness or probabilities.
- Executes bounded experiments in default `simulation_advisory` mode: trajectory
  risks are warnings. Optional `simulation_enforced` retains screening and guards.
  Advisory mode is for offline research, not robotic hardware deployment.
- Separates laboratory tools, deterministic investigators and private evaluation.
  Muse integration and repair verification are not implemented.

See [the tool contract](MUSE_LABORATORY_CONTRACT.md),
[numerical assumptions](DIAGNOSIS_METHOD.md), and
[the V2 protocol](ACTIVE_PROTOCOL_V2.md). The [V3 protocol](DRAFT_RELIABILITY_PROTOCOL_V3.md)
is a draft; no V3 held-out evaluation has been generated. Historical frozen runs
require their preserved source snapshots and runtime, not the cleaned current files.
Generated observations, oracle outputs and private reports belong outside the repository.

## Dashboard

The static frontend in `frontend/` provides Investigator, Analytics and Trajectory
tabs for read-only inspection of recorded evidence and planar simulation replay.
Run `npm ci && npm run dev` inside that directory; see its README for export/build
commands. Public observations and separately loaded simulation-truth visualization
remain distinct. Missing fits or conclusions stay unavailable. Demonstration
autoloading is prepared but disabled; sample-data publication requires approval.
No live backend or Muse connection is included.

A manual Pages workflow is prepared with publication disabled by default. Neither
a hosted site nor a public demonstration dataset is enabled by this milestone.
See [the completed-investigation replay contract](PRE_MUSE_INTERFACE_CONTRACT.md)
for existing interfaces and the metadata still needed before Muse integration.
