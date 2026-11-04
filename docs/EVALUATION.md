# Evaluation and release readiness

Status: pre-Muse feature freeze. This document records only checks that were actually run.
See [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md) for the judge-facing script.

## What is verified

| Area | Result | Evidence |
|---|---|---|
| Python test suite | 676 passed, 4 subtests passed (at 82723c9) | full `pytest` run, no cache provider |
| Frontend tests | 142 passed | `node --experimental-strip-types --test tests/*.test.ts` |
| TypeScript | `tsc --noEmit` clean | `npm run build` also succeeded |
| Production build | Vite build succeeded | `frontend/dist`, main bundle 186.35 kB (57.02 kB gzip) |
| Case A | live deterministic `kind=ambiguous`, `selected=null` | `frontend/public/evidence/case-a-passive-fits.json` |
| Case B | 8/8 gates, mean RMS 0.994 → 0.410 m | `frontend/public/evidence/case-b-studio-trial.json` |
| Case C | recorded 14 m candidate worse than 7 m baseline | `frontend/public/evidence/case-c-lookahead-14m.json` |
| Evidence hashes | every declared SHA-256 matches the shipped file | `frontend/tests/case-files.test.ts` |
| Social preview | 1200×630 PNG derived from Case B traces; SHA-256 matches the declared value | `frontend/public/social-preview.png` |
| Mock Muse | 5 targeted Studio tests passed | `pytest tests/test_policy_studio.py -k 'mock or live_provider_disabled or example_revision'` |
| Live Muse kill switch | `live_available()` is `False` by default | direct import check with `NAUTILUS_MUSE_ENABLED` unset |
| Secret scan | no tracked key patterns, no `.env` tracked, no key names in `dist` | see commands below |
| Local HTTP | frontend 200, simulation 200, evidence 200 with matching hash | Vite on 3000, API on 8000 |

The browser workflow itself was **not** run in this environment. There is no browser binary,
and the Playwright Chromium download stalled during extraction. The UI is covered by pure
markup/state tests and HTTP checks, but navigation, keyboard order, narrow-screen rendering,
file pickers and the 3D canvas still need a human pass. Do not record them as passed.

## Environments used

- Python 3.12.3 (`pyproject.toml` requires >= 3.10)
- Node.js 26.13.0, npm 11.20.0
- Frontend toolchain: Vite 7.1.7, TypeScript 5.9.3, `three` 0.180.0
- Build target: ES2022
- No environment variables were set for the offline checks; Muse/model variables were
  explicitly unset before the Python suite.

## Three verified cases

### Case A — passive ambiguity

Request:

```json
{"scenario":{"current_y":-0.06,"port_efficiency":1.0,"starboard_efficiency":1.0,"heading_bias_rad":0.0},"seed":42,"duration_s":45}
```

Outcome: `kind: ambiguous`, `selected: null`, competitive
`nominal`, `lateral_current`, `starboard_degradation`. All five declared hypotheses converge.
Protocol fingerprint `0139bc26…`; fit scores are a frozen heuristic, not probabilities.
This is passive-protocol ambiguity, **not** an agent or Muse abstention. The same scenario is
resolved by an active probe, so the demo must not claim that the agent gave up.

### Case B — bounded integral compensation

Baseline plus `integral_ki=6.0`, `integral_limit=1.5`, evaluated by the Studio on its two
development scenarios and three held-out scenarios.

| Measure | Baseline | Candidate | Difference |
|---|---:|---:|---:|
| mean RMS cross-track | 0.994072 m | 0.410259 m | −0.583813 m |
| worst outside-corridor fraction | 0.793033 | 0.0 | −0.793033 |
| completed missions | 1 | 2 | +1 |
| mean effort proxy | 310.296 N·s | 313.055 N·s | +2.759 |
| nominal-scenario RMS | 0.001981 m | 0.011398 m | inside 0.1 m gate |

Trial fingerprint `585bd1d5167ac464d81d942f37cd3fb33a4eb78c8660859200f76bb92d10130a`;
8/8 gates pass; outcome `Recommended`. Repeating the request produced the same fingerprint,
rows and traces. Held-out mean improves by 0.492883 m. The candidate was proposed by the host
example, not by Muse. The separate 3 m lookahead study in Case C's report is a different
candidate and must not be conflated with this policy.

### Case C — rejected 14 m lookahead

Predeclared candidate, host evaluation, three development scenarios, no search and no held-out
data. Values copied from `CONTROLLER_AWARE_REPORT.md`, not recomputed here.

| Scenario | 7 m baseline RMS | 14 m candidate RMS | 14 m outside fraction |
|---|---:|---:|---:|
| retained disturbance | 2.67707 m | 5.022044 m | 0.952024 |
| fresh current + | 2.441857 m | 4.595447 m | 0.946965 |
| fresh current − | 2.442906 m | 4.596372 m | 0.946965 |

Candidate fingerprint `9769d71b…`, baseline `adda0ae6…`, 3 m alternative `3add7582…`.
The 14 m candidate is worse in every scenario. The 3 m alternative is a separate candidate in
the same study and is not Case B.

## Submission asset: social preview

`frontend/public/social-preview.png` is 1200×630. It is not a screenshot and not a mock-up: the
headline numbers, candidate traces, `0.994 → 0.410 m`, `8/8` gates and the 0.493 m held-out
improvement all come from the recorded Case B trial traces, and the image carries the line
“Simulated evidence… not Muse-generated.” SHA-256:

