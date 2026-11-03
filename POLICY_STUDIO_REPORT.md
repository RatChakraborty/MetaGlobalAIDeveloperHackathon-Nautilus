# Autonomous Control Policy Studio

Built on `feature/autonomous-control-policy-studio` from `315ae7e`. Nothing in this
branch is committed, pushed, merged or deployed. No live Muse request was made, no
model credit was spent, no credential was read on any Studio path, and no controller
was sent to hardware. Production (`https://nautilus-demo-delta.vercel.app/`) is
untouched.

Status vocabulary used throughout: **Implemented locally** (code exists) ·
**Verified locally** (a check actually ran here) · **Deployed to Preview** ·
**Verified in Preview** · **Ready for Production** · **Not implemented**.

| Area | Status |
| --- | --- |
| Bounded controller IR + interpreter | Verified locally (624 Python tests) |
| Readable source ↔ IR compiler | Verified locally |
| Real simulator execution of revised policies | Verified locally (`tests/test_policy_studio.py`) |
| Paired / held-out evaluation and outcomes | Verified locally (scenarios A–C) |
| Hostile-policy rejection | Verified locally (scenario D) |
| Mocked Muse engineering loop | Verified locally (scenario E) |
| Studio website tab | Verified locally (build, tsc, 94 frontend tests, live dev server) |
| Full browser click-through of scenario F | **Pending user confirmation** — this VM has no browser automation |
| Studio function on Vercel Preview | **Not deployed** — needs approval |
| Live Muse | **Not implemented by design** (`live_available() == False`) |
| Investigation → Studio evidence handoff | Partial: public-evidence contract only, see §17 |

## 1. Branch and commit

- Branch: `feature/autonomous-control-policy-studio`
- Base commit: `315ae7e` ("Serve the free lab paths from Vercel and harden the live-run guards")
- HEAD: `315ae7e` — **all Studio work is uncommitted working-tree state**, because
  committing is a step toward the push you asked me not to do without approval.
  Every file listed below is present and tested in the tree.

## 2. Changed files

New (2,158 lines):

| File | Lines | Role |
| --- | --- | --- |
| `nautilus/policy_ir.py` | 200 | IR schema, validation, interpreter, limits |
| `nautilus/policy_runtime.py` | 99 | bounded stateful controller shell (integrator + filter) |
| `nautilus/policy_source.py` | 208 | readable source ↔ IR (parse-only `ast`) |
| `nautilus/studio.py` | 146 | matched paired trials, outcomes, robustness |
| `nautilus/studio_muse.py` | 342 | tool schemas, session, budgets, mock provider |
| `api/v1/studio.py` | 161 | Vercel function `/api/v1/studio` |
| `run_policy_studio.py` | 105 | operator CLI reproducing scenarios A–E |
| `tests/test_policy_studio.py` | 504 | 61 tests |
| `frontend/src/studio-api.ts` | 56 | typed client |
| `frontend/src/studio-view.ts` | 261 | Studio panel markup and mounting |
| `frontend/tests/studio-view.test.ts` | 76 | 6 tests |

Modified:

| File | Δ | Why |
| --- | --- | --- |
| `nautilus/simulator.py` | +18/−7 | optional `policy=` hook on `cable_follow`; no default-path change |
| `nautilus_api/server.py` | +22 | local dev route `/api/v1/studio` delegating to the same dispatch |
| `frontend/src/main.ts` | +5/−3 | Studio tab, render branch, mount call |
| `frontend/src/style.css` | +8 | Studio styles in the existing design system |
| `frontend/vite.config.ts` | +1 | dev proxy `/api → 127.0.0.1:8000`, mirroring Vercel same-origin |
| `vercel.json` | +3 | `api/v1/studio.py` `maxDuration: 60` |

## 3. Reused V6 components

Reused unchanged, no validation weakened:

- `nautilus/v6/robustness.py`: `build_suite()`, `SUITE_SPECS`, `GATES`, `ACCEPTANCE`,
  `decide()`. The Studio does not define its own scientific gates; it consumes the
  frozen ones and adds a split, not a relaxation.
- `nautilus/v6/evaluation.py`: `instrumentation()`.
- `nautilus/simulator.py`: physics, sensor model, `metrics()`, `Controller`, `command()`
  — the baseline IR reproduces `command()` bit-for-bit.

