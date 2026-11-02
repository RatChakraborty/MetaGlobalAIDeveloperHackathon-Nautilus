# V6 verified control-policy testing laboratory

Built on the accepted V5 commit `fba4e806886f00b6a4af6f1f176a25e334d13bc0` on
`feature/nautilus-v6-control-lab`. Not merged, not deployed, no live model request and
no hardware execution. `nautilus/simulator.py`, the safety envelope, scenario
generation, the evaluator and every frozen V4/V5 schema are unchanged
(`git diff --stat` against `simulator.py` is empty; the approved source fingerprint
remains `3893f25b…ddf9901`).

## Scope

Nautilus can now take one evidence-supported issue, propose a bounded control-policy
change, run it against the approved baseline under matched simulated conditions across
a fixed development suite, apply a predeclared acceptance rule, and emit a validated
recommendation package for human review.

A diagnosis never implies that a controller change repairs the fault. Every artifact
carries the explicit qualification that a tracking-metric improvement does not repair a
degraded thruster, and the scope string is fixed:
*Engineering recommendation from matched offline simulation; not a deployed repair,
safety certificate or diagnosis evidence.*

## 1. Workflow

Investigation → evidence-supported issue → candidate change → trusted validation →
matched simulation → robustness assessment → operator review → configuration artifact.

`ControlLabHost` runs this phase only after scientific finalization. It cannot append
fault-diagnosis evidence, re-open a closed ledger, or expose private scenario truth.

## 2. Versioned policy interface (`nautilus/v6/policy.py`, schema `nautilus.control-policy.v1`)

Records controller identity, source path/fingerprint/revision, the declared parameter
schema with units and bounds, observation and command contracts, actuator limits
(45 N per command, 0.32 m lever arm), determinism/initialization/reset semantics and an
explicit unsupported list (learned policies, integrators, adaptive scheduling, measured
force or surge feedback, six-DOF control, runtime code loading, physics or fault edits).

`build_policy(Controller())` → `policy_hash = f4d07641f52f0df18235c3b9a96ca59af0de66728286bed36ce3ff565894014c`.
The contract is closed: tampered bounds, a foreign source path, an unsupported
inspection status or any changed field fails validation.

## 3. Parameter-level improvement (`nautilus/v6/proposal.py`)

Tunable parameters are exactly lookahead, heading P gain, yaw-rate D gain and cruise
thrust. A model proposal is a closed five-field object (`parameter`, `value`,
`rationale`, `evidence_refs`, `expected_effect`); injected metrics, unknown fields,
out-of-bounds values, non-finite numbers and non-public evidence references are rejected.

Proposed, tested and accepted changes are separate records. Search is a bounded
coordinate search over a predeclared 10-value grid with at most 14 candidates, screened
on **two** development cases (`nominal`, `current_positive`).

**Selection exposure is partial, and is now disclosed by the code.** Those two cases
are members of the reported seven-case suite (verified: `screened_case_ids ∩ suite` is
exactly those two ids), so this is not held-out evaluation. Every evaluation records the
split and states it, and `validate_robustness` refuses any record that claims
`held_out: true` or fails to account for all seven cases. The five cases that never
touched selection are reported separately below; their mean RMS improvement (−0.522 m)
is essentially identical to the full-suite number (−0.529 m), so the conclusion does not
depend on the leaked pair.

**The selected value sits at the grid edge, not at the bounds edge.** Lookahead bounds
are 2–20 m and the predeclared grid began at 3 m. Two exploratory points below the grid
(never used for selection) were measured afterwards: lookahead 2.5 m gives a better
mean (−0.577 m unscreened) and lookahead 2.0 m better still (−0.618 m), but model-
mismatch regression grows to +0.053 m and +0.150 m respectively; 2.0 m fails the
declared per-scenario limit outright. So the grid did not truncate a change the rule
would accept — but the specific value 3.0 m is an artefact of a fixed grid, not a
uniquely determined optimum, and 2.5 m would also have passed. Every attempt, including
regressions and these exploratory points, is retained.

Measured screening (mean cross-track RMS difference, negative is better):

