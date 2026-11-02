# Multi-cause diagnosis V4 report

Implemented and offline-tested: versioned physical composition; six whitelisted
joint models; joint observer fitting; residual/sensitivity diagnostics; numerical
support rubric; structured V4 finalization; equal-capability deterministic adapters;
and tool-free critic orchestration with fake providers. **No real V4 Muse or critic
request ran, and no physical attribution calibration or real-model gain is claimed.**

Numerical checkpoint `2d97c4cfabc7a5576d04e943df516f0b463c8695`; release recovery checkpoint `81744fedf5753eaece5dd9aeafe42b306709bdc5`.
Original V1–V3 modules, physics and frozen reports remain unchanged. V4 resides in
`nautilus/v4`; joint fitting defaults off (`joint_enabled=False`) until explicitly
selected by a trusted caller. Historical tools/records remain supported.

## Physics and whitelist

`nautilus.physical-composition.v4` takes one or two validated components. A singleton
returns exactly the historical `configs` behavior; regression tests compare both
configuration objects and actual telemetry for every original registry entry.
Composition updates the existing independent physical fields; it never invents a
new simulator kernel, blindly multiplies efficiencies or permits overlapping causes.
Duplicate components, unapproved pairs, triples and invalid/nonfinite bounds reject.

Six stable IDs use `joint__` plus ordered component IDs: current+port, current+starboard,
current+bias, port+bias, starboard+bias, current+lag. Each declares component parameter
names, units, inherited bounds, composition, method, resource charge and limitations.
No dead-zone/drag extra pair, battery mechanism, time-varying fault or controller
source/policy modification was added.

## Fit, complexity and diagnostics

Both parameters are optimized jointly by bounded SciPy least-squares using historical
`_prepare`, observer `_predict`, actuator model and physics. Default up to two starts,
maximum 40 evaluations/start; explicit bounded testing can set≤80. One joint fit counts
one model call and **two parameter-start units per optimizer start**. Budget fields
report these units; the sidecar separately reports actual optimizer-start count.
Singleton nominal costs zero parameter starts, as historically. All policies receive
the same fit/unit caps and joint registry.

Objective is normalized physical innovations plus public command consistency;
y/heading/yaw scales .035 m/.004 rad/.003 rad/s, command scale .05 N. Complexity score
is SSE+k log(5N), k=2 for a pair, inherited k for singles. This is a predeclared BIC-like
heuristic for correlated innovations, not a calibrated likelihood or probability.
The policy favors the simplest adequate model within score gap6. Sequential residual
policy fits singles first, orders compatible second causes using current residual
structure, then fits the full pair jointly; it never presents a residual-only estimate
as the joint optimum.

Reports contain estimates, bounds, SSE/WRMS, convergence, cost, saturation and references.
A separately versioned sidecar stores exact scaled local Jacobian, singular values,
rank threshold max(1e-8,1e-6×largest singular value), condition, coupled directions and
conditional correlation when full rank. Residual fields include mean, dispersion,
early/late behavior, time slope, lag-one autocorrelation and systematic-bias flags.
Rank-deficient correlation is unavailable, not invented covariance. Provider packets
use explicit compact Jacobian summaries/hashes while full numerical records remain
available locally. Intervention/tail samples are excluded from command-law fitting
under the historical waveform-prefix rule; actual full observations remain recorded.

## Support and multi-cause conclusions

Strong support checks convergence, finite metrics, exact current observation epoch,
valid references, WRMS≤2, no bound saturation, relevant simpler comparisons, delta≥6,
local rank/condition, residual |lag1|<.8, pair |conditional correlation|≤.98 and separation
from other tested alternatives. Untested mechanisms and unavailable independent
confirmation remain explicit limitations; no universal causal identification follows.
`MULTI_CAUSE_SUPPORTED` means this numerical rubric passed. `PARTIAL` requires an
adequate component with its own support checks, and unresolved additional behavior;
`AMBIGUOUS_SET` retains unresolved alternatives. Inadequate fits are labeled separately.

`nautilus.diagnosis.v4` contains a maximum-two cause list, exact current fit estimates,
per-cause evidence status, single/joint/partial/abstain relationship, unresolved sets,
unexplained-residual flag, global qualification and actual evidence references.
Unsupported extra causes or free-text multi-cause claims cannot bypass structured
validation. Strong support with failed mandatory checks is rejected with original
proposal/host assessment preserved separately; confident support cannot also assert
unexplained residuals. Parameter estimates cannot be edited by the model. A partial
single explanation with unresolved alternative sets is permitted. Legacy finalization
continues to work and is not silently reclassified as a multi-cause finding.

## Planning and critic boundaries

Pair-aware forecasts reuse the 36-candidate V3 menu and the original hard screen.
Aligned noiseless public trajectories provide min/mean pairwise separation, explicitly
not information gain. The full menu remains predictively rejected, so Strict is
passive-only. Operator authorization is an independent human decision, not a planner
recommendation or model override.

The four tool names/primary signatures remain. Opt-in schemas extend template values
and add the V4 diagnosis union. A single read-only critic reviews current cause sets,
residual/identifiability diagnostics, simpler/joint alternatives, host rubric, safety
and narrative provenance; its instructions challenge unsupported extra causes.
It has no tools/truth and cannot modify fits. One review, low effort,2048 output tokens,
15000 serialized packet bytes,60 s timeout, zero retries; two investigator follow-ups
are included in the original 12-call budget. No unverified provider-native JSON schema
option or native pause API is assumed. Actual V4 provider schema/retention acceptance
has **not** been live-tested.

The shipped V4 host admits only marked offline fixtures and rejects the real MetaProvider in its tested configuration. Never relabel a real transport as a fixture; a separately reviewed live admission path is still required.
Fake-provider provenance says `offline_fixture_only`; investigator and critic usage
are separate, and reasoning/cached counts are subsets of output/input. Source-bound
checkpoints preserve response/call IDs and refuse uncertain dispatch replay. The V3
critic remains available unchanged as fallback.

## What was demonstrated

- Exact singleton configuration/telemetry compatibility across the old registry.
- Deterministic joint recovery on a known synthetic current+port fixture within the
  predeclared .12 m/s/.2 efficiency test tolerances, full local rank and repeatable score.
- Zero-excitation rank loss and unavailable conditional correlation.
- Joint parameter-start charging, saturation diagnostics, stale/reference checks,
  rejection of unsupported strong classifications and modified fitted estimates.
- Fake-model structured pair finalization, one read-only critic and genuine laboratory
  dispatch/Responses continuation linkage, including suspended human-request outcomes.

These are offline numerical/orchestration results, not a validated physical attribution
accuracy claim or proof that critique improves diagnosis. Full prediction-audit rollout,
calibration, broad negative-current coverage, incomplete-channel fitting and real-model
critic decision quality remain future research. The original V3 prediction audit is
preserved; V4 has conditional forecast helpers rather than a newly validated safe
predict–test–compare loop. Triple/time-varying faults and controller rewriting remain off.