Deliberately **not** reused:

- `v6/proposal.py` (parameter sweeps) — superseded: the Studio's search space is the
  IR, which also covers structural edits, and candidates are gated by `decide()`.
- `v6/patch.py` (static source diff) — remains review/display only. This report never
  treats an AST check or a token denylist as a sandbox.
- `v6/artifact.py` — provenance is re-expressed as `policy_fingerprint()`
  (SHA-256 over canonical JSON) plus a source fingerprint in every payload.

## 4. The controller IR and source language

Schema `nautilus.policy-ir.v1`. A policy is a JSON document:

```
{"schema": "nautilus.policy-ir.v1",
 "name": "...",
 "params": {"heading_kp": 39.0, "heading_kd": 18.0,
            "integral_ki": 0.0, "integral_limit": 0.5, "yaw_filter_alpha": 0.0},
 "desired_heading": <expr>, "port": <expr>, "starboard": <expr>}
```

Expressions are trees over a fixed vocabulary:

- binary: `add sub mul div min max lt gt atan2`
- unary: `neg abs sat wrap_angle`
- public inputs: `y_m`, `heading_rad`, `yaw_rate_radps`, `integral_y`,
  `integral_limit_m`, `filtered_yaw_rate`
- constants: `lookahead_m`, `max_heading_rad`, `cruise_thrust_n`, `max_thrust_n`,
  `lever_arm_m`
- parameters: the five declared `params`, each with a hard numeric bound
  (`heading_kp`, `heading_kd` ≤ 200; `integral_ki` ≤ 50; `integral_limit` ≤ 5;
  `yaw_filter_alpha` ∈ [0,1])

Limits: `MAX_NODES = 96`, `MAX_DEPTH = 14`, output clipping to `±max_thrust_n`,
non-finite results are a hard error.

The readable source is a list of assignments in a Python-looking but separate
language (`desired`, `error`, `moment`, `port`, `starboard`), compiled with
`ast.parse` and a whitelisted walk that accepts only: assignment, numbers, declared
references/parameters, `+ - * /`, `min/max/abs/atan2`, `clip`, `wrap`, and
`if(cond, a, b)`. Loops, recursion, imports, attribute access, calls outside the fixed
table, and any other statement are rejected with a readable error. **Arbitrary Python
controllers are not supported and are not claimed to be.**

Baseline controller source as the site shows it:

```
desired = max(-(max_heading_rad), min(max_heading_rad, atan2(-(y_m), lookahead_m)))
moment  = ((((heading_kp * wrap((desired - heading_rad))) - (heading_kd * yaw_rate_radps))
           - (integral_ki * integral_y)) / (2.0 * lever_arm_m))
port      = (cruise_thrust_n - moment)
starboard = (cruise_thrust_n + moment)
```

The baseline IR is not a reimplementation: a test asserts it equals the simulator's
`command()` across the operating envelope, and that the resulting trajectory is
identical to the default controller's.

## 5. Security and execution boundary

| Prohibited | How |
| --- | --- |
| Arbitrary Python | no `exec`/`eval` anywhere; JSON tree walked by `policy_ir.evaluate` |
| Imports / attribute access / calls | compiler rejects any `Import`, `Attribute`, `Call` outside its table, `Lambda`, `Subscript` |
| Filesystem / network / env / subprocess | the interpreter has no such capability and no module imports beyond `math` |
| Dynamic loading | no `importlib`, no `__import__`, no `getattr` |
| Hidden simulator state | inputs are an explicit allowlist; `tests/test_policy_studio.py::test_evaluator_cannot_reference_hidden_state` asserts `faults`, `port_efficiency`, truth state names, `plant`, `HIDDEN_PLANT` are unusable |
| Unbounded loops/recursion | IR has no loops; depth (14) and node (96) caps; source has no loop or def syntax |
| Unbounded memory | bounded node count, bounded state (one integrator, one filter), bounded params, 16 KB request body |
| Non-finite output | `PolicyError` on non-finite constant or result, division by zero, or non-finite command |
| Silently wrong physics | commands clipped to actuator limits, saturation recorded |

State is bounded and explicit: the integrator is clamped to
`±integral_limit` and frozen while the command is saturated (anti-windup); the yaw
low-pass is a single first-order state with `alpha` bounded to [0,1]. Both are
deterministic given fixed inputs and initial state.

