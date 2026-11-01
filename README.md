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
  The Muse adapter is experimental; live end-to-end continuation and repair verification are not established.

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
The static dashboard has no live backend or Muse connection; the Python adapter runs separately.

A manual Pages workflow is prepared with publication disabled by default. Neither
a hosted site nor a public demonstration dataset is enabled by this milestone.
See [the completed-investigation replay contract](PRE_MUSE_INTERFACE_CONTRACT.md)
for existing interfaces and the metadata still needed before Muse integration.

## Controller context

Trusted hosts can attach approved classical-controller source and declared settings
using `nautilus.controller_context`; hidden backend settings remain separate.
`nautilus.configuration_evaluation` compares bounded configurations in matched
development simulations. Results are not verified repairs. See
[the controller report](CONTROLLER_AWARE_REPORT.md) for contracts and measured limits.

## Meta Muse development adapter

The bounded Responses adapter and linked provenance importer are implemented;
see [the Phase B report](MUSE_PHASE_B_REPORT.md). Live text/function smoke tests
succeeded previously, but the first complete investigation stopped on an incomplete
model response before any laboratory action. Live end-to-end continuation is still
unverified. This is a development integration, not an accuracy or repair claim.

Offline validation uses `python -m pytest -q` and the existing frontend commands.
An explicitly authorized live development run can use:

```bash
python run_muse.py --authorize-api --scenario /private/development-settings.json \
  --output /private/new-muse-run
```

The trusted settings file must remain outside the checkout and contain exactly
`purpose` (`development-only`), `faults` (approved `Faults` constructor fields),
and an integer `seed`. Never provide this file to the model or public exporter.
`MODEL_API_KEY` must already be configured as a network secret scoped to
`api.meta.ai`; do not put its value in files. `NAUTILUS_MUSE_MODEL` is a nonsecret
model override. `--max-output-tokens` defaults to 2048 including reasoning; the
first full run exhausted that allowance. Review cost before increasing it. The
runner never retries API requests or enables configuration evaluation.

Open `public-investigation.json` (or the runner's public `investigation.json`) in
the existing dashboard, then **Open Muse provenance** with its matching sidecar.
The investigation report includes validated model provenance. Keep generated
records outside the repository and out of `public/` and `dist/`; publication is
not part of this workflow.
