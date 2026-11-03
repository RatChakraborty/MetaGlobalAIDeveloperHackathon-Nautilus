# Nautilus

An evidence-first engineering workspace for simulated marine-robot failure investigation
and controller evaluation. Nautilus separates what was recorded, what is computed now, and
what a model merely proposed. All robot experiments are simulated.

The interface keeps the MATLAB/WolframAlpha visual language: dense measurements, monospaced
identifiers, restrained colour and explicit numerical evidence.

## Three cases, three different claims

| Case | Mode | What it shows |
|---|---|---|
| **A — ambiguous drift** | Live deterministic computation | Five explanations fit; the passive protocol returns `kind=ambiguous`, `selected=null`. This is passive ambiguity, not an agent or Muse abstention. |
| **B — bounded integral compensation** | Live deterministic computation | Baseline plus bounded integral action passes 8/8 predeclared gates; mean RMS 0.994 → 0.410 m; held-out mean improves 0.493 m. Host-proposed example, not Muse. |
| **C — rejected 14 m lookahead** | Recorded demonstration | Predeclared candidate is worse on all three development scenarios (5.02 m vs 2.68 m RMS on the first). Not Muse-selected; inputs private. |

The three cards appear on **Overview**, each with provenance, result IDs, limitations and a
**Show evidence** link to the retained JSON. The execution-mode legend defines recorded,
live deterministic, live Meta Muse and mock sessions at the top of the app.

**Keep the studies separate.** Case C's 3 m lookahead alternative is a different candidate in
that recorded study. It is not the Case B bounded-integral policy, and its numbers must not be
merged with Case B's.

## What the workspace does

- Simulates a planar AUV with lateral current, independent thruster efficiency and heading bias.
  Public telemetry omits longitudinal position and speed and never includes hidden plant truth.
- Fits declared physical explanations with the deterministic `observer-v1` passive protocol.
  Scores are heuristic; a frozen score gap decides ambiguity.
- Evaluates controller policies through a bounded IR, source round-trip, matched paired trials,
  fixed acceptance gates and a separate held-out robustness split.
- Retains hash-linked investigation records and downloadable reports.
- Runs a bounded, server-side Muse adapter in development. It is off by default; the controller
  Studio's live provider is not available.

Six destinations mirror the workflow: **Overview** (start and cases), **Workspace**
(Simulation Lab, Investigator, Trajectory), **Dashboards**, **Policy Studio**, **Experiments**
and **Reports**.

## Install and run

Requires Python 3.10+ and Node 22.12+. Python 3.12.3 and Node 26.13.0 were used for the
verified run below.

```bash
# Python core and tests
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'

# API (terminal 1)
.venv/bin/python -m nautilus_api.server 8000

# Frontend (terminal 2)
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:3000/`. Vite proxies `/api` to `127.0.0.1:8000`. The API exposes no
health route; smoke-test with `POST /api/v1/simulations`.

Offline CLI example:

```bash
.venv/bin/python run_day1.py   # writes simulation results and a plot to outputs/
```

## Execution modes

| Badge | Meaning |
|---|---|
| Recorded demonstration | Stored trace or artifact; not computed now. |
| Live deterministic computation | Trusted simulator runs now; identical inputs and seed reproduce the numbers. Free. |
| Live Meta Muse | Paid model call, server-side, disabled by default. Not used by any demo case. |
| Mock development session | Scripted data for tests; never scientific evidence. |

Case A and Case B call the free API. Case C is a retained artifact. No case is a physical robot
run or a live Muse run.

## Verification status

| Check | Result |
|---|---|
| Python tests | 662 passed, 4 subtests passed |
| Frontend tests | 142 passed |
| TypeScript / production build | clean / succeeded |
| Case B determinism | identical fingerprint and rows on repeat |
| Targeted mock-Muse tests | 5 passed |
| Evidence SHA-256 checks | all shipped files match |
| Secret scan | no tracked keys or server-only names in the bundle |
| Browser click-through | **not run here** — no browser binary; needs a human pass |

