# Nautilus v2: reduced, development-gated investigation protocol

No Muse, repairs or GUI are implemented. This protocol separates missing physical
models, physical ambiguity, incorrect confidence and observational limitations.
The exposed v1 evaluation is not used for tuning or as v2 validation.

## Preservation and scientific boundary

The v1 worktree, Git metadata, source-only patches, manifests, reports and private
results are preserved in an independent pre-v2 checkpoint. Actual upstream main
is checked before work; the feature branch has the real upstream parent, never
the independent snapshot root 75893b1. No new commit or push is authorized.

Development uses fresh seeds in 600000..606999. Held-out generation is prohibited
until `evaluate_v2.py freeze` writes a manifest containing all algorithm source
hashes, this protocol hash, numerical environment, plans, distributions, registry,
notes, observation schema, experiment menu, scoring and resource budgets.
The manifest is immutable. Changed source or runtime is rejected. A new method
requires a new separately declared evaluation pool. No v1 held-out answers are read.

## Included scope and gates

The legacy five-model passive engine remains unchanged and separately reported.
The extension registry contains actuator lag, thrust dead zone, three axis drag
scales, heading gain, controller lookahead, symmetric thrust efficiency and uniform
hull drag. All singleton implementations reuse simulator equations. Joint compound
templates and arbitrary combinations are unsupported and rejected by the tools.

Common thrust versus uniform drag **fails the development ambiguity gate**: zero
of twenty standard-mission cases have two adequate competitive explanations under
gap six. It is excluded as an ambiguity stratum; the individual physical models
remain tested out-of-family mechanisms. No magnitudes or thresholds were changed
to make that ambiguity family pass. Straight coast-down with no lateral or angular
excitation provides no public y/heading/rate signature and is not a speed sensor.

Lag versus dead zone passes the predeclared development gate: at least12/20
adequate competitive comparisons, median conditional public separation <=1 noise
unit, and at least one permitted experiment with empirical separation >2 units.
Development sensitivity columns, their scaling/cosines and full separation
matrices are reported privately. These are local diagnostics, not Fisher ellipses
or calibrated uncertainty. Controller gain/lookahead changes are identifiable
from requested commands; they are not claimed to be actuator ambiguity.

All included Tier1 physical/capability regression tests pass before context and
held-out evaluation. Compounds (B), all masks/corruptions (E), restore/persist,
adversarial mask assignment, formal Fisher reporting, cost-aware policies and
latent-margin stress strata are **deferred**. Missing measurements or commands
are rejected explicitly; there is no hidden reconstruction, imputation or sensor
schema extension. No speed, displacement or true-state channel was added.

## Physical semantics

`PlantConfig.drag_scale` retains v1 semantics: linear drag only. New axis scales
and `uniform_drag_scale` multiply both linear and quadratic damping coefficients:
`D_linear_i = D0_i * legacy_scale * axis_scale_i * uniform_scale`,
`D_quadratic_i = Q0_i * axis_scale_i * uniform_scale`.
All scales default to one, preserving v1. Common thrust loss uses the same
efficiency on both actual thruster forces, after the existing signed dead zone
and first-order actuator update. No separate competing dynamics implementation
is introduced. Controller faults affect requested commands, not actuator states.

Registry numerical bounds (each template has one parameter):

| Template | Parameter and units | Allowed range | Declared healthy engineering range |
| --- | --- | --- | --- |
| actuator_lag | time constant, s | 0..1.2 | 0..0.25 |
| thrust_deadzone | dead zone, N | 0..6 | 0..0.5 |
| drag_surge/sway/yaw | coefficient multiplier | 0.5..3 | 0.9..1.1 |
| heading_controller_gain | heading gain, N*m/rad | 5..80 | 35..43 |
| controller_lookahead | lookahead, m | 2..20 | 6..8 |
| common_thrust_scale | paired efficiency | 0.2..1 | 0.9..1 |
| uniform_drag_scale | all-coefficient multiplier | 1..3 | 1..1.1 |

Healthy ranges are declared public engineering assumptions, not the injected
plant settings. Selecting a lag/dead-zone model does not itself imply degradation.
The report distinguishes the numerical model label from a `physical_finding`:
an estimate inside the corresponding healthy range is nominal-compatible. Score
rules and raw model ambiguity remain visible; they are not silently collapsed.
Parameter recovery is biased by ordinary unmodeled discrepancies and is reported,
not assumed accurate because the model converges or fits well.

