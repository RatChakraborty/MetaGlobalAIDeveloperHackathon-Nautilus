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
  The Muse adapter remains experimental; diagnostic accuracy and repair verification are not established.

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
succeeded previously, but both controlled investigation attempts stopped on incomplete
model responses before any laboratory action. The isolated read-only
`get_fit_report` diagnostic now verifies real dispatch and continuation. Full
four-tool low-effort investigation has since executed a real experiment and four
fits with accepted continuations, ending in a valid input-budget host abstention.
A voluntary model diagnosis, accuracy and repairs are not established.

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
model override. The full-investigation runner selects documented low reasoning
effort by default (`--reasoning-effort low`); its live acceptance is now verified.
`--max-output-tokens` defaults to 4096 including reasoning; the
first full run exhausted its former 2048-token allowance, and the recovery exhausted
4096. The low-effort run stopped at the measured-input threshold instead; review
cost and context growth before authorizing another run. The
runner never retries API requests or enables configuration evaluation.

Open `public-investigation.json` (or the runner's public `investigation.json`) in
the existing dashboard, then **Open Muse provenance** with its matching sidecar.
The investigation report includes validated model provenance. Keep generated
records outside the repository and out of `public/` and `dist/`; publication is
not part of this workflow.

The separate development-only `run_muse_diagnostic.py --authorize-api --output
/private/new-dispatch-run` command permits at most two requests, 4,096 output
tokens each, one real `get_fit_report` action and zero experiments/retries. Do not
run it without separate API authorization. The optional `--reasoning-effort low`
(and nonsecret `NAUTILUS_MUSE_REASONING_EFFORT` provider setting) uses the
Meta syntax subsequently confirmed by the user from official documentation.
The successful live diagnostic omitted this override; a new live test still
requires explicit authorization. It is not a scientific investigation or accuracy benchmark.