Run the suites:

```bash
env -u MODEL_API_KEY -u OPENAI_API_KEY -u UPSTASH_REDIS_REST_URL -u UPSTASH_REDIS_REST_TOKEN \
  .venv/bin/python -m pytest -q -p no:cacheprovider
cd frontend && npm test && npm run build
```

Details, exact numbers, limitations and the Muse readiness contracts are in
[EVALUATION.md](docs/EVALUATION.md). The judge script is in
[DEMO_RUNBOOK.md](docs/DEMO_RUNBOOK.md).

## 3D trajectory viewer

The 3D panel replays only imported recorded visualization companions. Live simulation telemetry
has no longitudinal position, so computed runs stay numerical in the Simulation Lab and
Dashboards. The viewer states this distinction on screen; no trajectory is invented.

## Meta Muse

The investigative adapter and linked provenance importer exist; historical development runs
are documented in [MUSE_PHASE_B_REPORT.md](MUSE_PHASE_B_REPORT.md). The controller-engineering
loop has a deterministic mock and a live provider that remains unavailable
(`live_available()` is `False`; verified per-token prices are required before any request).

- `NAUTILUS_MUSE_ENABLED` is a server-side kill switch; only the exact value `true` opens the guard.
- `MODEL_API_KEY` is read server-side only and must never be exposed to the browser.
- Paid routes also require `NAUTILUS_DEMO_TOKEN`, daily/monthly caps and an allowed origin.
- Recorded Muse provenance is never labelled live, and mock sessions are never evidence.
- **No paid Muse calls were made for the final demo and documentation pass.**

See [the architecture](docs/ARCHITECTURE.md#muse-integration-status) and the
[cost envelope](docs/muse-cost-envelope.md).

## Historical control studies

The controller-context and V6 laboratories remain available for reproducibility:

- [CONTROLLER_AWARE_REPORT.md](CONTROLLER_AWARE_REPORT.md) — matched controller-context study,
  including the predeclared 7 m / 3 m / 14 m lookahead comparison used by Case C.
- [V6_CONTROL_LAB_REPORT.md](V6_CONTROL_LAB_REPORT.md) — versioned control-policy contract,
  matched evaluation, seven-case development suite and bounded search.
- [Policy Studio](docs/ARCHITECTURE.md#controller-engineering) — the current bounded-integral
  workflow used by Case B.

These are development measurements, not benchmarks, repairs or safety certificates. The
controller patch path is static review only and never executes a model-written patch.

## Limits and safety

- Simulation only; no hardware interface, deployment or field validation.
- Passive scores are heuristic and not calibrated probabilities.
- Hidden plant truth is not exposed to the lab; the Case A evidence file records a post-hoc
  truth check only after classification.
- Case C cannot be regenerated from the public tree; its retained scenario inputs are private.
- Ledger integrity proves recorded bytes, not physical correctness or authorship.
- The frontend has no durable storage; session state is in memory.
- External model behaviour is bounded by schemas and host validation, but diagnostic accuracy
  and repair verification are not established.

## Documentation

- [Architecture and trust boundaries](docs/ARCHITECTURE.md)
- [Evaluation, commands and release readiness](docs/EVALUATION.md)
- [Three-minute demo runbook](docs/DEMO_RUNBOOK.md)
- [Muse laboratory contract](MUSE_LABORATORY_CONTRACT.md)
- [Diagnosis method and numerical assumptions](DIAGNOSIS_METHOD.md)
- [Pre-Muse interface contract](PRE_MUSE_INTERFACE_CONTRACT.md)

## Security

Never commit `.env` files, `MODEL_API_KEY`, `NAUTILUS_DEMO_TOKEN`, Upstash credentials or
provider pricing. Use the names in [`.env.example`](.env.example) and keep values in the
environment or the deployment secret store. Live Muse spend must be separately authorized.