| Candidate | Δ RMS (m) | Admissible |
|---|---:|---|
| lookahead 3 m | −0.4563 | yes |
| lookahead 5 m | −0.2041 | yes |
| lookahead 9 m | +0.1628 | no |
| lookahead 11 m | +0.2925 | no |
| heading Kp 30 | +0.0098 | no |
| heading Kp 48 | −0.0049 | yes |
| heading Kd 12 | −0.0092 | yes |
| heading Kd 26 | +0.0126 | no |
| cruise thrust 11.5 N | +0.1021 | no |
| cruise thrust 15 N | −0.1036 | yes |
| lookahead 3 + Kp 48 | −0.4613 | yes |
| lookahead 3 + Kd 12 | −0.4606 | yes |
| **lookahead 3 + thrust 15** | **−0.5075** | **yes** |

13 candidates, 1,008.98 simulated seconds, selected `{lookahead_m: 3.0, cruise_thrust: 15.0}`.

## 4. Matched evaluation (`nautilus/v6/evaluation.py`)

Each case runs the baseline and the candidate through the frozen V4 development
comparison: identical vehicle, faults, mission, plant, initial zero state, timestep,
noise protocol and seed. Instrumentation adds an actuation-effort proxy
(`Σ mean(|port|,|starboard|)·Δt`), mean and peak absolute command, maximum |yaw rate|,
finiteness and guard context. Guard/fallback is reported as not applicable for unguarded
matched missions; corridor excursions are measured directly. All results are paired
differences, never candidate-only metrics.

## 5. Robustness suite and predeclared rule (`nautilus/v6/robustness.py`)

Seven fixed development cases, each with its own seed but a shared seed per
baseline/candidate pair: nominal, positive current (+0.45 m/s), negative current,
thruster degradation (port efficiency 0.45), heading bias (+0.30 rad), compound
current + bias + starboard degradation, and model mismatch (lag 1.2 s, 4 N dead zone,
1.12× drag). Equal budgets: one baseline and one candidate run per case.

Thresholds, fixed before any candidate exists: mean RMS improvement ≥ 0.05 m;
per-scenario regression ≤ 0.10 m; worst-case max cross-track increase ≤ 0.25 m;
worst-case excursion-fraction increase ≤ 0.05; no completion regression; saturation
increase ≤ 0.05; mean effort ≤ 1.20× baseline.

Measured result for the selected candidate (7 cases, 14 simulations, 368.91 simulated
seconds):

| Scenario | RMS (m) base → cand | Max (m) | Outside fraction | Completed |
|---|---|---|---|---|
| nominal | 0.002 → 0.006 | 0.005 → 0.014 | 0.000 → 0.000 | yes → yes |
| current_positive | 1.986 → 0.891 | 2.367 → 1.159 | 0.793 → 0.000 | no → yes |
| current_negative | 1.983 → 0.887 | 2.362 → 1.158 | 0.793 → 0.000 | no → yes |
| thruster_degradation | 0.460 → 0.258 | 0.565 → 0.299 | 0.000 → 0.000 | yes → yes |
| heading_bias | 1.713 → 0.843 | 2.142 → 1.044 | 0.698 → 0.000 | no → yes |
| compound_current_bias_degradation | 0.665 → 0.193 | 0.719 → 0.371 | 0.000 → 0.000 | yes → yes |
| model_mismatch | 0.004 → 0.032 | 0.008 → 0.092 | 0.000 → 0.000 | yes → yes |

| Aggregate | Baseline | Candidate | Difference |
|---|---:|---:|---:|
| Mean cross-track RMS (m) | 0.9732 | 0.4444 | −0.5288 |
| Worst-case maximum cross-track (m) | 2.3669 | 1.1592 | −1.2077 |
| Worst-case outside fraction | 0.7930 | 0.0000 | −0.7930 |
| Completed missions | 4 | 7 | +3 |
| Worst-case saturation | 0.0000 | 0.0000 | 0.0000 |
| Mean effort proxy (N·s) | 362.00 | 373.00 | +11.00 (+3.0%) |

Every declared gate passed (observed vs threshold): finite runs 0/0; mean RMS
−0.5288/−0.05; worst scenario regression +0.0286/+0.10; worst-case cross-track
−1.2077/+0.25; worst-case excursion −0.7930/+0.05; completions 7/4; saturation
0.0000/+0.05; mean effort 373.00/434.40. Decision: **accept on the development suite**
(the artifact carries that qualification verbatim; it is not a held-out result).

Split by selection exposure (measured from the same runs):

| Subset | Cases | Mean RMS base → cand | Δ | Worst-case max base → cand | Completed |
|---|---:|---|---:|---|---|
| Screened (used by search) | 2 | 0.9941 → 0.4486 | −0.5455 | 2.3669 → 1.1592 | 1 → 2 |
| Unscreened (never consulted) | 5 | 0.9649 → 0.4428 | −0.5221 | 2.3616 → 1.1583 | 3 → 5 |

