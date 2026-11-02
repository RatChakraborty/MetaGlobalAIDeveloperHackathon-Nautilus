# V3 development protocol — safety, planning and one critic

This is development work, not a new final holdout or an accuracy claim. Base source:
`3344254f2e23a379c45f8e1e97e80674ba11fe96`. The original Phase D protocol/report
and evaluator are unchanged. Reproduce the frozen Phase D evaluation from that
commit; its production source guard deliberately rejects a V3 source tree.

## Software contracts

`nautilus.muse_v3.make_lab` defaults to enforced safety. `Flags.legacy()` explicitly
selects all features off and advisory research behavior. The original runner remains
callable without V3. Four laboratory signatures and numerical algorithms are retained.
Only finalization validation is extracted into a nonmutating shared method.

Feature flags: `risk_aware_planning`, `enforced_experiment_safety`, `critic_enabled`,
`prediction_audit_enabled`. All flags, safety mode, model settings and budgets are
recorded in the original provenance and an additional hash-linked V3 sidecar.

Safety values remain corridor 1.5 m, predictive 1.1 m, guard .9 m, tail 2 s.
The original full fifteen-case uncertainty screen is used for the exact parameters,
both at the laboratory boundary and again in the backend. Predictive rejection
creates a safety event, consumes no experiment/simulation budget and creates no
observation. Host action limits bound repeated rejected requests. No substitution,
override or new actuator program exists. Accepted experiments still run the original
monitor and drift tail; zero commands are not verified stopping or containment.

## Bounded candidate grid and planner

Before scenario results, reserve a finite grid of 36 candidates: six existing
families × durations {4,6} s × levels {0,2,4} N. Phase is half the duration.
Thrust-step/ramp use the level as amplitude; coast-down adds differential level/4;
differential-step uses level as cruise and level/4 differential; heading-response
uses level cruise and .1 rad target; cable-follow uses max(.25,level) N cruise.
Every request goes through the existing `parse_trial` envelope. No bounds are widened.
For feedback-controlled families, the declared cruise level is not the maximum
realized actuator command: the original controller can generate larger moments.
The exact parameters and complete screens are retained privately for audit.

Signed predictive margin is 1.1 − ensemble maximum observed |y| − .14 m.
The original screen simulates the existing guard/tail policy, not an unguarded
trajectory. Its ensemble is nominal; signed ±.65 m/s current; signed ±.5 rad bias;
individual .3 port/starboard efficiency; four individual drag multipliers 3;
and four combinations of signed current/bias with .3 port efficiency, lag1.2 s,
dead zone6 N and drag .9. It is a finite stress screen, not a reachable-set proof.

Forecast only current, converged singleton fits with exact current epoch references,
no bound hits and max physical/command WRMS≤2. Keep up to four score-gap≤6 competitors.
Fewer than two fits or negligible separation makes discrimination unavailable.
Public fit records alone enter the planner; no backend/case truth is passed.
Each model uses the existing forward simulator with zero sensor noise, zero reset
and aligned .05 s times. Compare y, wrapped heading, yaw rate and requested port/starboard
commands, scaled by {.035 m,.004 rad,.003 rad/s,.05 N,.05 N}. These are declared
noise/command scales, not calibrated predictive uncertainty. Report all pairwise
normalized RMS distances, their minimum and mean. Missing speed/x, confounding,
model mismatch, residual correlations and incomplete registry coverage remain.

Only original-screen-accepted, experiment/time-budget-eligible candidates with
available nonzero separation receive utility = minimum separation − .01×duration.
Return at most three recommended IDs. Safety is a hard eligibility condition,
not a penalty. At most four planning passes, 36 candidates/pass and four model
forecasts/candidate; repeated identical fits reuse the same context. Screen results
for this fixed grid are cached privately within the trusted process; execution
always reruns the authoritative screen. No fifth tool is added. If the grid has
no feasible candidate, the menu recommends none: use passive fits or abstain.
Do not infer that all continuous-envelope maneuvers have been exhaustively ruled out.

## One pending-finalization critic

The first valid model `finalize` is validated without closing the laboratory. Its
exact proposal is preserved in trusted pending state and the V3 event chain. A
separate invocation of `muse-wonder-1.0`, low effort, receives a public allowlisted
packet: pending proposal, selected fit and up to three strongest alternatives,
residual/bound/epoch evidence, actual safety warnings and remaining budgets.
No backend, raw ledger narratives, tools, secrets, private scenario metadata or
hidden reasoning enter this packet.

The critic has an independent Responses conversation (`previous_response_id=None`),
`tools=[]`, one request, zero retries, 2048 output tokens, ≤60 s timeout and ≤15000
serialized UTF-8 packet bytes. There is no verified tokenizer; this is a byte cap,
not an asserted 15000-token provider cap. Instructions/envelope add input overhead.
It returns text JSON validated by a closed bounded schema, not an assumed unsupported
provider-native JSON-schema option. Severity/recommendation are enums; concern arrays,
text lengths and actual observation references are checked. Raw model reasoning and
request headers are not recorded.