## 6. Controller ↔ simulator integration

`nautilus/simulator.py` gained one optional argument:

```python
def simulate(..., policy=None)
...
if policy is not None and experiment.maneuver == "cable_follow":
    port, starboard, desired = policy(t, obs_y, obs_heading, obs_yaw_rate, vehicle, controller)
else:
    port, starboard, desired = experiment_command(...)
```

The callback receives observed channels only (`obs_y`, `obs_heading`,
`obs_yaw_rate`, the `Vehicle`/`Controller` dataclasses the baseline already had) plus
the policy's own state through `PolicyController`. Physics, sensor model, fault
injection and metrics are untouched; with `policy=None` every existing code path is
byte-identical, which is why the 563 pre-existing tests still pass unmodified.

Verification that a policy change alters real behaviour:
`test_structural_change_changes_simulated_behavior` changes a coefficient in the IR
and asserts the simulated trajectory diverges; `test_seeded_simulations_are_reproducible_with_policy`
asserts same-seed determinism.

## 7. Evaluation methodology

- `paired_trial(policy, part, scenario_ids)` runs baseline and candidate on the *same*
  `DevelopmentScenario`: identical vehicle, faults, mission, plant, seed, duration.
  Differences therefore come from the control law, not from sampling.
- Common random numbers: both arms use the same seed, so sensor noise sequences are
  identical. Closed-loop divergence means the two arms visit different states, so the
  noise realization is common but not independent — reported as such in every payload
  (`methodology.common_random_numbers` and a note that paired differences are not
  independent samples).
- Metrics, all measured by the simulator: `rms_cross_track_m`,
  `max_abs_cross_track_m`, `fraction_outside_corridor`,
  `command_saturation_fraction`, `mission_success`, `effort_proxy_n_s`.
- Split of the frozen seven-case V6 suite:
  - development (iterated on): `nominal`, `current_positive`, `current_negative`,
    `thruster_degradation`
  - held-out (reported, never used to select): `heading_bias`,
    `compound_current_bias_degradation`, `model_mismatch`
- The held-out response explicitly carries
  `"note": "Held-out split: reported as evidence, never used to select a candidate."`
- No stability guarantee is claimed anywhere; the wording is "tracking metric
  improvement under matched simulation".

## 8. Acceptance rules

A candidate is **Recommended** only if `decide()` accepts it on the development split,
i.e. every gate passes:

| Gate | Threshold |
| --- | --- |
| `finite_runs` | all traces finite |
| `mean_rms_improvement` | mean cross-track RMS improves ≥ 0.05 m |
| `no_scenario_rms_regression` | no scenario worse by > 0.10 m |
| `no_worst_case_cross_track_regression` | worst-case max error +≤ 0.25 m |
| `no_worst_case_excursion_regression` | worst-case corridor excursion +≤ 0.05 |
| `no_completion_regression` | completions do not fall |
| `no_saturation_regression` | worst-case saturation +≤ 0.05 |
| `no_effort_blowup` | mean effort ≤ ×1.2 |

Outcome mapping (`nautilus.studio.outcome`):

- **Recommended** — `decide()` accepted.
- **Inconclusive** — no gate failed except `mean_rms_improvement`; evidence does not
  separate the candidate from noise.
- **Rejected** — the candidate either improved the aggregate but failed a regression
  or safety gate, or improved nothing and failed something.

One aggregate metric can never carry an acceptance; B below is exactly that case.

## 9. Muse engineering loop

Tool schemas (validated, unknown tools and unknown arguments rejected):

`inspect_controller`, `inspect_diagnosis_evidence`, `propose_controller_revision`
(params or source text), `validate_controller`, `execute_controller_trial`,
`inspect_experiment_results`, `compare_candidate_policies`,
`evaluate_policy_robustness`, `finalize_controller_recommendation`.

Ordering is evidence-driven, not scripted: the session refuses a trial before
validation, refuses a recommendation without a Recommended trial, and the mock planner
re-reads results and may revise after a rejection. Limits (`Budget`):
12 requests, 12 trials, 3 candidates, 180 s wall clock — each enforced with an explicit
`ToolError`, so the loop stops rather than silently truncating. Abstention is a valid
terminal decision.

