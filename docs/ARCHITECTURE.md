# Nautilus architecture

Status: current for `main` at `82723c9` (docs refreshed at `19765e2`). Every robot result in this repository comes
from a simulator; no hardware execution is included.

## Purpose

Nautilus is an offline engineering workspace for marine-robot failure investigation and
controller evaluation. It answers three bounded questions:

1. Which declared fault explanations are consistent with public telemetry, and when is the
   evidence too ambiguous to choose one?
2. Does a candidate controller change improve measured cross-track performance under matched
   simulation conditions?
3. What exactly supports each claim, and can a reviewer reproduce it from retained artifacts?

It does not establish physical causes, certify safety, or repair real vehicles.

## Layers and trust boundaries

```
browser (Vite/TypeScript)
  six destinations · session store · evidence viewer · 3D recorded replay
        |
        |  JSON over HTTP; public fields only
        v
API (stdlib server locally / Vercel Python functions)
  /api/v1/simulations · /api/v1/investigations · /api/v1/studio · /api/v1/muse-investigations
        |
        v
trusted Python core
  simulator · passive protocol · controller context · configuration evaluation
  policy IR/runtime · paired trials · V6 policy lab · investigation ledger
        |
        +--> optional Meta Muse adapter (server-side only; disabled by default)
```

Trusted code owns every number. The browser may choose declared scenario knobs and controller
parameters, but it never receives hidden plant truth, private evaluation fixtures or provider
credentials. A model, when enabled, can only propose tool calls; the host validates the call,
runs the trusted tool and records the result.

## Simulation and public telemetry

`nautilus/simulator.py` implements a simplified planar AUV with lateral current, independent
port/starboard efficiency and heading bias. Observations contain time, measured lateral
position, heading, yaw rate and commanded thrust. Longitudinal position and speed are not
observed. Public API rows omit hidden truth columns (`y_true` and similar).

The passive protocol (`nautilus/protocol.py`) fits the declared hypotheses and returns one of:
`single_cause`, `ambiguous`, `no_fit` (implementation-specific labels are exposed as returned).
Scores are heuristic, not probabilities. The ambiguity decision uses a frozen score gap.
Diagnostic experiments and the active investigator exist in the core, but the default API
simulation route uses the passive protocol.

## Investigation records and evidence

An investigation export contains public observations, a hash-linked ledger and an optional
recorded conclusion. `nautilus_api/ledger.py` provides the optional shared budget/ledger store
when Upstash is configured. The frontend validates record shape and ledger linkage on load;
integrity proves byte consistency, not physical correctness or authorship.

Exports and visualization companions are loaded explicitly by the user. Missing fits or
conclusions remain "unavailable" rather than being synthesized.

## Controller engineering

- `nautilus/policy_ir.py` defines the bounded controller IR and parameter limits.
- `nautilus/policy_source.py` converts between IR and reviewed source text under structural
  limits; source is not executed as arbitrary Python.
- `nautilus/policy_runtime.py` interprets the policy in the trusted simulator.
- `nautilus/studio.py` runs validation, matched paired trials, fixed acceptance gates and a
  held-out robustness split.
- `nautilus/configuration_evaluation.py` and `nautilus/v6/` provide the older approved
  controller-context and control-lab evaluations used by the historical studies.

The Studio's development split and its held-out split are separate. A `Recommended` result
means the candidate passed the declared gates on that split; it is not a repair, benchmark or
safety result. A candidate can be host-declared, predeclared in a study, or selected by a
bounded search; the interface and reports must say which.

## Muse integration status

Two bounded adapters exist:

- investigation adapter (`nautilus/muse*.py`), with recorded live development runs documented
  in the historical reports;
- controller-engineering loop (`nautilus/studio_muse.py`, `nautilus/studio_muse_live.py`), with
  a deterministic `MockMuse` and a live provider (`studio_muse_live.py`). The live provider is
  reachable only through the operator script `scripts/run_muse_studio_live.py`; the public web
  path does not select it.

