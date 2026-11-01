# Supervisor events, exports and command overlays

Base: merged PR #4, main `3afef5b2c4ac317a54af12c813e3e3b1d2e9b02a`.
Target: `feature/supervisor-events-and-exports`. The delivery records publication
status and the resulting commit SHA. No dataset publication or deployment is included.

## Derived records

`nautilus.supervisor` is the authoritative Python deriver. The public companion is
`nautilus.supervisor-events.v1`, bound to run ID, source ledger head and observation
hashes. Each event stores canonical bytes, a stable SHA-256 ID, episode/order/local
time, source channel, rule, supporting value, threshold/units and disclosure.
The original ledger is never modified or rehashed.

Default rules (`nautilus.analysis-thresholds.v1`):

- Observed warning: abs(observed_y_m) >= 1.0 m; re-arm at <= 0.9 m. The first
  sample can enter warning. These are analysis thresholds, not official corridor
  limits or the existing safety guard. Noise can still affect observed crossings.
- Requested-command saturation: abs(command) >= declared limit minus 0.000001 N;
  re-arm below limit minus 0.001 N, independently per channel. Limits come only
  from validated declared controller context. Unknown limits produce no claim.
- Guard intervention: explicit enforced mode, guard_intervened=true,
  stop_reason=observed_guard and an exact recorded guard_time_s sample are required.
  Final timestamps, predictive warnings and advisory triggers are insufficient.
  The label does not assert that physical vehicle motion stopped.

Truth entries use separate `nautilus.visualization-events.v1` records: abs(recorded
true y) > recorded corridor half-width, once per outside entry. They include the
canonical allowed pose/reference projection for exact provenance checks and never
enter the public summary, investigator view, report or numerical observations.
Hashes establish integrity relative to retained sources, not authentic authorship.

Each episode retains its reset clock and observation hash. Optional visualization
v3 adds an explicit episode_ref; v1/v2 remain supported. Legacy multi-episode
visualizations are ambiguous for new command/event overlays and fail closed there.
The Python exporter can write companions and an explicitly episode-bound file.
`public_event_summary` is ready for trusted-host use, but these summaries are not
independent evidence. No Muse connection or budget change is made. Browser imports
verify fields, hashes, source samples, rule conditions, scope and episode binding;
Python regeneration additionally verifies full derivation completeness.

## Downloads

The browser revalidates public investigation, optional host sidecar and public
supervisor companion before enabling native Blob download links. There is one
deterministic TypeScript report generator, with no LLM or network requirement.
`investigation_report.md` includes available public episode summaries, fit scores,
convergence, residual/identifiability information, execution/safety records, public
events, recorded conclusion and an actual host comparison when present. Unsupported
or absent evidence is omitted or marked unavailable. Raw controller source and
raw truth coordinates are excluded. Narrative punctuation is entity-encoded as
untrusted data so it cannot inject Markdown structure or remote resources.

`config_diff.json` requires an accepted recorded proposal. It preserves host status,
approved parameter/unit/value, evidence refs and available configuration fingerprints.
Evaluated before-values come from the approved host comparison, never hidden actual
settings. Unevaluated cases may use declared context; missing before-values or
fingerprints are null. No-proposal/rejected cases disable the diff. Operator review
is always required; this is not a deployment-ready hardware parameter file.

## Replay

Signed arrows attach at schematic thruster locations: local forward +x, port at
scene-local z=-0.53 and starboard z=+0.53, matching the existing planar mapping.
They encode recorded requested N: 0.035 display-length units/N, capped at 1.6;
abs(command)<=0.001 hides the arrow. This is a graphical scale, not a force model.
Commands are piecewise-held from the most recent logged sample, as in the simulator's
sample-then-integrate loop. They are never extrapolated beyond the recorded clock.
Primary/reference bindings are separate. Geometry is reused during updates and
owned resources are released with the existing scene disposal. The overlay defaults
off and preserves vehicle motion, cameras, effects and lateral exaggeration.

A compact adjacent marker strip seeks exact recorded times. Public observed
warnings and visualization-only breaches carry different labels. A later experiment
cannot place its reset-time event on the initial trajectory. Mismatched selected
episodes hide the overlay; ambiguous legacy files never synthesize commands.

## Actual acceptance and verification

The retained genuine development disturbance produced one observed warning at
3.55 s and one separate truth-breach entry at 5.05 s. At 3.55 s the truth cross-track
position was about 0.993 m, demonstrating why an observed warning is not a true
corridor breach. At 5.05 s it was about 1.506 m. The browser sought both markers and
showed held port/starboard commands 10.740/15.260 N at 5.05 s. Both arrow colors
rendered through SVG; toggles, free camera and remount preserved one renderer.
One sampled SVG draw was 45.30 ms; this is not an FPS benchmark or GPU acceptance.
There was no actual guard stop in this recording. An actual enforced simulation
fixture verifies guard handling; advisory and duration-cap negative fixtures pass.

The retained genuine host comparison enabled a 7-to-3 m lookahead diff and a
report containing the actual tentative conclusion and measured comparison. JSON
was downloaded and byte-compared successfully. The cloud browser repeatedly timed
out for Markdown download events, including native links; that browser acceptance
remains unverified. Actual Markdown bytes were generated and checked from the
validated records, and native-link Blob content/disposal is unit tested. No claim
of a successful Markdown browser download is made.

- Complete Python suite: 269 passed (256 previous plus 13 new), no skips.
- Complete frontend suite: 39 passed (28 previous plus 11 new).
- TypeScript and repository-base production build pass; existing large replay-chunk
  warning remains. Hardware WebGL2, GPU memory and hardware frame rate are unverified.
- Tests cover signs, thresholds/re-arm, missing limits, real guard metadata, reset
  episodes, truth isolation, tampering, Python-to-TypeScript event-ID parity, genuine
  simulator exports, all host result states, safe reports, units, missing values,
  Blob links, command alignment, reference separation and scene resource disposal.
- Simulator/controller equations, fit engine, four tools, budgets, safety policies,
  original tests and frozen protocols are unchanged. Private demonstration files,
  raw scenarios, credentials, traces, caches and build output stay outside the commit.

## Source inventory

- `SUPERVISOR_AND_EXPORT_REPORT.md`
- `MUSE_LABORATORY_CONTRACT.md`
- `frontend/README.md`
- `frontend/export_records.py`
- `frontend/src/command-arrows.ts`
- `frontend/src/investigation-exports.ts`
- `frontend/src/main.ts`
- `frontend/src/records.ts`
- `frontend/src/replay-math.ts`
- `frontend/src/replay.ts`
- `frontend/src/supervisor.ts`
- `frontend/src/trajectory.ts`
- `frontend/tests/command-arrows.test.ts`
- `frontend/tests/investigation-exports.test.ts`
- `frontend/tests/supervisor.test.ts`
- `nautilus/supervisor.py`
- `tests/test_supervisor.py`
- `tests/test_supervisor_exports.py`