The actual first tool outcome is `pending_critic`, `finalized:false`, with the review
and its hash. This is a deferred operation, not a fabricated completed diagnosis.
The normal investigator conversation receives that outcome for its original call ID
and preceding response ID. It gets at most two follow-up requests, within the original
twelve-request/action/token/deadline ceiling. It must explicitly include
`critic:<review hash>` plus a substantive-length response in its subsequent finalize
limitations; it may retain, qualify, revise or abstain. No extra numerical budget is
granted. A missing/invalid review stops inference and produces explicit critic-failure
provenance and host abstention. The laboratory never closes and reopens.

The host verifies linkage and response presence, not the scientific adequacy of a
natural-language rebuttal. A high-severity judgment is not certified truth or a
permission to override safety. Review failure, budget exhaustion and voluntary
abstention have distinct provenance. Propose finalization early enough to leave a
follow-up investigator request; exhausting twelve requests before response yields a
host abstention rather than an unreviewed model conclusion.

## Prediction audit

Where two eligible fits and a predictive-accepted requested experiment exist, record
both numerical reset trajectories before execution, with candidate parameters and
epoch references. After execution compare only time-aligned pre-guard samples.
A leading-minus-alternative RMS gap beyond one normalized unit gives descriptive
support/contradiction; otherwise inconclusive. No valid aligned prefix means untestable.
The original prediction stays unchanged. This heuristic is not validated information
gain, likelihood or physical causal confirmation. With an empty feasible grid there
is no demonstrated safe predict–test–compare cycle.

## Twenty-four development cases and comparisons

The private immutable reservation precedes generation. Source `evaluate_v3.py` fixes
six strata of four, with no result-dependent replacement:

- nominal/subtle: two nominal, signed small current;
- current: signed ordinary and small current;
- thruster: port/starboard ordinary and subtle degradation;
- sensor/controller: signed bias, heading gain, lookahead;
- compound: current+port, current+starboard, signed current+bias;
- mismatch/ambiguity: joint lag/dead zone twice, common thrust loss+uniform drag,
  near-confounded small current+bias.

Fresh private seeds above 2^54 are disjoint from the prior Phase D reservation range.
All 24 are development cases and may not later be advertised as untouched holdouts.
Initial public observations, declarations and noise are identical within policy pairs;
mutable laboratories are independent. All mechanism values/answers stay private.
There is no independently certified correct-abstention subset.

Complete truth-set equality is exact only for sixteen representable singleton/nominal
cases; eight compound/misspecified cases get constituent and family scores separately.
All attempted cases remain completion/safety denominators. Nonabstaining wrong
singleton diagnoses, partial incomplete compound claims, tentative/supported claims
and abstentions must be reported separately. No post-hoc identifiable subset.

Prepare A legacy/advisory/no critic; B planning+enforced/no critic; C legacy+critic/
advisory; D full V3. Planning is an additional changed factor in B/D, not a pure
critic effect. Test component ablations offline. A future performance ablation must
also compare planning off/on at fixed safety/critic settings. Current offline numerical
baselines are existing matched fixed advisory and a first-safe-grid-then-passive fixed
policy, not live Muse A/D. They cannot establish critic efficacy.

## Pilot admission and exposure

At most six predeclared IDs (first of each stratum), never chosen by results. No
repeated legacy campaign or remaining eighteen-case live sweep is authorized here.
Before any future launch, freeze exact source/configuration and perform a new spending
admission check; checkpoint starts before inference and never repeat completed or
uncertain starts. Stop on provider failure, unexpected usage or implementation defect.

Per case: 12 investigator requests/actions, 4096 output/request, 32768 investigator
output total, 350000 measured investigator input soft stop, fits8/starts16, experiment1,
16 simulated seconds including enforced tail, zero retries, 60 s timeout and 600 s
investigator deadline (critic work included). One critic request/2048 output is
separate; two follow-up investigator requests are included in the twelve, not extra.

Six-case maximum request/output exposure: 72 investigator +6 critic =78 requests;
196608 investigator +12288 critic =208896 output tokens. Reasoning is included in
output; cached input is included in input. Measured investigator input soft thresholds
sum to 2100000, but the last accepted response of each case may overshoot. Critic packets
sum to at most90000 serialized bytes, plus six instruction/envelope overheads. These
are not a verified hard aggregate input-token ceiling. Without a verified tokenizer,
provider context bound or reliable tariff, a conservative maximum total input-token
charge cannot currently be established. The $8 objective is not enforceable from the
credit balance. Under the user's section14 stop condition, do not launch now; request
verified pricing/context limits or a revised explicit token/overshoot authorization.