The two summaries agree to within 3 mm of mean RMS, so the result is not an artefact of
tuning on the screened pair.

**Gate calibration check.** The per-scenario regression limit (0.10 m) is 6.7% of the
1.5 m corridor half-width, which is generous as an absolute bound. The largest measured
per-scenario regression is +0.0286 m, so re-applying the rule with a tightened 0.05 m
limit (56% stricter) still accepts this candidate with no failed gate. Tightening to
0.03 m would reject the model-mismatch case — the candidate is accepted on the declared
rule, not on a wide margin.

Two cases regress in absolute terms — nominal (2 mm → 6 mm) and model mismatch
(4 mm → 32 mm) — both far inside the declared per-scenario limit. The candidate is not
uniformly better; it trades a small nominal and mismatch penalty for large gains under
currents and bias. The rule refuses the inverse pattern by construction: a candidate
whose mean RMS falls while its worst-case corridor behaviour grows is rejected by
`no_worst_case_cross_track_regression` even when `mean_rms_improvement` passes, which
is covered by an explicit test.

No simulation result is a real-world controller safety certificate.

## 6. Model reasoning inside host limits (`nautilus/v6/host.py`)

`ControlLabHost` exposes a sanitized context: policy contract, permitted parameters,
optional diagnosis rubric, host screening results, budgets, patch availability and the
tool list. It withholds private scenario truth, current values, fault efficiencies and
seeds. Tests assert that none of those appear in the serialized context or the artifact.

The model may propose, request evaluation, interpret and recommend. The host alone runs
numerics, so a proposal containing metrics is rejected as a schema violation. The host
rule governs the decision; a model recommendation is recorded separately with an
`agreement` flag. When the model recommends acceptance of a candidate the rule rejects
(longer lookahead under lateral current), the artifact records `decision: reject`,
`agreement: false`, no approved difference and a rejection risk note.

## 7. Host-owned testing enforcement

Whitelisted parameters only; bounded proposal count (4) and evaluation count (≤4, default
2); simulation budget checked against a per-call estimate before running; deterministic
seeds owned by the host; finite-value validation; no filesystem, network or subprocess
use anywhere in the evaluation path; provenance through policy hash, source fingerprint,
run IDs, configuration IDs and per-case simulator hash. The evaluation API is never
registered as an investigator tool.

## 8. Restricted source-patch review (`nautilus/v6/patch.py`, static only)

An earlier draft of this milestone ran an approved diff in a subprocess with rlimits and
an injected denial guard. That execution path has been **removed**, because it added
attack surface and contradicted the project's no-arbitrary-code-execution claim without
ever providing certified isolation (it had no kernel namespace). The module now imports
only `ast`, `pathlib` and `re`, and a test parses the module to assert exactly that, that
no `eval`/`exec`/`compile` call exists, and that no runner attribute exists to call.

What remains is static review of one approved target: `command` in
`nautilus/v6/controller_variant.py`, a module the trusted simulator never imports and
whose default law is unit-tested for exact numerical equivalence with
`nautilus.simulator.command`. Diffs are rejected if they touch any other path, add a
second region, exceed 40 added lines / 4,000 bytes, contain imports, sockets,
subprocesses, `eval`/`exec`, dunder access or filesystem calls, or remove the actuator
bound. Structural checks re-parse the patched module and verify the single target
function, an unchanged fixed signature, the retained `max_thrust` bound, bounded
returned commands, the triple return contract and unchanged imports. Nothing is written
to disk and nothing is executed.

The artifact cannot represent an executed or certified patch: the allowed states are
`not_attempted`, `review_only` and `unavailable`, and any `certified: true` is rejected
by both the Python validator and the browser validator. Execution is reported as
unavailable rather than claimed. The reviewable-diff path is therefore the only
supported one, and it is not part of the demo narrative.

## 9. Workbench integration

`frontend/src/control-lab.ts` validates `nautilus.control-lab-recommendation.v1`
structurally and cross-field (scope wording, baseline-consistent differences inside
declared bounds, proposal/difference agreement, decision equality with the host rule,
required human review, impossible patch certification, and rejection of any executed
patch state) and renders the Control Lab
panel: current policy values, proposed change with reason and expected effect,
baseline/candidate aggregates, per-scenario robustness, every declared gate, unresolved
risks, human-review status, patch status and the configuration-diff download. The
artifact loads standalone or through **Open investigation files**
(`workbench.ts` accepts the schema as the `controlLab` companion).