```
ce0f4632c2e73eea9fceffcba7d2c4b3f70bd606960a223f9a5ae424f4a2325b
```

The image was rendered locally and inspected, but no product owner has approved it as the
submission card yet. `frontend/index.html` points `og:image` and `twitter:image` at
`https://nautilus-demo-delta.vercel.app/social-preview.png`. That production host still serves the
previous build and does **not** contain this file; the URL only becomes valid after an approved
deploy of this branch, and the social card must be re-checked in a link preview tool at that point.
Until then, treat the social card as prepared, not published.

## Commands

Run from the repository root unless noted. Use the project virtual environment.

```bash
# Full Python suite (about 3.5 minutes)
env -u MODEL_API_KEY -u OPENAI_API_KEY -u UPSTASH_REDIS_REST_URL -u UPSTASH_REDIS_REST_TOKEN \
  .venv/bin/python -m pytest -q -p no:cacheprovider

# Mock Muse / Studio integration
.venv/bin/python -m pytest -q tests/test_policy_studio.py \
  -k 'mock or live_provider_disabled or example_revision' -p no:cacheprovider

# Frontend unit/markup tests
cd frontend && npm test

# Deterministic demo case tests (also inside the full frontend suite)
cd frontend && node --experimental-strip-types --test tests/case-files.test.ts

# TypeScript and production build
cd frontend && npm run build

# Tracked-secret scan
git grep -nEI '(sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)' || true
git ls-files | grep -E '(^|/)\.env($|\.)' || true

# Bundle scan for server-only names and key shapes
grep -rhoE 'MODEL_API_KEY|OPENAI_API_KEY|UPSTASH_[A-Z_]+|NAUTILUS_MUSE_[A-Z_]+|sk-[A-Za-z0-9_-]{16,}' frontend/dist || true
```

## Local startup

```bash
# API (terminal 1)
.venv/bin/python -m nautilus_api.server 8000

# Frontend (terminal 2)
cd frontend && npm ci && npm run dev
```

Vite proxies `/api` to `127.0.0.1:8000`. Open `http://127.0.0.1:3000/`.
The API has no health endpoint; smoke-test it with `POST /api/v1/simulations`.

```bash
curl -sS -H 'Content-Type: application/json' \
  -d '{"scenario":{"current_y":-0.06,"port_efficiency":1.0,"starboard_efficiency":1.0,"heading_bias_rad":0.0},"seed":42,"duration_s":45}' \
  http://127.0.0.1:8000/api/v1/simulations
```

Expected: HTTP 200, public observations and `"kind": "ambiguous"`.

## Dependencies and determinism

- The Python package requires `numpy`, `matplotlib` and `scipy`; tests require `pytest`.
- The frontend has a committed `package-lock.json`; use `npm ci`, not an upgrade.
- Simulation seeds are fixed in the demo requests, so Case A and Case B are deterministic.
- No network access is needed for the offline tests. Live Muse is not exercised.
- `frontend/dist/assets/replay-*.js` is 569.45 kB and triggers Vite's chunk-size warning.
  This is a performance warning, not a build failure; the 3D viewer is lazy-chunked.

No flaky tests were observed in the full run. The suite is long because several policy and
robustness tests execute real deterministic simulations. A loaded machine can increase wall
time; it should not change outcomes.

## Missing assets and blockers

- No browser automation binary is available, so the full UI acceptance pass is pending.
- The social preview is data-derived and locally inspected, but it has no human owner approval
  and its absolute `og:image` URL is not yet served by the production host (see above).
- Case C cannot be regenerated from the public tree; its retained scenario inputs are private.
- The live Muse provider remains disabled: no verified per-token price is configured, and
  `live_available()` returns `False`.
- The local stdlib server exposes `/api/v1/muse-investigations`; the browser live-Muse client
  targets `/api/muse`. Any future live-Muse enablement must reconcile that route in the
  deployed environment before claiming the feature works.
- Production deployment is not part of this branch and was not performed. The production host
  remains the previous build, so metadata and social preview cannot be verified there.

## Muse upgrade readiness

Required contracts, and what already exists:

| Contract | Existing seam | Remaining work |
|---|---|---|
| Model-proposed hypotheses | Investigation tool schema and recorded adapters | One schema-validated hypothesis tool bound to the passive/active protocols, with host range checks. |
| Model-proposed controller revisions | `propose_controller_revision`, IR validator, source round-trip | Enforce rationale/evidence references and reject candidates that reference unavailable results. |
| Trusted tool execution | `studio_muse.call` single dispatcher | Keep all new tools behind it; no model code execution, no hidden truth. |
| Structured evidence memory | Public rows, trial rows, gates, fingerprints, ledger events | Stable result IDs for every quoted number and an append-only event store with hashes. |
| Independent numerical verification | Host re-runs and gate evaluation in `nautilus/studio.py` | Re-derive report numbers from retained runs; detect stale candidate/config IDs. |
| Live agent event traces | Muse provenance sidecar with usage, latency, termination, finalization origin | Add live Studio events with the same provenance validation; never call them chain-of-thought. |
| Verified model-generated report | Deterministic report/export path | Bind prose claims to result IDs and fail closed on unknown references. |
| Operational safety | Default-off switch, spend/token/request envelopes, daily/monthly caps | Configure verified prices, reconcile the deployed route, run one separately authorized low-cost test. |

The upgrade must not introduce new fault models, a second simulation engine, or major UI
redesign. The three demo cases and their labels must remain valid after it.