**Live Muse is disabled, not stubbed as working.** `live_available()` returns `False`,
every payload carries `live_available: false`, `mock: true`, `provider_calls: 0`, and
`/api/v1/muse-investigations` (the existing paid path) is untouched and still requires
`NAUTILUS_DEMO_TOKEN` plus the Upstash budget ledger. The Studio's `muse` action never
reaches a provider and reads no key. Enabling live engineering requires the ten
spending-control steps in §7 of the request, of which only "fail closed" is currently
satisfied — see §18.

## 10. Website UI

One application, one design system, no second app:

- A `Policy Studio` tab joins `Simulation Lab` in the existing tab bar (shown when the
  API is enabled), mounted by `mountStudio` into `#studio-root`.
- Panel contents: baseline source in an editor, parameter fields, Validate, Run paired
  trial, Robustness (held-out), Reset to baseline, policy fingerprint, gate table with
  pass/fail, per-scenario metric table, trajectory/command plots with corridor overlay,
  source diff vs baseline, and a Muse panel whose controls show the disabled state with
  the reason returned by the API.
- An exportable engineering report is assembled client-side from the same payloads
  (`.studio-report` text block) — no numbers are invented in the frontend; every
  displayed number comes from a response.

## 11. API routes

`POST /api/v1/studio` (free, deterministic, no credential, 16 KB body):

| Action | Body | Returns | Measured here |
| --- | --- | --- | --- |
| `baseline` | `{}` | IR, source, fingerprint, `live_muse: false` | 0.03 s, 3 KB |
| `validate` | `{source}` or `{policy}` (+ optional `params`) | `{valid, policy, source, fingerprint}` or `{valid:false, error}` | 3 ms |
| `trial` | `{policy|source, params?, part?, scenarios?}` | paired rows, gates, aggregate, outcome, ≤120-point traces | 0.27 s, 15 KB |
| `robustness` | `{policy|source, params?}` | held-out rows, decision, outcome | 0.51 s, 6 KB |
| `muse` | `{}` | mocked session transcript, budget, final decision | 1.26 s, 19 KB |

Errors: 400 unknown action / unknown scenario / oversized or malformed body, 422
policy or source rejection, 500 evaluation failure. `?action=` is never used, so a
link cannot trigger simulator work. The same `dispatch()` also serves the local dev
server (`POST /api/v1/studio`), so local and deployed code cannot drift.

## 12. Tests

- Full Python suite: **624 passed in 214 s** (563 baseline tests untouched + 61 new),
  run with `MODEL_API_KEY`, `OPENAI_API_KEY`, `UPSTASH_REDIS_REST_URL` and
  `UPSTASH_REDIS_REST_TOKEN` unset.
- `tests/test_policy_studio.py` (61): IR schema and bounds, node/depth limits,
  division-by-zero and non-finite rejection, hidden-state rejection, output clipping,
  source round-trip, structural revision, six hostile sources, source size limit,
  integrator bounds and anti-windup, filter determinism, real behaviour change, seed
  reproducibility, split discipline, accept/reject/inconclusive, robustness on held-out
  only, mock session end-to-end, revise-after-rejection, abstention, budget stop,
  recommendation precondition, tool schema, validate-before-execute, candidate cap,
  live provider disabled, five dispatch tests, and five HTTP tests (real socket:
  no credential needed, wired numbers equal library numbers, hostile source 422,
  malformed/oversized 400, dev server shares dispatch).
- Frontend: **94 passed** (88 baseline + 6 Studio), `npx tsc --noEmit` clean,
  `npm run build` succeeds (only the pre-existing 569 kB chunk warning).
- Secret scan: `grep -rIl` for `MODEL_API_KEY`, `UPSTASH_REDIS_REST_TOKEN`,
  `NAUTILUS_DEMO_TOKEN`, `OPENAI_API_KEY`, `sk-` over `frontend/dist` — no matches
  (924 KB bundle).

## 13. Successful, rejected and inconclusive investigations

Reproduce with
`env -u MODEL_API_KEY .venv/bin/python run_policy_studio.py --output /tmp/policy_studio_evidence.json`
(5.4 s; the CLI refuses to write inside the repository).

**A — Recommended.** Structural change: add bounded integral compensation
(`integral_ki = 6.0`, `integral_limit = 1.5`; baseline integral gain was 0), which
introduces the `integral_y` term into the law. Development mean RMS difference
**−0.6234 m**, all gates passed:

