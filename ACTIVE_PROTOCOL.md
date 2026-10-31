# Frozen ambiguity benchmark and bounded investigation

This milestone implements numerical active baselines only. No Muse, dashboard,
extra maneuver adapter or repair-verification claims are included.

## Evidence and reproducibility

`evaluate_active.py freeze` writes an immutable manifest **before** generating
held-out candidates. The manifest records the actual upstream commit, SHA-256
of every algorithm source file, configurations, distributions, all 160 candidate
IDs/seeds, hypotheses/bounds, sensor schema, environment versions, scoring and
decision rules. Run refuses changed source, configuration, runtime or an existing
output destination. Source is uncommitted until human approval, so the source
file hashes, not an invented revision identifier, specify the exact algorithm.

Use single numeric-library threads for freeze and run:

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python evaluate_active.py pilot --output ../active-private/development.json
python evaluate_active.py freeze --output ../active-private/frozen.json
python evaluate_active.py run --manifest ../active-private/frozen.json \
  --output ../active-private/heldout
```

All generated outputs contain private oracle material and must stay outside the
source repository. The CLI refuses in-repository output and never overwrites
existing results. Each case is checkpointed, including failures and unsupported
cases. No resampling, retry-until-20, or filtering by active success is performed.

## Passive protocol

The partial measured-state observer is unchanged. Commands are observed inputs;
measurements correct state only after the prior one-step prediction is scored.
No x, true velocities, hidden states or plant settings enter fitting. Known-zero
reset heading and velocities are required, including for each new experiment.

- Models: nominal, lateral current, port efficiency, starboard efficiency, heading
  bias. Bounds: current [-1,1] m/s, efficiencies [0.1,1], bias [-0.8,0.8] rad.
- Six public channels from `OBSERVATION_FIELDS`; only y, heading and yaw rate are
  scored. Cadence 0.05 s; standard deviations 0.035 m, 0.004 rad, 0.003 rad/s.
- Three deterministic starts, bounded least squares, max_nfev=60 per start.
- Weighted innovation SSE plus k*log(3*N), counting one shared physical parameter
  across all independent reset episodes. Subsequent measurements have the existing
  sqrt(2) approximate innovation scaling; each reset's initial reading does not.
- Adequacy: weighted RMS <=2. Competitive adequate scores: gap <=6.
- Gap six is retained from development as a **heuristic**, not a physical noise
  floor, posterior probability, calibrated likelihood or validated error rate.

Outcomes are mutually exclusive and public-only:

1. Any missing, nonfinite, invalid or nonconverged candidate comparison gives
   `optimization_failure`; failed optimizations cannot manufacture ambiguity.
2. No individually adequate model gives `model_inadequate`.
3. At least two adequate converged candidates within gap six gives `ambiguous`.
4. Otherwise the adequate converged winner is `identified`.

The private evaluator separately labels identified conclusions right or wrong.
Confident errors are not counted as ambiguity. Controller and compound families
are explicitly unsupported. Their passive outputs and errors remain in full-pool
accounting, but are not presented as supported ambiguous benchmark cases.

## Frozen pool

Primary: 100 candidates, seeds 200000..200099, passive window 30 s. Ten-case cycle:
nominal, mismatch control, current, port, starboard, bias, controller,
current+bias, thruster+bias, current. Hard stratum: 60 candidates, seeds
300000..300059, passive window 0.5 s; cycle nominal, mismatch, current, port,
starboard, bias. Hard cases model a short recovered initial log, not worse sensors
or a weaker numerical algorithm. Development seeds are disjoint (20000 and 30000
blocks). The 0.5-second design is motivated by the development pilot, then frozen
before held-out screening. Results must be reported separately by stratum.

Single faults use current_y magnitude uniform [0.3,0.7] with random sign and
current_x uniform [-0.1,0.1]; efficiency uniform [0.25,0.65]; heading-bias magnitude
uniform [0.25,0.55] with random sign. Controller faults have kp uniform [-45,-20].
Compounds use the same independent ranges. Plant-mismatch controls vary lag in
[0,0.3] s, dead zone [0,0.8] N and drag multiplier [0.8,1.2]. These private plant
values are used only in hidden execution, not forecast or fitting.

Operational mission duration remains 100 s at the normal controller settings.
Existing mission failure means not reaching the cable endpoint or exceeding the
inspection corridor. Performance degradation is separate (relative to a matched
nominal run: RMS +0.25 m, max error +0.5 m, or completion delay +5 s). A fault is
not assumed to produce operational failure. Every supported operational failure
with a public ambiguous outcome is retained, regardless of later resolvability.
Nominal/degradation/nonqualifying controls remain in the full-pool accounting.

## Experiments and forward predictions

Only two initially permitted requests: (6 N cruise, 10 s) and (22 N cruise, 20 s).
General request envelope is 2..25 N, 2..30 s. Per investigation: at most two
distinct requests and 30 s total simulated mission time. No arbitrary Python or
plant modification is exposed. These bounds are not a physical safety guarantee.
No additional maneuver is introduced without evidence that one is needed.

Forecasting is a **free-running closed-loop nominal simulation**, using fitted
parameters and declared engineering defaults. It is separate from observer
innovations. Forecasts are never treated as new evidence. Initial t=0 is excluded
from experiment-separation scoring to focus on responses to changed actions.
Predicted separation is worst-pair sensor RMS normalized by sqrt(2*sigma^2+d^2),
where the declared discrepancy envelope is (0.1 m, 0.03 rad, 0.02 rad/s). This
engineering envelope and separation threshold two are uncalibrated heuristics.
Scores below two are still assessed empirically rather than assumed impossible.

The greedy policy maximizes worst-pair predicted separation; ties follow library
order. Fixed and independently seeded random policies use the same engine, data,
request library, reset assumptions, backend and budgets. Random policy seeds are
independent of generation seeds. Equal per-request sensor seeds across policies
provide common random numbers; different experiments get independent noise.
Repeated requests within a trial are rejected. Every policy still executes each
requested experiment against the hidden plant.

Joint refitting shares fault parameters across the original log and all actually
acquired reset trials. Episodes are never joined into a continuous trajectory.
The complexity penalty is counted once. An evaluator may cache deterministic
fit computations by public evidence hashes; cached future evidence is never
supplied to a policy before it executes the corresponding request.

## Resolution and audit

Offline assessment executes both permitted requests, then evaluates each single
test and their pair (all evidence sets within the same two-test budget). Only the
offline evaluator checks correctness. Categories:

- `resolvable`: at least one assessed evidence set identifies the true family.
- `partially_resolvable`: no correct identification, but a remaining ambiguity
  set is reduced and still contains the true model.
- `not_resolved_by_library`: assessment succeeds numerically without a correct
  identification or qualifying partial reduction.
- `undetermined`: numerical or model-adequacy failure leaves assessment inconclusive.

These describe finite experiments, not fundamental unidentifiability. Per-case
reports retain predicted separation, all assessed outcomes, confident errors,
parameter errors and policy ledgers. Successful offline assessment does not imply
that a particular planner chose the right test first.

Ledger events contain actual public observations, trace hashes, requests, forecast
scores, diagnosis updates, stop reasons, protocol fingerprint and chained event
hashes. Wall-clock fit timings are excluded from semantic ledger hashes for
reproducibility; total runtime is reported separately. The chain detects edits,
not a malicious party able to rewrite the whole ledger.

Report full counts with denominators, ambiguity rates and Wilson intervals;
stratified rates are descriptive, not population estimates. Active results must
be separated by resolvability class. Appropriate abstention is not a wrong
diagnosis. Demo criteria are applied only after the full frozen run: first retained
resolved case, first retained correct revision of an initial favorite, and first
retained unresolved abstention. Missing categories are reported, not invented.

Muse remains unimplemented. A future Muse comparison must keep the same numerical
engine, observations, permission boundaries, test library and budget. Any benefit
from extra evidence must first be compared with fixed/random and greedy active
baselines, not attributed to Muse.