## Observations, fitting and decisions

Initial telemetry is the full first30 seconds at0.05-second cadence, containing
exactly the original six public fields. True velocities, x, private forces, seeds
and fault values never enter the fitting or agent interface. Zero physical heading
and velocities at each reset remain experimental assumptions, not truths inferred
from timestamp zero.

The v2 engine shares one parameter across all independent reset episodes. It
scores public y, heading and yaw-rate one-step innovations, using v1 sensor scales
(0.035 m,0.004 rad,0.003 rad/s) and the same sqrt(2) approximation after each reset
reading. It additionally checks requested-command consistency with the declared
controller/waveform, conditional on the observed sensors, using0.05 N logging
tolerance. This deterministic consistency channel is not an independent noisy
physical sensor or calibrated likelihood.

Ranking: physical innovation SSE + digital command-consistency SSE + k*log(5*N).
Adequacy: **both** physical WRMS and command WRMS must be <=2, avoiding dilution
by zero command residuals. Two deterministic starts, max_nfev40 per start, bounded
least squares. Every candidate comparison must converge. Failed/invalid comparisons
are optimization failure, no adequate candidates means model inadequate, multiple
adequate candidates within gap6 means ambiguity, otherwise identified. Thresholds
are retained as uncalibrated heuristics, not posterior probabilities or a physical
noise floor. Complexity is counted once across reset episodes.

Alongside legacy v1 scores, the same v2 score is also applied to only the original
five templates. This restricted comparison separates new command scoring from
expanded model access. Raw scores from different engines are not likelihood ratios.

## Physical candidate pool

Twenty physical cases, independent seeds900000..900019:

- A:twelve cases: one draw from each of nine extensions, plus three additional
  lag/dead-zone draws under the development-qualified family.
- C:four supported single faults: current, port, starboard and bias.
- D:four controls: two nominal and two ordinary physical-mismatch controls.

B and E have no candidates; they are excluded, not replaced by easier cases.
The suggested120-case full design is reduced explicitly for execution feasibility.
Development workflow cases took83..138seconds each. The preliminary30-case design
with partial active assessment was reduced before freeze to20 cases with complete
active assessment, retaining difficult mechanisms rather than omitting unresolved
development families from active comparisons.
Every planned case is retained, whether it fails, degrades, passes, fits poorly,
is confidently wrong, or cannot be resolved. No target ambiguity count is promised.

Fault distributions are uniform: lag0.3..1.1s, dead zone1..5N, axis scales1.4..2.5,
gain8..20, lookahead11..18m, paired efficiency0.5..0.9, uniform drag1.2..2.0,
current magnitude0.3..0.65m/s, side efficiency0.3..0.6, bias magnitude0.3..0.5rad.
Current/bias signs are seeded independently. Ordinary control plant ranges are
lag0.05..0.25s, dead zone0.1..0.5N and legacy linear-drag multiplier0.95..1.05.
The machine manifest records exact plans, distributions and healthy interpretations.

Operational outcome is determined offline from the complete100-second mission:
failure if endpoint/corridor criteria fail; degradation separately if matched
nominal RMS rises0.25m, max error0.5m, or completion is delayed5s. An injected
parameter is not automatically a failure. No operational label or private answer
is used to decide which models or experiments a policy receives.

## Experiment and capability interface

Seven configurations are available equally: differential steps at4N and1N, excited
coast-down, straight coast-down, differential amplitude ramp, thrust step and
closed-loop heading-response test. The latter actually feeds measured heading
and gyro into steering control. No experiment is called speed hold.

Requests are strict JSON: whitelisted mode and mode-specific numeric arguments.
The reusable capability supports a bounded parameter envelope, but evaluation
sessions enforce exactly the same seven-request menu for every policy. A future
Muse comparison must use that same restriction, or predeclare equally capable
continuous-parameter baselines and a new evaluation pool.
Limits: duration4..16s, common thrust0..20N, differential magnitude<=6N, combined
request<=25N, target heading magnitude<=0.5rad, known-zero reset and0.05s cadence.
An observation-based guard ends a trial when measured |y| exceeds8m; inspection
corridor excursions beyond1.5m and guard stops are reported independently.
This is not a proof of physical spatial safety, particularly with noisy sensors.