The server-side kill switch is `NAUTILUS_MUSE_ENABLED`: only the exact value `true` enables the
guard. `live_available()` in `studio_muse` returns true only when that switch is on and
`MODEL_API_KEY` is set. The live envelope refuses every request until verified per-token prices
are configured. Mock sessions are labelled mock
and are never scientific evidence. See [the Muse readiness contracts](#muse-readiness-contracts).

## API surface

| Route | Method | Behaviour |
|---|---|---|
| `/api/v1/simulations` | POST | Free deterministic simulation; public observations + passive diagnosis. |
| `/api/v1/investigations` | POST | Queue the scripted deterministic investigation. |
| `/api/v1/investigations/{id}` | GET | Poll job state and public result. |
| `/api/v1/investigations/{id}/cancel` | POST | Request cancellation. |
| `/api/v1/studio` | POST | Free Studio actions: baseline, validate, trial, robustness. |
| `/api/v1/muse-investigations` | POST | Paid live investigation; requires `NAUTILUS_DEMO_TOKEN` and budget. |

The local stdlib server and the hosted functions share the Studio dispatch table so behaviour
does not drift. The browser's live-Muse client targets `/api/muse`; this is an operator-only
path and is not part of the free demo.

## Frontend

Six persistent destinations (`frontend/src/navigation.ts`):

1. **Overview** — verified Case Files, execution-mode legend, free example, session state.
2. **Workspace** — Simulation Lab, Investigator, recorded Trajectory replay.
3. **Dashboards** — measured channels, fit evidence, diagnosis, controller comparisons.
4. **Policy Studio** — controller source/parameters, diff, validation, paired trial, robustness.
5. **Experiments** — runs and trials from this browser session plus a loaded export.
6. **Reports** — download the record, configuration diff, comparison and engineering report.

`frontend/src/session.ts` is an in-memory session index; it is not durable storage. The report
and evidence downloads are generated from loaded or computed public data.

The 3D viewer (`frontend/src/trajectory.ts`, `replay.ts`) renders only imported recorded
visualization companions. Live simulation telemetry has no x-position, so computed runs are
shown numerically in the Simulation Lab and Dashboards and are explicitly not drawn in the
recorded replay.

## Execution modes

| Mode | Meaning |
|---|---|
| Recorded demonstration | Stored trace or artifact; not computed now. |
| Live deterministic computation | Trusted simulator runs now; same inputs/seed reproduce the numbers. |
| Live Meta Muse | Paid server-side model call; off by default; not used by the three cases. |
| Mock development session | Scripted UI/provider data for tests; never evidence. |

Case A and Case B are live deterministic computations. Case C is a recorded development study.
No demo case is a live Muse run, and no robot experiment is physical.

## Security invariants

- `MODEL_API_KEY` is read server-side only and is never sent to the browser.
- `NAUTILUS_DEMO_TOKEN` is compared in constant time; without it the paid route is disabled.
- CORS is restricted to the configured `NAUTILUS_ALLOWED_ORIGIN`.
- Request bodies are size-limited and scenario fields are allow-listed and range-checked.
- Ledger verification detects tampering; it does not establish authenticity.
- Public evidence files contain public observations, result metadata and explicitly labelled post-hoc
  evaluation notes; hidden inputs and private fixtures stay out.

## Muse readiness contracts

The final scientific-agent upgrade can build on the following existing seams. Not all of these
are complete; the requirements are listed so the upgrade does not renegotiate the trust model.

1. **Hypothesis proposals** — a strict tool schema that returns declared hypothesis names and
   parameters only, with host-side range/type validation and an append-only action record.
2. **Controller revisions** — IR/source proposals through `validate_controller`; no model code
   execution, bounded size and explicit candidate IDs.
3. **Trusted tool execution** — one dispatcher (`studio_muse.call`) that owns all simulator and
   evaluator access; unknown tools, extra fields and invalid state transitions rejected.
4. **Structured evidence memory** — public observations, fit results, trial rows and gate
   outcomes stored with stable IDs and hashes; hidden truth and private fixtures excluded.
5. **Independent numerical verification** — every quoted number re-derived by the host from the
   retained run, not accepted from model text; configuration/source fingerprints checked.
6. **Live event traces** — ordered request/action/result events with usage, latency, termination
   reason and explicit host-finalization provenance; no private chain-of-thought claim.
7. **Verified model-generated report** — report fields bound to evidence IDs and rejected when a
   referenced result is missing, stale or from a different candidate.
8. **Operational controls** — verified provider prices, per-session spend/token/request ceilings,
   daily and monthly caps, no retries that duplicate lab actions, and the default-off switch.

Remaining gaps are listed in [EVALUATION.md](EVALUATION.md#muse-upgrade-readiness).
