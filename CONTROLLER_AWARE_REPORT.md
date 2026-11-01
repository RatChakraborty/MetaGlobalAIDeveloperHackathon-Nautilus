# Controller-aware foundation

Built from main `1937d2631fcaf167ff5470db497d719770d38471` (merged PR #3) on
`feature/controller-intelligence`. No merge, deployment, dataset publication,
Muse client or reasoning loop is included. The implementation is staged locally; no feature commit or remote branch was
created. Automatic approval review blocked the GitHub tree upload, citing missing
branch-specific commit/push approval. No alternate upload route was attempted.
The complete source-only patch is the review checkpoint.

## Source and context

The allowlist reads only `nautilus/simulator.py` and exports bounded excerpts of
`Controller`, `command`, `experiment_command` and `wrap_angle`. A pinned AST
analyzer verifies their known structure; changed/unsupported code yields unknown
facts and no excerpts or insights. Comments cannot change the allowlist or rules.
Approved source excerpts are untrusted task data, not agent instructions.

Verified in that scope: atan2 cross-track/lookahead guidance, target override,
desired-heading clipping, wrapped heading error, heading-P/yaw-rate-D feedback,
differential allocation and command clipping. Accumulated integral state, measured
force/surge feedback and six-DOF control are absent within the inspected path.
Disturbance rejection and physical cause remain unverified. Lack of integral state
alone does not establish persistent offset or explain this development failure.

Source excerpt SHA-256:
`3893f25b388f458edc36eeef9d2b7cb4dd58eaa412d4a15c449359eb7ddf9901`.
Exact approved excerpts refer to revision `1937d2631fcaf167ff5470db497d719770d38471`;
changed comments have a different fingerprint and no claimed source revision.
Simulator source SHA-256 remains
`c4f5035d81bc51778ba0447b794541af0d6cb49c3da135742a8f9d1c821ef074`.

`nautilus.controller-context.v1` is closed, bounded and JSON-validated. It includes
identity, source, declared settings with units/bounds, interface, structural facts,
qualified insights, unknowns and a canonical hash. Learned-policy metadata has an
optional validated contract; no weights, runtime, normalization or learned rollouts
are invented. Only the classical source has verified structural support.

Trusted host use:

```python
context = build_controller_context(approved_declared_controller)
initialize_controller_context(laboratory, context)
snapshot = build_investigator_context(laboratory)
```

The snapshot combines approved context, public telemetry/history, public hypothesis
registry, experiment parameter menu, budgets, schemas and safety limits. It never
serializes the backend. Initialization appends one hash-chained `controller_context`
event before investigation actions, containing a canonical context and provenance
reference. Historical events are never changed. The four tools and their budgets
are unchanged; the configuration evaluator is not an investigator capability.
Declared and actual settings need not agree. Tests deliberately differ them and
retain actual settings only on the privileged simulation side. Telemetry can carry
physical consequences of hidden settings; isolation does not mean those settings
are scientifically unidentifiable.

## Matched development measurements

`evaluate_configuration(DevelopmentScenario(...), approved_baseline, changes)`
accepts only lookahead, heading Kp/Kd and cruise thrust. Bounds are respectively
2–20 m, 5–80 N*m/rad, 0–80 N*m/(rad/s), and 0–45 N. Runs are bounded to a
120 s cap and 0.02–0.2 s steps with the declared 45 N action limit. Other simulator
inputs remain trusted and matched: vehicle, physical disturbance, initial zero
state, actuator model, geometry, duration cap, timestep, noise settings and seed.
Different completion times may consume different-length prefixes of the same
noise stream. Metrics use recorded outputs; tracking/completion truth is explicitly
visualization-only. Counts are sampled counts, not continuous breach duration.

Before execution, two alternatives were fixed: lookahead 3 m and 14 m versus 7 m.
No parameter search or held-out data was used. All six outcomes are retained.
The original retained development disturbance is compound, not a pure-current
experiment. Its baseline exactly reproduces every original truth and observation
sample. Injected values remain private. Two fresh development scenarios isolate
positive/negative lateral-current disturbance; their generation inputs remain in
the private review environment. These are development measurements, not benchmarks.

| Scenario | Lookahead (m) | RMS (m) | Max abs(y) (m) | Outside samples / total | Outside fraction | End / elapsed (s) |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| retained-development-disturbance | 7 | 2.677070 | 2.810649 | 1900 / 2001 | 0.949525 | capped / 100.000 |
| retained-development-disturbance | 3 | 1.191200 | 1.370127 | 0 / 2001 | 0.000000 | capped / 100.000 |
| retained-development-disturbance | 14 | 5.022044 | 5.607786 | 1905 / 2001 | 0.952024 | capped / 100.000 |
| fresh-current-positive | 7 | 2.441857 | 2.561575 | 1613 / 1708 | 0.944379 | complete / 85.348 |
| fresh-current-positive | 3 | 1.085822 | 1.325771 | 0 / 1716 | 0.000000 | complete / 85.716 |
| fresh-current-positive | 14 | 4.595447 | 5.113929 | 1607 / 1697 | 0.946965 | complete / 84.799 |
| fresh-current-negative | 7 | 2.442906 | 2.566941 | 1614 / 1708 | 0.944965 | complete / 85.349 |
| fresh-current-negative | 3 | 1.086931 | 1.327769 | 0 / 1716 | 0.000000 | complete / 85.718 |
| fresh-current-negative | 14 | 4.596372 | 5.116582 | 1607 / 1697 | 0.946965 | complete / 84.800 |

All runs have zero commanded saturation fraction; this says nothing about measured
actual thrust. In the retained case, 3 m reduces RMS by 1.485870 m and removes
sampled breaches but still fails to complete within 100 s. The 14 m candidate
regresses. Fresh positive/negative cases have the same direction of tracking change;
3 m completion is about 0.37 s slower than baseline. At 14 m, fewer outside samples
in shorter runs do not indicate improvement: outside fractions and RMS increase.
These observations do not verify repairs or generalize beyond these conditions.

Approved configuration fingerprints (baseline, 3 m, 14 m):

- 7 m: `adda0ae62a6391e69070e48939412684cae58824cff094eae654c89d17c07122`
- 3 m: `3add7582fb2e72460e20d26ed433081c573601bca3948f29e735855a81b68feb`
- 14 m: `9769d71ba606299782d82f47049f8f0aa9ed8391116fecd0aabe8fbcee76b8f9`

Private comparison files retain run IDs, trajectory hashes, metrics, differences
and observation/visualization references for every run. Regeneration requires the
retained private scenario inputs; public source does not disclose them. Behavior
probes and synthetic unit scenarios are independently reproducible from tests.

## Export and replay

`export_configuration_evaluation` writes separate baseline/candidate public and
visualization files plus a comparison summary outside the repository. Public v2
adds only validated controller provenance to the unchanged six-channel ledger.
Visualization v2 adds approved controller identity/configuration, never private
actual settings, forces or hidden plant metadata. Historical v1 remains supported.
Export checks observations and trajectory fingerprints before serialization.

The Trajectory inspector shows identities, source/configuration fingerprints,
units and approved differences, and `Controller not recorded` for old records.
The existing comparison, recorded geometry, interpolation, endpoint hold, cameras
and underwater renderer remain intact. Public provenance must match visualization
metadata. All six pairs imported through the real Python-to-TypeScript path:
21,662 poses across 12 exports, with exact timestamp alignment. Browser QA confirmed
the 3 m candidate at 100 s within the corridor and the original reference outside;
identities and 7-to-3 m difference were visible. GPU is unavailable: SVG fallback
worked; hardware WebGL2 appearance/performance remains unverified.

## Verification and limits

- Complete Python suite: 224 passed (192 existing, 32 new); no assertions weakened.
- Frontend: 23 passed (19 existing, 4 new); TypeScript and repository-base build pass.
- Pinned default 2 s simulation regression and all four configuration-change paths pass.
- Source allowlist, unsupported AST, directive-comment containment, JSON/hash/schema,
  declared/actual mismatch, sanitized errors, private-backend exclusion and ledger
  continuity tests pass. This is not model-level prompt-injection certification.
- Simulator, fitter, laboratory, tools, safety, baseline policies and frozen protocol
  sources remain unchanged. No historical manifest/fingerprint is rewritten.
- Production output contains no JSON data; font notices remain. Dependencies used
  the preserved environment; a clean network install and GitHub CI are not claimed.
  The existing large replay-chunk warning remains.

The optional runtime controller adapter is deferred to preserve the simulation
kernel exactly. `ADAPTER_CONTRACT` specifies named observations and N-valued bounded
actions, explicit host-owned state, finite validation, trusted runtime restrictions
and future policy provenance; tests check its declared interface. No RL runtime,
new controller law, new physics, repair verifier or new held-out pool is added.

Future evaluation must either give comparable declared information to all relevant
investigators or label a Muse-with/without-context ablation. Configuration studies
are separate from diagnosis evaluation and baseline tool budgets. No claim of
improved diagnostic accuracy follows from source access. The next Muse branch must
add protected inference and versioned missing usage/provenance fields separately.

## Source inventory

- `CONTROLLER_AWARE_REPORT.md`
- `MUSE_LABORATORY_CONTRACT.md`
- `PRE_MUSE_INTERFACE_CONTRACT.md`
- `README.md`
- `frontend/README.md`
- `frontend/export_records.py`
- `frontend/src/controller.ts`
- `frontend/src/demo.ts`
- `frontend/src/main.ts`
- `frontend/src/records.ts`
- `frontend/src/trajectory.ts`
- `frontend/tests/controller.test.ts`
- `nautilus/controller_context.py`
- `nautilus/configuration_evaluation.py`
- `tests/test_controller_context.py`
- `tests/test_configuration_evaluation.py`

## Host-side evaluation addendum

`ConfigurationEvaluationHost.finish(lab, response)` accepts a host-owned envelope
with `final_decision` (the exact existing finalize arguments) and an optional
`configuration_proposal`: parameter, finite value, rationale, observation evidence
references and optional qualitative expected effect. Only the existing four
configuration parameters/bounds are accepted. Duplicate/unknown JSON fields fail
closed. Malformed envelopes fail before finalization; a semantically invalid
proposal is recorded as rejected only after a valid decision finalizes.

The trusted host chooses scenario, baseline, permitted parameters, authorization
and a separate budget. Execution defaults off, permits at most one attempt, and
never follows abstention automatically. Finalization failure executes nothing.
Attempted comparisons reserve two duration caps; failures consume the attempt and
reservation, with actual runtime unknown. No retry/search or fifth lab tool exists.

The retained lab history ends at its original finalized event. A separate
`nautilus.post-investigation.v1` sidecar anchors one canonical hash-linked event to
that final hash. It records rejected, skipped, failed, improved or non-improved
outcomes, actual comparisons and genuine run references. Improvement means lower
recorded RMS in the stated conditions; other metrics and diagnosis are not certified.
Exception details are excluded. Hashes establish linkage, not trusted authorship.

`export_host_evaluation` validates the anchor, faithfully mirrors the recorded
final conclusion and writes public investigation evidence separately from the
sidecar and visualization files. Truth-derived metrics never enter the lab snapshot
or public observation export. The existing Investigator tab can manually load the
sidecar, show measured metrics, qualifications and recorded filenames/run IDs for
manual Trajectory comparison. Nothing is fetched or executed from those references.
Missing sidecars show unavailable state. Free-text rationale remains untrusted and
requires human review before any publication.

Fresh deterministic mock responses exercised the real fitter, finalization, host
evaluator, exporter and TypeScript validators. In the fixed 20 s host development
conditions, RMS was 1.031616 m at 7 m lookahead, 0.521930 m at 3 m and 1.552121 m
at 14 m. Both comparisons reached the duration cap; neither verifies a repair.
Each charged one attempt and 40 simulated seconds. Abstention and invalid-parameter
responses charged zero and ran nothing. Numerical failure is covered by an explicitly
mocked exception test, not reported as an observed simulator failure. Private inputs
and all generated records remain outside the source tree.

Latest verification: 256 Python tests and 28 frontend tests pass; TypeScript and
production build pass. Tests cover schemas, isolation, genuine references, tampering,
ledger preservation, failures, budgets and unchanged tools. Browser import confirmed
the actual linked metrics and caveats. No GPU acceptance or Muse accuracy claim is
added. Comparative proposal studies require equal host policies and separate budgets;
otherwise label them a separate demonstration, not a fair repair benchmark.

Additional source: `nautilus/host_evaluation.py`, `tests/test_host_evaluation.py`,
`frontend/src/post-evaluation.ts`, `frontend/tests/post-evaluation.test.ts`. Existing
exporter, main UI and contract documentation receive focused integration changes.
The complete source inventory is now 20 files. The foundation checkpoint remains
preserved separately. Remote branch publication still awaits direct branch-specific
approval after the earlier automatic review rejection; no new upload was attempted.