| Scenario | Baseline RMS | Candidate RMS |
| --- | --- | --- |
| nominal | 0.0020 | 0.0114 |
| current_positive | 1.9862 | 0.8091 |
| current_negative | 1.9826 | 0.8054 |
| thruster_degradation | 0.4603 | 0.3116 |

Held-out (not used to select): mean −0.4929 m, `heading_bias` 1.7130 → 0.5819,
`compound_current_bias_degradation` 0.6650 → 0.3142, `model_mismatch` 0.0035 → 0.0069.
The nominal regression (0.002 → 0.0114 m, tiny in absolute terms but 5× in relative) is
reported, not hidden; it stays inside the declared 0.10 m gate.

**B — Rejected.** `integral_ki = 12.0`, `integral_limit = 2.5`. Aggregate improves
(−0.0667 m) but four gates fail: `no_scenario_rms_regression` (nominal 0.002 → 0.1005),
`no_worst_case_cross_track_regression`, `no_completion_regression`,
`no_effort_blowup`. Held-out mean **+0.1840 m** (a regression). This is the
"one aggregate metric improved" case the request asked to reject.

**C — Inconclusive.** `integral_ki = 0.02`. Mean −0.0011 m; only
`mean_rms_improvement` fails, no safety gate breached → abstain/inconclusive rather than
a fabricated recommendation. Held-out −0.0009 m.

**D — Hostile policies** (all six rejected before execution): `imports`,
`attribute_access`, `function_calls`, `loops`, `hidden_truth`, `state_mutation`.

**E — Mock iterative engineering.** Deterministic provider, real numerics:

```
inspect_controller → inspect_diagnosis_evidence → propose_controller_revision(integral-ki-6)
→ validate_controller → execute_controller_trial → evaluate_policy_robustness
→ finalize_controller_recommendation(recommend)
```

Final: `decision: recommend`, `candidate_id: integral-ki-6`, outcome `Recommended`,
budget `7/12 requests, 7/12 trials, 3 candidates, 1.25 s of 180 s`,
`provider_calls: 0`, `live_available: false`. A separate test drives the
revise-after-rejection path (`integral-ki-3` rejected, then a corrected candidate) and
another drives abstention.

## 14. Evidence that controller changes change simulation

1. `test_structural_change_changes_simulated_behavior`: an IR coefficient edit produces
   a different trajectory from the same seed.
2. Scenario A's per-scenario numbers differ only through the control law (paired,
   same seed, same plant); `nominal` 0.0020 → 0.0114 m proves the executed command stream
   changed.
3. `test_baseline_ir_reproduces_simulator_control_law_exactly` and the trajectory
   equality test prove the default path is unchanged, so A's difference cannot come
   from a physics change.
4. `tests/test_policy_studio.py` HTTP tests assert the wired numbers equal the library's
   to 1e-12, so the website displays measured values, not renderings.

## 15. Browser and deployment validation

- Verified locally over real HTTP: `GET /` with the preview `Host` header → 200; the
  served `main.ts` contains the `Policy Studio` tab; through the Vite proxy the site's
  own origin performed `baseline → validate → trial → robustness → muse` and received
  `Recommended` for the integral candidate and `recommend` for the mock session. A
  schema-only policy produced 422 on the same origin.
- **Not verified: the browser click-through (scenario F visual/interaction).** This VM
  has no browser automation. The dev server is running and shown in the Browser panel,
  but the tab must be clicked, the editor used, and the plots inspected by you.
- **Not deployed:** `api/v1/studio.py` exists and is tested, and `vercel.json` now gives
  it `maxDuration: 60`, but nothing has been deployed to Preview. Preview verification
  and the Production question are yours to authorize.

## 16. Remaining unsupported features

- Live Muse engineering (§7 of the request) is **not implemented**: no priced model is
  bound to the Studio, no reservation is computed, no reconciliation exists. The
  existing `$0.41` reservation belongs to `api/muse.py` and is neither reused nor
  extended. Enabling live work requires a priced model, hard request/token caps, a
  conservative per-run reservation, shared daily/monthly caps, reserve-then-reconcile
  against measured usage, fail-closed handling of missing usage/timeouts, model and
  price allowlists, and concurrency/idempotency checks — none of which are in place.
