# Nautilus Final Acceptance Ledger

Status key: **Verified** (tests or runtime evidence exist), **Implemented** (code exists, not fully verified), **Incomplete**, **Blocked**, **Excluded** (optional, infeasible, documented).

Last updated against commit `e647ff1` (feature branch `feature/autonomous-control-policy-studio`). Remote `main` at `e647ff1`.

## Release gates (at `e647ff1`)

| Gate | Result | Evidence |
| --- | --- | --- |
| Python suite | Verified: 662 passed, 4 subtests passed, exit 0 | `pytest -q` with model and Upstash variables unset |
| Frontend `npm test` | Verified: 0 failures, exit 0 | `frontend/` |
| `tsc --noEmit` | Verified: exit 0 | `frontend/` |
| Production build | Verified: exit 0 (chunk-size warning only) | `frontend/dist` |
| Bundle secret scan | Verified: none of the five secret values present | `frontend/dist` |
| Production deployment | Verified READY from `e647ff1` | `dpl_CWCNwcJHPewS4AKBBFquwVxJXCvU` |
| Browser acceptance | Not verified: no browser automation in this environment | - |

## Requirement status

| Area | Status | Notes |
| --- | --- | --- |
| Robustness gate on the host | Verified (mock tests and one real-run gate check) | `nautilus/studio_muse.py`, commit `48d31d2`. Recommendation refused before robustness, accepted after. |
| Muse connectivity (Test A) | Verified (one authentic call) | `docs/MUSE_LIVE_TEST_RESULTS.md` |
| Muse engineering loop (Test C) | Verified, but recorded before the gate | `artifacts/muse-live-engineering-run.json` (git-ignored) |
| Muse robustness continuation (Test D) | Verified | `artifacts/muse-live-robustness-run.json` (git-ignored) |
| Muse Tests 1, 2, 4, 6 (investigation, experiment planning, feedback, negatives) | Incomplete | Not run in this release |
| Muse Test 5 (rerun of robustness enforcement with the provider) | Incomplete | Not rerun after the gate; see the Test D result |
| Core Muse scientific-agent improvements (hypothesis tools, active experiments, evidence memory) | Incomplete | Not implemented in this pass |
| Muse-authored structural controller change | Incomplete | Test C produced a `integral_ki` / `integral_limit` change; structural IR change not yet demonstrated |
| Scientific-agent benchmarks against deterministic baselines | Incomplete | Not run |
| Agent Engineering Trace UI | Incomplete | Not implemented |
| Live agent execution UI with cancellation | Incomplete | Not implemented |
| Six top-level destinations | Implemented | `frontend/src/destinations.ts`, `navigation.ts`; unverified in a browser |
| Overview, Simulation Lab, Dashboards, Policy Studio, Experiments, Reports | Implemented | Frontend tests pass; no browser acceptance |
| Claim-to-evidence links | Incomplete | Not verified |
| Case Files A, B, C | Implemented | `frontend/src/case-files.ts`, `docs/EVALUATION.md` |
| Field Case 01 (real AUV data) | Excluded | See the feasibility note below |
| Documentation (README, ARCHITECTURE, EVALUATION, DEMO_RUNBOOK, RELEASE_CHECKLIST, SECURITY, MUSE_INTEGRATION, `.env.example`) | Incomplete | Several still reflect the earlier state |
| Security controls (server-only keys, token-gated paid route, kill switch) | Implemented | `api/muse.py`; bundle scan verified |

## Real-world AUV dataset feasibility

Source: `https://github.com/nature1949/AUV_navigation_dataset`, CC0-1.0, five recording CSVs plus `data format.xlsx`.

Verified from the source:

- The format spreadsheet documents units: velocities m/s, accelerations m/s^2, angular rates rad/s, angles rad. Heading is 0 = east, counter-clockwise positive. `time` is seconds from zero.
- Sample file `20220712_0_1.csv` has 940 data rows, SHA-256 `3287424eafd36f5e3129ad9bd2c21c827fc9779338f4136e84b2a6ea6369973c`.
- Position is GPS latitude and longitude. `alt` is 0 in the sampled rows.
- The spreadsheet says some fields do not change underwater.

Why the Field Case is excluded:

- The data has no labelled failure, no control commands and no thrust. Measured velocity is not commanded thrust.
- The vehicle is surface-referenced and the planar dynamics do not match the existing differential-thruster model, so the bridge would be a limited initial-condition and reference-geometry transform only.
- The only defensible claim would be a simulated disturbance applied to a measured path. That claim cannot be verified against the physical fault mechanism.

Decision: excluded from the Production interface. Documented here as a scientific compatibility limitation.

## Pass status (uncommitted tree on top of `7a45245`)

- Phase A (scientific agent): evidence IDs (`E1`), evidence-first guard, hypothesis records citing evidence IDs, append-only action log, bounded memory with stable IDs, counterfactual notes. Focused tests pass (132).
- Phase B (Muse-authored source): `from_source` compilation is in place; an end-to-end Muse-proposed source run is not yet executed.
- Phase C (live Muse): one bounded Studio session ran earlier (8 requests, about 25k in / 3.7k out, est. $0.047), before the malformed-reply fix. No final decision was recorded. Aggregate estimated spend to date is about $0.23 of $30.
- Phase D (UI): frontend `npm ci`, `npm test`, `tsc --noEmit` and `npm run build` pass on the current tree.
- Full Python suite on the current tree: 666 passed, 2 failed.

### Open failures

1. `tests/test_muse_evaluation.py::test_resume_skips_completed_pairs_and_prevents_duplicates` and `::test_provider_failure_is_terminal_case_and_campaign_stop` fail with `Frozen source/runtime changed`. `evaluate_muse.make_manifest` pins `CANDIDATE=340d1c1` and rejects any working-tree change under `nautilus/*.py`. The 14 tests pass at HEAD. This is an intentional protocol guard. It is not bypassed or re-pinned. Resolving it requires either reverting the `nautilus/` edits or a documented protocol revision by the owner.

## Remaining work (in order)

1. Run the Muse Tests 1, 2, 4 and 6 with the real provider within the $30 budget, and record results.
2. Rerun the robustness-gate test (Test 5) with the real provider.
3. Implement or verify the core scientific-agent enhancements and benchmark them honestly.
4. Implement the Agent Engineering Trace and claim-to-evidence links, if feasible.
5. Update all documentation to the final state.
6. Rerun the release gates on the final commit, commit, merge to `main`, deploy, and run production smoke tests.
