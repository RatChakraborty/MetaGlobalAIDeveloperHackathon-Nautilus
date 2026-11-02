# Muse evaluation protocol v1 — prospective simulator holdout

This is a small, balanced, predeclared simulation comparison, not a field-robot
reliability certification. Candidate: `340d1c12e1f39252a84b4aaae59dd149b1d2b93b`,
`muse-wonder-1.0`, Responses endpoint, low effort, auto tool choice, sequential calls.
Candidate Python files, full prompt, four strict declarations, numerical/experimental
code, controller context, evaluator/scoring code, this protocol and numerical runtime
are fingerprinted in the private immutable manifest. No candidate changes are allowed.

## Independence and selection

V1 seeds around 100000/200000/300000 and V2 900000-series cases are exposed historical
resources, explicitly documented by `DRAFT_RELIABILITY_PROTOCOL_V3.md`; they are
excluded. Development programs reserve roughly 1000, 20000/30000, 600000-series,
1100000–1200100 and small unit-test ranges. New evaluator tests use an explicitly separate
2^40 fixture block; real inference rejects fixture manifests and reserves above 2^52. Private manifest discovery in the current
workspace found no additional historical frozen manifests. No old oracle result was
opened or reused. Auditing cannot establish facts about inaccessible external runs.

Before generating any held-out physical case, reserve twelve new private generation
seeds in an entropy-selected block above 2^52; freeze their order and case IDs. Do not
publish these seeds. Shuffle the following fixed mix once before generation: two
nominal, two signed lateral-current, port and starboard degradation, two signed
heading biases, simultaneous current+bias and current+port, one controller-gain
change, and one simultaneous actuator-lag/dead-zone plant mismatch. No resampling,
mission-failure qualification or outcome-based exclusions. This is a prospective
holdout relative to the audited repository/workspace, not a guarantee of untouched
use outside that scope. Twelve cases, not individual telemetry rows, are the units.

Distributions are fixed in the manifest/evaluator before generation. Pure current
cases change only lateral current, not unmodeled longitudinal current. Nominal uses
the public default plant rather than the historical hidden nuisance plant. Compound
and joint-plant conditions are simultaneous, not ambiguity labels assigned afterward.
They are not fully representable by one singleton template. Controller-gain changes
are representable but actual settings remain private; declared context stays default.
All constructors/strata are validated before the first real request. Unsupported
construction stops the evaluation without resampling or live calls.

## Paired permissions and baseline audit

Each policy gets a new `Laboratory` and `SafeBackend`, identical two-second initial
six-channel observations/noise, default declared controller context, public supervisor
summary for Muse, and the same registry, singleton fitter, actuation bounds and safety.
Initial evidence hashes must agree. Backend case seeds and request hashes give matched
noise when two policies choose exactly the same experiment; different maneuvers are
legitimate interventions, not repeated independent physical cases. Evaluator labels,
private parameters and case IDs/seeds are never put in provider context.

Older `evaluate_active.py` uses legacy tools/protocols; `evaluate_v2.py` uses a different
session/backend, exhaustive initial-fit cache, 64 fits/128 starts and two experiments.
Those outcomes are not reused as direct Muse comparisons. All compared policies here
use the current validated laboratory, no initial fits or privileged fit cache.

Report three policies independently:

1. **fixed_reference:** unchanged existing `DeterministicInvestigator('fixed')`.
   It consumes up to eight registry-order fits, then requests a fixed experiment
   which invalidates them; without fit budget it generally must abstain. This is a
   resource-policy limitation known before holdout, not an outcome-based adjustment.
2. **fixed_matched (main comparator):** a frozen wrapper around that fixed strategy
   requests `LIBRARY[0]` first, then uses its original registry-order fits, numerical
   ranking and finalization. This avoids spending every fit before invalidation.
   It still has the complete registry/menu permission; its policy fits only the first
   eight registry entries. It is explicitly distinct from the unchanged fixed policy.
3. **Muse:** unchanged Phase C prompt/host and four tools, no scripted action choices.

There is no unlimited/exhaustive baseline advantage. Policy-selected hypotheses and
experiments need not match. Main paired differences compare Muse with fixed_matched;
fixed_reference is a transparent additional reference, never silently substituted.
No policy or template order may change based on held-out performance. NumPy
generation uses each frozen private seed; fixed policies have no randomized action
selection. Muse sampling defaults are unchanged and no unsupported provider seed
is supplied; repeated identical model outputs are not guaranteed.

## Frozen resource and safety policy

Per policy: eight fit calls, sixteen starts, one experiment, sixteen simulated seconds,
twelve action attempts, advisory safety, unchanged four finalization/tool signatures.
For Muse: twelve requests, 4096 output tokens/request, 32768 aggregate output including
reasoning, 350000 cumulative measured input soft stop, 1 MB cumulative request JSON,
60-second request timeout, 600-second between-action wall deadline, zero retries and
no configuration evaluation. Full authoritative results/ledger remain on the host;
Phase C lossless observation-array presentation and continuous call-ID linkage remain.