- Structural edits are expressed as IR/DSL trees. Adding a genuinely new primitive
  (e.g. a new filter class, thrust allocation matrix, or gain schedule table) requires
  a new IR version; the interpreter's vocabulary is fixed at
  `add sub mul div min max lt gt atan2 neg abs sat wrap_angle`.
- No multi-invocation resumable session: a Studio session is one request. Measured
  worst case (1.26 s, 19 KB) is far inside a 60 s function, so resumption was not
  needed at this budget; a live session would need it.
- Scenario F's visual/interaction confirmation and all Preview work are pending.

## 17. Diagnosis → Studio handoff (partial)

The evidence contract exists and is enforced: `inspect_diagnosis_evidence` returns
`scenario_id`, `matched: true`, three public baseline metrics,
`uncertainty: "inferred from observed tracking error; not a confirmed fault"` and
`hidden_truth_exposed: false`, measured from a real matched baseline run under
`current_positive`. Hidden faults and plant truth are never passed.

**Not implemented:** passing a specific investigation's export into a Studio session.
There is no `evidence_ref`/`investigation_id` argument, and the website does not hand
the loaded record to the Studio panel. So the *shapes* match and the boundary is right,
but the automatic wiring described in §10 of the request is incomplete.

## 18. Deployment constraints and cost

- Vercel Python function, one invocation per action. Measured: baseline 0.03 s,
  validate 3 ms, trial 0.27 s, robustness 0.51 s, muse 1.26 s; payloads 3–19 KB
  (traces capped at 120 points per series, 2 scenarios by default, ≤4 on request).
  `maxDuration: 60` is ample; Hobby memory and response limits are not approached.
- No persistence, no background process, no filesystem state: every response is
  recomputed from the simulator, so there is nothing to lose between requests.
- Cost of the free paths: **$0** — no provider contact, no Redis use, no credential.
  Only Vercel function invocations and bandwidth.
- Cost of the mock Muse path: **$0** — deterministic mock.
- Cost of live Muse: **unknown and unestablished**, therefore disabled. Do not reuse the
  `$0.41` reservation.

## 19. Approvals needed before this leaves the branch

1. Commit the working tree on `feature/autonomous-control-policy-studio` (message and
   scope listed above).
2. Push the branch.
3. Deploy to Preview and run the checks I cannot: browser click-through (scenario F),
   Studio tab rendering, trial plots, Muse panel disabled state, and a live
   `POST /api/v1/studio` from the Preview origin.
4. Decide whether `main` / Production ever receives this. Production currently serves
   the free lab paths and is unchanged by this branch.
5. A bounded live-Muse test would need a separate, written cost envelope first.

## 20. Honest assessment

The engineering core is real and verified: a bounded IR with a hand-written
interpreter, a readable source language that compiles to it, real simulator execution,
paired matched evaluation reusing the frozen V6 gates, honest Recommended / Rejected /
Inconclusive outcomes (including a case where an aggregate gain is rejected), a
hostile-policy suite that rejects all six attacks before execution, and a multi-step
mocked Muse session that selects experiments, validates before executing, and stops
with an evidence-based recommendation.

What is not done: live Muse and its spending controls, the investigation→Studio
handoff, new IR primitives, and every deployment step. So the final acceptance
standard — *you* diagnose a failure, edit the controller in the website, run it, compare,
and export a report — is satisfied in code and over HTTP but **not yet confirmed by a
human in a browser against a deployed Preview**. Until you click through it and approve
a Preview deployment, this is "verified locally", not "ready for production".

## Reproduction

```
# Python (no provider keys, no network)
env -u MODEL_API_KEY -u OPENAI_API_KEY -u UPSTASH_REDIS_REST_URL \
    -u UPSTASH_REDIS_REST_TOKEN .venv/bin/python -m pytest -q tests        # 624 passed

# A–E evidence, written outside the repository
env -u MODEL_API_KEY .venv/bin/python run_policy_studio.py \
    --output /tmp/policy_studio_evidence.json

# Frontend
cd frontend && npm test && npx tsc --noEmit && npm run build               # 94 passed, build ok

# Local end-to-end: API on 8000, site on 3000 (Vite proxies /api)
.venv/bin/python -m nautilus_api.server 8000 &
cd frontend && npm run dev -- --port 3000
```
