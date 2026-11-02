# Nautilus V3 — safety, numerical planning and independent critic

Implemented behind feature flags on the verified Phase D source. **No safe candidate was found in the fixed 36-maneuver grid.** Enforced V3 therefore offers passive diagnosis/abstention here. The 24-case offline numerical comparison completed, but no real Muse pilot ran: maximum input-token exposure and a reliable tariff remain unverified under the requested spending admission rule. There is no claimed Muse or critic accuracy gain.

## Source and preservation

Base: `3344254f2e23a379c45f8e1e97e80674ba11fe96`; branch `feature/safety-active-critic-v3`. Original Phase D protocol, report and evaluator remain unchanged. Historical records were neither recalculated nor reused for V3 tuning. The old investigator remains callable, with all V3 flags off preserving public ledgers and request construction in regression fixtures. Frozen Phase D source fingerprint checks intentionally reject a V3 checkout; use the recorded old commit to reproduce that evaluation.

Full development methodology, distributions, denominators, limits and admission rules are in [V3_DEVELOPMENT_PROTOCOL.md](V3_DEVELOPMENT_PROTOCOL.md). Private reservation body fingerprint: `336df8ffbc4d38c75377555023fe0ac17faa582eba6112b99a0a904b4b7b79ee`. This is fresh development data, not a new final holdout.

## Safety feasibility

The predeclared grid has six existing maneuver families × durations4/6 s × levels0/2/4 N. Phase is half duration, differential level/4, heading target .1 rad, cable-follow minimum cruise .25 N. Every exact parameter set passed the original Trial validator and original fifteen-stress-case screen. Corridor±1.5 m, predictive1.1 m, guard.9 m, tail2 s and uncertainty ensemble were not relaxed.

| Family | Generated | Accepted | Rejected | Signed margin range, m |
|---|---:|---:|---:|---:|
| amplitude_ramp | 6 | 0 | 6 | -1.112517 to -1.111270 |
| cable_follow | 6 | 0 | 6 | -1.274038 to -1.241104 |
| coast_down | 6 | 0 | 6 | -1.151217 to -1.112517 |
| differential_step | 6 | 0 | 6 | -1.133373 to -1.112517 |
| heading_response | 6 | 0 | 6 | -1.315595 to -1.215078 |
| thrust_step | 6 | 0 | 6 | -1.112712 to -1.112517 |

All 36 rejected for the predictive envelope. Margin=1.1−ensemble maximum |y|−.14 m. Best margin was approximately −1.11127 m. Exact parameters, declared actuation levels and full screens are retained privately; for feedback maneuvers, cruise level alone does not bound controller-generated thrust. The fixed grid is not an exhaustive continuous feasibility proof. No claim of safe informative active experimentation is supported under the audited menu. No actuation mechanism or safety threshold changed.

The existing enforced laboratory and backend already contained the core hard rejection; V3 explicitly selects it by default and tests the trusted boundary, rather than replacing it. A rejected request creates a safety record, no observation, no backend execution and no simulated-time charge. Repeated attempts are bounded by host actions. Predictive acceptance, actual execution, guard intervention, excursion and post-guard drift remain separate. The original zero-command fallback remains unverified as containment.

## Planner and features

`nautilus/active_planner.py` consumes allowlisted public current fit reports, never a hidden backend. It admits converged current singleton competitors with no bound hits and WRMS≤2, at most four within score gap6. Existing zero-noise forward models predict five observable channels on aligned .05 s samples. Pairwise normalized RMS minimum/mean are reported with declared scales. Fewer than two meaningful competitors, identical responses or forward-model failure yields unavailable discrimination, not an invented information score.

Only predictive-accepted candidates within remaining experiment/time budget can receive utility (minimum separation−.01×duration) or recommendation. At most four planning passes, 36 candidates/pass, four models/candidate and three recommendations. Repeated identical fit contexts reuse their menu. Execution always reruns the original screen. There is no fifth laboratory tool.

Flags: `risk_aware_planning`, `enforced_experiment_safety`, `critic_enabled`, `prediction_audit_enabled`. `make_lab`/V3 defaults select enforced safety; `Flags.legacy()` explicitly enables historical advisory research behavior with all additions off. Original four signatures and numerical algorithms are retained. Finalization validation is factored into a nonmutating shared method; the existing host gains optional orchestration hooks.

