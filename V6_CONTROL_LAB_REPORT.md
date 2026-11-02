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
on **two** development cases (`nominal`, `current_positive`) only. The other five
robustness cases are never consulted during selection, so the reported suite is not a
tuned set. Every attempt, including regressions, is retained.

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
0.0000/+0.05; mean effort 373.00/434.40. Decision: **accept**.

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

## 8. Restricted source-patch lab (`nautilus/v6/patch.py`)

Feature flag `NAUTILUS_CONTROLLER_PATCH_LAB`, disabled by default. One approved target
only: `command` in `nautilus/v6/controller_variant.py`, an isolated module the trusted
simulator never imports; its default law is unit-tested for exact numerical equivalence
with `nautilus.simulator.command`. Diffs are rejected if they touch any other path, add
a second region, exceed 40 added lines / 4,000 bytes, contain imports, sockets,
subprocesses, `eval`/`exec`, dunder access or filesystem calls, or remove the actuator
bound. Structural checks re-parse the patched module and verify the single target
function, unchanged signature, retained `max_thrust` bound, bounded returned commands,
triple return contract and unchanged imports.

Execution requires the flag **and** a passing sandbox self-test. The runner uses a fresh
process, stripped environment, `RLIMIT_AS` 512 MiB, CPU 10 s, 64 descriptors, 1 MiB file
writes, a wall-clock timeout, a temporary directory and an injected `sitecustomize`
denial guard for sockets, `os.exec`, `os.fork` and `open` outside the evaluation
directory. A harness re-runs the patched function on fixed samples, checks determinism
and the ±45 N actuator bound, and must report that both network and filesystem probes
were blocked.

Measured on this host with the flag enabled: `status: executed`, `certified: false`, all
nine checks passed, and the guard confirmed network and filesystem denial. This is
**best-effort process isolation, not a kernel network namespace**; the artifact keeps
`certified: false`, the patched module never replaces the trusted baseline, and matched
suite regression plus human review are still required. With the flag off (the default)
the lab returns `review_only` with the validated unapplied diff, which is the supported
path.

## 9. Workbench integration

`frontend/src/control-lab.ts` validates `nautilus.control-lab-recommendation.v1`
structurally and cross-field (scope wording, baseline-consistent differences inside
declared bounds, proposal/difference agreement, decision equality with the host rule,
required human review, certified-only executed patches) and renders the Control Lab
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
`4b7b36991fff466ae3a4f9f6ca33ac8f21182fa5b65616a32fadc241f252a0b2`
(approved difference `lookahead_m 7.0 → 3.0 m`).

## 11. Testing

- Full Python suite: **497 passed** (446 existing on V5 + 51 new V6 tests), 141.8 s.
- Frontend: **66 tests across 13 files passed**; `tsc --noEmit && vite build` succeeds
  (the pre-existing >500 kB replay-chunk advisory remains).
- Simulator/evaluator diff against V5: empty.

Coverage added: policy contract and tampering; bounds enforcement including booleans,
NaN, infinity and unknown parameters; no-op equivalence; matched seeds/physics against a
direct `simulate` call; instrumentation arithmetic; paired differences; determinism;
permanent regression retention; every acceptance gate individually rejecting; the
mean-improves/worst-worsens anti-pattern; completion, saturation and effort regressions;
failed-case accounting without invented metrics; screening restricted to two cases;
bounded search and no-admissible-candidate behaviour; proposal schema closure and metric
injection; host budget and authorization; model/host disagreement; privacy of truth and
seeds; artifact tampering, scope, human review and certification rules; exporter
round-trip; patch scope/token/size/context/signature/bound rejection; sandbox
self-test, timeout, guard-failure and out-of-bound output paths; default variant
equivalence with the trusted command law; frontend validation, markup and diff export.

## What is not claimed

- No physical repair, deployment, safety certificate or generalization beyond the seven
  development cases.
- No live Muse request in this milestone; the model phase is orchestrated and tested
  with fake responses only.
- No held-out evaluation and no comparison against external controllers.
- Source-patch isolation is process-level with a denial guard, not a kernel namespace;
  it is reported as uncertified and is off by default.
- The frontend panel was validated by unit tests, TypeScript and the production build;
  no browser session was run in this environment.