The JSON operations are `propose_hypothesis`, `request_experiment`,
`get_fit_report`, and `finalize`. Unknown fields, code, classes, unsupported
combinations, widened bounds, invalid confidence values and forged evidence
references are rejected. Every fit and optimization attempt is budgeted, including
failed attempts. Limits:64 model-fit calls,128 optimization starts, two trials and
32 charged simulated seconds in this evaluation. Experiment duration is charged
conservatively even if the guard ends a trial early. A new experiment invalidates
old fit scores until joint refitting. Final supported claims require current,
adequate numerical evidence and categorical confidence; no probability is accepted.
Ledger events are hash chained and reference actual public observations. They
detect edits, not a malicious replacement of the complete ledger. Python objects
are not security sandboxes; a future model receives only the JSON capability API.

## Policies and model-discovery comparison

Expanded exhaustive fitting visits every allowed model and counts every attempt.
For all20 predeclared cases, fixed, seeded random and greedy policies use identical
expanded fits, sensors, trial menu and budgets. This cohort covers every extension,
all supported single faults, and all controls, including the difficult axis-drag
mechanisms. All candidates are assessed actively regardless of initial outcomes.
The exact cohort indices are recorded before held-out generation. No mechanism
is removed from active assessment because development policies failed to solve it.

Every assessed case gets an initial test even if passive output was identified or
inadequate; this avoids v1's inability to reconsider confident errors. Stop after
that only on a unique adequate raw model identification, otherwise use a second
test. Fixed order begins with the general differential4N test and excited coast.
Random seeds start1000000, separate from generation. Greedy maximizes mean pairwise
noise/discrepancy-normalized forecast separation among adequate converged fits,
with all-converged fallback. This remains a heuristic, not expected posterior
information gain. Same per-request hidden sensor seeds match evidence across
policies; different requests have independent noise.

Forward predictions are free-running nominal closed-loop/waveform simulations,
not observer innovations. The declared discrepancy envelope is(0.1m,0.03rad,
0.02rad/s). Fitted-parameter errors can badly distort forecasts: predicted and
empirical development separation matrices are both retained.

Resolvability concerns the evidence sets actually acquired by these three frozen
policies. At least one correct conclusion means empirically resolvable; a reduced
adequate ambiguity retaining truth is partial; numerical/inadequacy failure can
make assessment undetermined; otherwise it is not resolved by this evaluated
protocol. This is not an exhaustive search of every possible experiment sequence
and never establishes fundamental unidentifiability. Non-active cases are marked
not assessed, not unresolved. All categories and confident errors remain reported.

## Context comparison

There are68 distinct hand-authored templates:56 mechanism hints, eight irrelevant
notes and four directives. Correct and misleading conditions draw from the same
hint banks; their private reliability labels are never tool inputs. The first two
wordings per hint/directive are development-only and the last two held out;
irrelevant banks split first/last four. Text contains no numerical fault values or
public condition identifiers. Misleading hint assignment is a predeclared cyclic
alternative; every fifth misleading note includes a directive. Text is always
untrusted evidence and cannot change permissions, budgets, physical fits or safety.

All twenty physical cases have paired note presentations. Four note presentations
share the exact same public telemetry. Keyword rules and score shift4 are frozen
before held-out presentation. Preferences adjust relative scores only; no model
is removed and convergence/adequacy are not overridden. This is a context/model
preference baseline over exhaustive fits, not a substitute experiment policy.
Active policy comparisons use absent notes to isolate experiment selection.

## Reporting, scope and reproducibility

Report complete physical-pool accounting, strata, outcome types, false positives,
raw model and physical findings, parameter errors by units, fitting attempts,
runtime, experiments/time, observed envelopes, all context conditions and paired
changes. Report descriptive Wilson intervals for binomial proportions. Small,
correlated strata and matched sensor seeds limit population claims. No method,
mask, note or experiment is tuned on v1 or v2 held-out outcomes.

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python develop_v2.py --output ../v2-private/development.json
python evaluate_v2.py dev --output ../v2-private/capabilities.json
python evaluate_v2.py freeze --development ../v2-private/development.json \
  --output ../v2-private/frozen.json
python evaluate_v2.py run --manifest ../v2-private/frozen.json \
  --output ../v2-private/heldout --batch 1
```

Repeat the last command to resume missing planned cases. Existing checkpoints are
hash-validated and never overwritten. Private data, snapshots and reports remain
outside the source repository. All source commits, pushes and merges remain pending
explicit approval. Future Muse comparisons need equivalent tools and new untouched
evaluation cases if prompts or methods are informed by these results.