Forecast separation is not information gain, causal confidence or validated attribution probability. Missing speed/x, current/thrust/bias confounding, saturated/omitted fits, residual correlations and incomplete singleton coverage remain material limitations. No real active-planner benefit is measured here.

## Critic architecture and provenance

One separate `muse-wonder-1.0`/low, tool-free invocation reviews a valid pending finalization before the laboratory closes. Its compact public packet contains the selected/current competing fits, actual epoch references, residual/bound evidence and actual safety warnings. The closed review schema bounds severity/recommendation enums, concern arrays, text and genuine references. No hidden plant, seed, credential, evaluator label, raw hidden reasoning or laboratory tool is supplied.

The first finalize returns an honest `pending_critic`, `finalized:false` outcome for its real call ID. The proposal is preserved; the lab is never closed/reopened. Original Responses continuation IDs are retained. The investigator gets at most two further requests within its original twelve, and must cite the review hash plus a substantive-length response before actual finalization. It may retain, qualify, revise or abstain; no added numerical budget or safety override exists.

Critic limit: one request, zero retries, 2048 output tokens,≤60 s,≤15000 serialized packet bytes (not an exact tokenizer measurement). JSON-only text is validated locally; no unverified provider-native schema option is assumed. Missing/invalid review stops inference, records explicit role failure and leaves host-enforced abstention. A high-severity review cannot force more experiments. Host linkage/response-presence validation does not certify the quality of a natural-language rebuttal.

The original Muse provenance remains compatible; a separately hash-linked strict V3 sidecar records flags, plans, pending proposal, critic accounting, response and optional numerical predictions. Export/import checks bind both to the final ledger. These hashes detect inconsistency, not authentic authorship. No raw provider response or hidden reasoning is persisted.

## Predict–test–compare

Implemented for eligible competing fits and a predictive-accepted requested experiment: preserve both noiseless numerical trajectories before execution, then compare aligned pre-guard observations without rewriting the prediction. A normalized RMS gap>1 yields descriptive support/contradiction; otherwise inconclusive; insufficient prefix is untestable. The rule is not calibrated evidence of causality. The empty safe menu means no genuine safe prediction/experiment cycle was demonstrated. Tests exercise this path with an explicitly artificial accepted-screen fixture and real numerical simulation, not a fabricated live success.

## Fresh 24-case offline development comparison

The private design was reserved before generating outcomes: four cases each in nominal/subtle, current, thruster, sensor/controller, simultaneous compounds, and mismatch/near-confounding strata. Seeds are fresh and disjoint from Phase D. All 24 cases were retained. Six pilot IDs were selected by first-of-stratum position before results, not by favorable performance. All paired initial public ledgers matched, and each policy had independent state. Sixteen cases are singleton/nominal representable; eight are incompletely representable by one final label.

These are **deterministic numerical baselines**, not live Muse A/D runs. Advisory uses the established experiment-first matched fixed policy. Safety fixed takes the first accepted grid candidate if any, then existing passive registry-order fitting/finalization. With zero feasible candidates, it remains passive. Both get fits8/starts16/experiment1/time16/action12; no privileged fits or truth.

| Offline outcome | Advisory matched fixed | Safety-constrained fixed |
|---|---:|---:|
| Completed cases | 24/24 | 24/24 |
| Exact / representable | 10/16 (62.5%) | 6/16 (37.5%) |
| Partial constituent / compound or misspecified | 7/8 | 4/8 |
| Voluntary abstention / attempted | 4/24 (16.7%) | 14/24 (58.3%) |
| Whole-family accuracy / attempted | 12/24 | 6/24 |
| Incorrect nonabstaining attribution / nonabstaining cases | 3/20 | 0/10 |
| Supported / tentative decisions | 20 / 0 | 10 / 0 |
| Supported incomplete constituent claims | 7 | 4 |
| Numerical fits / starts | 192 / 336 | 192 / 336 |
| Converged / saturated fit reports | 192 / 64 | 192 / 86 |
| Policy elapsed time, summed seconds | 115.877 | 14.768 |
| Simulated experiment seconds | 288 | 0 |
| Executed experiments | 24 | 0 |
| Observed excursions / attempted | 6/24 (25%) | 0/24 |
| Excursions / executed experiments | 6/24 (25%) | Undefined (0 executions) |