Advisory risk warnings do not prohibit execution. Record predicted enforced rejection,
observed corridor excursions and actual guard intervention separately. Proposals
not reached by the laboratory screen are counted as unassessed, never called safe. Do not call
advisory excursions contained. No hardware or controller modifications are authorized.

Campaign: at most twelve real Muse cases, 4.2 million cumulative measured input tokens
and 393216 reserved output tokens. Check totals before each new case and reserve the
whole next-case output ceiling. Limit an active case's remaining input threshold by
remaining campaign allowance; an accepted final response can cross a measured-input
soft stop. Start no new case at a reached threshold. Unknown output usage is charged
conservatively by the candidate host. Pricing is unverified in this environment:
use the user-authorized token/request fallback; the $15 estimate target cannot be
enforced or called a guaranteed dollar cap. No credit balance is treated as a budget.
Any provider failure stops further cases; no retry or model switch. Unexpected
technical/integrity defects stop the campaign and require a new versioned protocol.

## Predeclared truth and scoring

Score only after both baseline and Muse sessions are closed. Record physical truth,
representability and observational identifiability separately. There is no independent
identifiability oracle, so do not define an identifiable subset, correct-abstention
score or hindsight resolvability category. Numerical `ambiguous` is descriptive only.

Main physical-finding score uses the existing `v2_models.finding`: a selected fit in
its declared healthy range maps to nominal. Also report exact raw declared labels.
Exact complete mechanism identification requires equality with the whole injected
mechanism set. There are nine representable singleton/nominal cases; two compounds
and the joint-plant case cannot receive complete exact credit from a scalar label.
Constituent identification on those three cases gets separately labeled partial
credit, never complete correctness. Family scoring requires whole-family-set equality;
constituent-family coverage is separate for mixed-family compounds. A supported
prediction outside the actual constituent set is a truth-inconsistent supported claim;
a supported true constituent of a compound is separately incomplete. This does not
establish whether confidence was warranted by public evidence alone.

Record tentative conclusions, voluntary scientific abstentions, host terminations,
provider failures, evidence-ref validity, fitting/convergence/saturation, hypotheses,
experiments/time, safety, measured tokens/cached/reasoning counters and latency.
Abstention has no binary correct/incorrect label absent an identifiability reference.
Conditional numerical experiment discrimination is a change in competitive-set size
(gap <=6) on at least two identical template IDs fitted both before and after the
experiment. If that evidence is absent, report unavailable. It is not physical
information gain or a reason to filter cases.

For every policy report all-attempt completion, exact identification yield on nine
representable attempted cases, yield conditional on valid completion, and selective
exactness among non-abstaining representable diagnoses with coverage denominators.
Failures remain in main reliability denominators. Report partial/out-of-registry
outcomes and six strata separately. Use descriptive 95% Wilson intervals for marginal
proportions and paired wins/losses/ties; do not claim statistical superiority from this
purposive n=12 sample or treat trace samples as independent cases.

## Freeze, execution, resume and reporting

Run all offline tests and builds first. Commit harness/protocol before freeze.
`evaluate_muse.py freeze` writes an exclusive private manifest and full-file SHA-256;
its body fingerprint excludes only its own digest. Manifest permissions are read-only,
and hashes detect changes; they are not protection against a privileged rewrite.
`run` validates frozen source/runtime/configuration before generating cases. No prompt,
algorithm, case rule, baseline or scoring change is allowed after freeze. An evaluator
wrapper retains bounded structured tool calls only, never raw provider reasoning.

Each case gets an exclusive started marker before inference and a hashed terminal
checkpoint after closed-ledger validation/scoring. Verified completed cases are skipped
on resume. A started-but-incomplete case blocks automatic resume: preserve partial
records and stop rather than risking duplicate calls or discarding unknown usage.
No completed case may rerun under this manifest. Normal host budget terminations are
terminal outcomes; provider failure halts the campaign. Progress output contains only
opaque case IDs and operational usage until all analysis is frozen.

Private manifests, truth, seeds, original tool outcomes and per-case records stay
outside the checkout. The public report includes all attempted anonymized outcomes,
aggregate/stratified metrics, paired differences, runtime/source/manifest fingerprints,
usage, failure categories and limitations. It omits per-case true/predicted mechanism
labels, traces, private parameters, seeds and keys. Do not selectively omit unfavorable
cases. Any partial evaluation is explicitly partial; report planned, started, terminal
pairs and valid Muse completions separately. No dashboard redesign, repair evaluation,
deployment or dataset publication is part of this protocol.