Compare in 3D remains bound to the existing validated baseline/candidate export pair;
the panel never invents trajectories, grants approval or executes a patch.

## 10. Final output

`nautilus.control-lab-recommendation.v1` records: investigation ID, public evidence
references, controller identity and fingerprint, baseline configuration, the validated
proposal, exact approved differences with units, evaluation conditions (suite, matched
conditions, budgets, acceptance rule, rubric), baseline and candidate aggregates,
per-case robustness with gates, unresolved risks, the host decision plus model
recommendation and agreement, human-review status, patch record, limitations and the
fixed non-deployment scope. Hashes are canonical SHA-256; `export_artifact` writes
`control-lab.json` and `configuration-diff.json` outside the source tree.

Demo artifact for the run above:
`fbf36a9d4f6cfb98e1e420a992be080e22669ee1e6c066bf87032e14d3ec1578`
(approved difference `lookahead_m 7.0 → 3.0 m`).

## 11. Testing

- Full Python suite: **497 passed** (446 existing on V5 + 51 V6 tests).
- Frontend: **66 tests across 13 files passed**; `tsc --noEmit && vite build` succeeds
  (the pre-existing >500 kB replay-chunk advisory remains).
- Simulator/evaluator diff against V5: empty.

Coverage added: policy contract and tampering; bounds enforcement including booleans,
NaN, infinity and unknown parameters; no-op equivalence; matched seeds/physics against a
direct `simulate` call; instrumentation arithmetic; paired differences; determinism;
permanent regression retention; every acceptance gate individually rejecting; the
mean-improves/worst-worsens anti-pattern; completion, saturation and effort regressions;
failed-case accounting without invented metrics; screening restricted to two cases and
the exposure record accounting for all seven; bounded search and no-admissible-candidate
behaviour; proposal schema closure and metric injection; host budget and authorization;
out-of-order evaluation followed by `finish()`; model/host disagreement; privacy of truth
and seeds; artifact tampering, scope, human review, held-out and certification rules;
exporter round-trip; patch scope/token/size/context/signature/bound rejection; the
absence of any execution machinery in the patch module; default variant equivalence with
the trusted command law; frontend validation, markup, qualification display and diff
export.

## 12. Diagnosis-pool status (V4 catalog, not V6)

The concern that the 60–100 case pool and multi-cause faults were never built does not
hold, and the correction matters for planning. `nautilus/v4/catalog.py` already generates
them and is covered by existing tests:

- `reserve(..., full=False)` plans **60** cases (`full=True` plans 100, generating 88
  after strata G and K are explicitly excluded as unsupported).
- Eight strata exist (A, B, C, D, E, F, H, J); multi-cause faults are compositional
  pairs via `PAIRS`/`compose`, not just concatenated settings.
- Verified by direct generation: `V4D027` → truth `['lateral_current',
  'port_degradation']`, `V4D045` → truth `['lateral_current', 'heading_bias']`, both
  representable, gated and classified `operationally_distinguishable`.
- Gate failures are retained, never resampled, and scoring uses exact cause sets with
  paired statistics.

What does not exist is the **executed end-to-end diagnostic study**: a 60-case run with
two policy arms, checkpoints and aggregate statistics has not been performed, and V6 is
about control-policy improvement, not diagnostic accuracy. It is also not feasible in the
remaining time: each case runs a full bounded V4 laboratory loop per policy arm, so 60
cases × 2 arms is an hours-scale private run, and its results would need their own
review and report. Recommendation: keep it as the top roadmap item (run the 60-case
study with both policy arms and publish the paired result), and do not claim diagnostic
accuracy anywhere in this submission.

## What is not claimed

- No physical repair, deployment, safety certificate or generalization beyond the seven
  development cases; the decision is accepted *on the development suite*.
- No held-out evaluation: two of the seven cases screen selection, and both the artifact
  and the UI now say so.
- No live Muse request in this milestone; the model phase is orchestrated and tested
  with fake responses only. Running one needs a provider key and explicit authorization.
- No comparison against external controllers.
- No patch execution at all: the subprocess runner was removed, only static review
  remains, and no patch can be recorded as executed or certified.
- The frontend panel was validated by unit tests, TypeScript and the production build;
  it was not exercised in a real browser session in this environment.