Zero excursions with zero experiments is **not** successful safe active experimentation. Diagnostic yield fell and abstention increased without the additional experimental evidence. These development results do not isolate planner or critic efficacy and do not establish improvement over Phase D; the case pools and safety availability differ. No correct-abstention label or post-hoc identifiable subset was created.

Prepared factor settings A legacy/advisory/no critic; B planner+enforced/no critic; C legacy+critic/advisory; D full V3 have offline fake-provider orchestration coverage. Planning changes in B/D are an additional factor. Future performance ablations must hold planning/safety fixed when measuring critic effect. No repeated live legacy campaign was run.

## Pilot admission, usage and next stage

**Live V3 pilot: not run. Real investigator requests0; real critic requests0; real API tokens0.** All model replies used by new orchestration tests are clearly marked deterministic fake-provider fixtures with genuine laboratory operations. Existing Phase C/D real responses remain historical evidence, not V3 critic validation.

At the maximum six predeclared cases: up to72 investigator+6 critic=78 requests; investigator output≤196608 and critic output≤12288, total≤208896 tokens including reasoning. Critic continuation is unnecessary for a tool-free one-shot review. Investigator follow-up is included within the twelve-request ceiling, not extra. Numerical/action/time limits remain as requested.

Measured investigator input has per-case350000 soft stop, aggregate threshold2100000 before final-response overshoots. Critic packets total≤90000 serialized bytes plus instructions/envelopes; no verified tokenizer converts that to an exact provider-token ceiling. Cached tokens are subsets of input, reasoning subsets of output. Provider-verified pricing/context-token limits are unavailable under the current restricted configuration; the $8 objective cannot be enforced from the dashboard credit balance. A reliable worst-case aggregate input-token charge is not established. Under the explicit section14 stop condition, no authenticated calls were made.

Next stage: review the empty-grid finding and passive-only utility, then supply verified pricing/context bounds or a revised explicit token/overshoot authorization for the already reserved small pilot. Freeze exact pilot source/configuration and checkpoint starts before any calls; never repeat completed or uncertain starts. Stop after any provider/configuration failure or unexpected usage. Do not launch the remaining eighteen cases or a new legacy sweep without renewed approval. With the present evidence, expansion to a24-case live campaign is **not justified**.

## Frontend and validation

The existing three tabs remain. A local V3 companion-file control shows recorded numerical plans, safety/rejection context, critic review, investigator response and prediction audit when present. Missing evidence is explicitly unavailable. All narratives are rendered as text. Deterministic Markdown export includes validated V3 records; no configuration-change artifact or fabricated demonstration is created. Public investigation/Muse formats remain compatible.

Offline validation includes legacy request/ledger equivalence; finite reproducible original-screen audit; malformed/repeated rejection without execution, observations or time charges; backend defense in depth; accepted-branch guard/adverse-outcome retention; pure public-fit aligned forecasts and stale epochs; all four flag settings; nonmutating pending validation; one critic with genuine references/no tools; failure/unknown schema/invalid reference rejection; two-request follow-up bound; exact continuation IDs; prediction-before/after ordering; fresh24-case generation; private-field rejection; cross-language Unicode hashes and deterministic export. Test-only screen acceptance is labeled artificial and never used for product execution or case results.

All48 offline numerical records passed the existing public exporter and frontend ledger importer without hash rewriting or private fields; each generated the same Markdown report twice and no configuration export. The original frozen evaluator tests use an explicitly scoped offline-fixture adapter on the new tree; production candidate verification remains unchanged, and a regression confirms V3 cannot be refrozen as the original candidate. 396 Python tests, ten frontend test files, five exporter tests, TypeScript and the production build passed. The existing Vite chunk-size advisory remains. Source diff checks passed; no private records or generated frontend datasets are staged.

## Limits of this milestone

Trusted rejection prevention and bounded orchestration are implemented and tested. Safe informative active diagnosis, real critic usefulness, provider acceptance of the new tool-free review path, real decision correction, improved accuracy and real-world safety are **not established**. The finite conservative screen may leave no workable active menu; changing that policy requires separate scientific justification, not threshold relaxation for a favorable demo. Keep the prior candidate available as fallback.
