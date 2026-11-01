# Muse Phase B integration

## Initial attempt (retained development history)

See the recovery addendum below for the latest measured result.

The source integration and offline validation are complete. **The live end-to-end
definition of done is not met.** The one authorized development investigation
stopped at its first successful HTTP response: `status: incomplete`, no function
calls, with the entire 2,048-token output allowance consumed. No laboratory fit or
experiment executed. The host finalized an explicitly labeled abstention using the
real initial observation reference. This is not a voluntary Muse diagnosis or a
completed model/tool continuation. No second investigation was attempted.

Model: `muse-wonder-1.0`. Endpoint: `https://api.meta.ai/v1/responses`.
Measured first response: 18,241 input tokens, 2,048 output tokens, 20,289 total;
22.553 seconds provider request latency and 22.565 seconds overall host duration.
The adapter did not retain the exact successful HTTP status code, provider reasoning or detailed incomplete-response
payloads; output-budget exhaustion is consistent with these measurements, not an
independently retained provider explanation. There were no transport retries,
HTTP error responses, model tool calls, fits, experiments, or configuration
comparisons. All original laboratory budgets remained available.

The real action sequence was: send approved initial context and four declarations;
receive incomplete response; execute **host** `finalize` with `confidence: abstain`
and `hypothesis: null`. Do not attribute this finalization to the model.

## Source changes and protocol

- `nautilus/muse.py`: fixed-HTTPS Meta Responses adapter, nonsecret
  `NAUTILUS_MUSE_MODEL` override, inherited proxy/TLS trust, runtime
  `MODEL_API_KEY` lookup, no redirects or implicit retries. Credentials are never
  persisted or included in exceptions. HTTP error bodies are withheld. Successful
  responses containing the local credential binding are rejected without saving.
- `nautilus/muse_investigator.py`: four declarations derived from
  `capability_schema()`, strict closed objects, explicit optional-map unions,
  original registry/trial semantic validation and `Laboratory.call()` dispatch.
  Provider unions are envelopes; host validation preserves cross-field rules.
  A matching call ID maps to one accounted action; repeats reuse cached outcomes,
  while changed arguments under an existing ID stop the session. Provider call
  counts and unique laboratory-action attempts remain distinct.
- Continuation sends `function_call_output` with the original `call_id` and
  `previous_response_id`; tools/instructions are resent and `store: true` is
  explicit. Fake-provider and transport tests verify this method; **live
  continuation remains unverified**. Meta accepted the complete four-tool schema,
  `tool_choice: auto`, `parallel_tool_calls: false`, and strict declarations in
  the real request. The incomplete response did not exercise tool dispatch.
- The host handles text-only responses with bounded recovery, rejects parallel
  calls, never diagnoses from prose, and stops on incomplete/malformed responses,
  authentication errors, exhausted limits or bounded provider failures. Retryable
  429/5xx responses may be retried only under an explicit retry allowance; defaults
  and the live run use zero. Network timeouts are not retried automatically.
- `run_muse.py`: explicit-authorized single-run command, external trusted private
  development settings, external output directory, no held-out scenario selection.
  Per-request output allowance is configurable; the performed run used 2,048.
- `frontend/src/muse-provenance.ts`, existing report builder and small Investigator
  tab addition: import a separate allowlisted `nautilus.muse-provenance.v1` sidecar
  bound to the initial observation and finalized ledger anchor. Original canonical
  body bytes are hashed, avoiding Python/JavaScript float reserialization issues.
  Displays model identity, calls, usage, latencies, retries, sanitized errors and
  finalization origin. Old public v1/v2 records and post-investigation records
  remain unchanged. All three tabs remain available; no dashboard redesign.
- `tests/test_muse.py` and `frontend/tests/muse-provenance.test.ts`: fake-provider
  integration through a real laboratory, transport, strict-schema invariants,
  continuation, fitting/experiment execution, finalization/abstention, stale fits,
  malformed JSON, duplicate keys, unknown tools/parameters, text, errors,
  incomplete responses, retry/deduplication, ID collisions, budgets, deadlines,
  backend isolation, untrusted notes/comments, hash linkage and export/import.

## Limits, privacy and records

The live policy allowed at most ten model requests, ten unique model action
attempts, eight fits, sixteen optimization starts, one experiment and sixteen
simulated experiment seconds, all within the original laboratory ceilings.
It reserved at most 16,000 output tokens across requests, with 2,048 per request,
a 60-second request timeout, 600-second overall deadline and 1 MB cumulative
outbound context/tool bytes. A 120,000 measured-input-token threshold prevents
subsequent calls once reached; it cannot predict the provider's next charge.
Output reservations are conservative even if usage is missing; failed requests
consume their reservation. Laboratory calls are synchronous, so the deadline is
checked between actions and used to cap HTTP timeouts, not a process-kill guarantee.

There is no verified Meta tariff or provider-side dollar-budget control in this
integration. Cost is bounded through request/token allowances; **no dollar spend
or monetary hard cap is claimed**. Provenance records cost as unavailable. Review
pricing and the per-request reasoning allowance before authorizing another run.

The provider receives only approved public snapshots, declared controller context,
public six-channel observations, registries/schemas, public supervisor summaries
and actual tool results. Notes and source comments remain untrusted data, not
instructions. Prompt-injection tests establish dispatch containment, not immunity
of the model's judgment to misleading text. No backend/evaluator object or
visualization truth is serialized. Configuration proposals/evaluation are disabled;
the original finalize signature and separate host-evaluation contract are unchanged.
Future proposal support must use that host envelope, never extra finalize fields.

Real generated files are outside the checkout in
`/workspace/nautilus-local/muse-phase-b/`: allowlisted public investigation,
linked provenance, original public-history reconstruction and generated
`investigation_report.md`. Original hash-chain checks, Python exporter allowlists,
private-key/channel screening, frontend record/provenance import and report
production passed. No configuration diff or visualization export was produced.
The records remain local review material; no dataset or site was published.
Hash linkage establishes consistency, not authentic model authorship. Free-text
privacy review remains necessary before any future public dataset release.

## Validation and next steps

Offline: complete Python suite **299 passed**; all **9 frontend test files passed**;
**5 exporter unittest cases passed**; TypeScript and Vite production build passed.
The existing large replay-chunk build warning remains. New tests use deterministic
fake responses, explicitly distinct from the real incomplete response above.
Python-generated provenance was also loaded through the TypeScript importer/report
builder; frontend-only CI tests do not require a Python virtual environment.

Before claiming Phase B success, authorize one further bounded development run
with a reviewed reasoning/output allowance and pricing budget. Require a real
structured call, actual laboratory execution, matching tool-result continuation,
and valid model finalization or labeled host abstention after those actions. Do
not promote this single failed development run to an accuracy result. Comparative
work needs a predeclared protocol and separate authorization; no benchmarks,
parameter search, tuning claims, repair claims or held-out evaluations were run.

## Recovery addendum — context and budget review

The original incomplete attempt above is retained unchanged as development history.
The following source changes address its narrow context/output blocker, without
changing physics, numerical fitting, experiment protocols, safety or tool signatures.

Canonical UTF-8 serialization measurements for the same approved development setup:

| Component | Original bytes | Recovery bytes |
| --- | ---: | ---: |
| System instructions | 1,367 | 1,367 |
| Four strict function declarations | 14,427 | 14,427 |
| Initial Muse context | 48,874 | 14,911 |
| Context plus function declarations | 63,301 | 29,338 |

Original context components included 21,384 bytes of history (including an 11,847-byte
controller event), another 10,511-byte controller context, 8,565 bytes of duplicated
capability schemas, 6,781 bytes of registry entries and a duplicated registry ID
list. Raw initial observations occupied 8,981 bytes and raw controller excerpts
3,390 bytes; those figures overlap enclosing components and must not be summed.
Supervisor summary was 241 bytes, menu 388 bytes and safety/budgets 179 bytes.
The only measured provider count for the original request was 18,241 input tokens;
component byte counts are **not** exact component token counts or billing estimates.

`nautilus.muse-context.v1` preserves every public observation value without rounding
or downsampling, in explicitly ordered six-channel arrays tied to original evidence
references. Observation episodes/metadata now occupy 4,534 bytes. Shared registry
fields are factored into defaults and reconstruct exactly; identifiers, parameter
bounds, units, mechanisms and confounders remain available (3,113 bytes of entries
plus 263 bytes of shared defaults). Controller identity, approved structural facts,
declared settings, interface, unknowns and context/source hashes remain (3,865
bytes), while raw source/comments and duplicated controller ledger serialization
are omitted from the model-facing view. The complete authoritative history/source
context remains on the trusted host. Supervisor summaries, operator notes, numerical
caveats, all experiment defaults/bounds, coupled constraints, safety and budgets
are retained. Selection is deterministic and independent of private injected faults.
Subsequent `get_fit_report` results still use the original full laboratory outcome.

Strict schema unions remain unchanged: 14 knob variants, 14 bound variants and 32
experiment-parameter variants. Optional-map subsets are already deduplicated;
replacing them with mandatory nullable keys would change accepted argument shapes.
Provider support for factoring these via references was not verified, so no new
schema feature or weakened semantic validation was introduced. Focused regression
tests cover every existing optional subset and per-template proposal shape.

Recovery policy: 4,096 output tokens per request, at most 16,000 overall, ten model
requests, zero automatic retries, unchanged eight-fit/sixteen-start/one-experiment/
sixteen-simulated-second laboratory limits and disabled configuration evaluation.
The CLI forwards the selected allowance and now defaults to 4,096. The host reserves
each request's maximum before dispatch, then releases only explicitly measured
unused output tokens; missing usage and failed requests remain fully charged.
The 120,000 measured-input-token stop threshold is checked between requests and
cannot guarantee the next provider input charge. Existing timeout, byte and wall
limits remain. The available-credit figure is not a spending authorization or a
verified tariff. Public documentation/pricing requests were unavailable through
the current restricted network; no precise dollar cost or reasoning-control
parameter is invented.

Optional allowlisted provenance diagnostics now include actual HTTP status,
completed tool/text versus incomplete/error classification, explicitly reported
incomplete-reason codes, provider response/previous-response IDs and submitted
function-call IDs. Unrecognized incomplete reasons map to `other`; absent reasons
remain null. Malformed JSON/argument rejection and laboratory rejection are
classified separately. No raw provider body or hidden reasoning is persisted.
Old provenance companions and public v1/v2 records still validate unchanged.

### Recovery live outcome and acceptance

One additional real development investigation was attempted, with **one actual
Meta API request and zero retries**. The model remained `muse-wonder-1.0` at the
approved Responses endpoint. Meta returned **HTTP 200**, `status: incomplete`, and
explicit `incomplete_details.reason: max_output_tokens`. This reason is now
retained as an allowlisted diagnostic, not inferred from token counts.

Measured usage: **10,175 input tokens, 4,096 output tokens, 14,271 total**.
Provider request latency was **33.123 seconds**; total host duration was
**33.135 seconds**. Input usage fell by about **44%** from the earlier measured
18,241 tokens, but the doubled output allowance was still exhausted before a
function call. Output reservation accounting charged 4,096 of the 16,000-token
ceiling. No provider pricing was verified; there is no precise dollar-spend claim.

| Live acceptance step | Recovery observation |
| --- | --- |
| Completed Meta response | No: incomplete, explicitly output-token exhausted |
| Structured laboratory call | None returned |
| Trusted dispatcher validated a model action | Not reached |
| Actual model-requested laboratory execution | None |
| Actual tool result sent with matching call ID | Not reached |
| Meta accepted a continuation request | Not attempted |
| Subsequent Muse decision | Not reached |
| Valid finalization or host stop | Explicit host-enforced abstention |

Actual sequence: send compact approved context and four strict tool declarations;
receive incomplete response; host calls unchanged `finalize` with a null hypothesis,
initial evidence reference and `HOST-ENFORCED ABSTENTION: incomplete_response`.
This is neither voluntary model caution nor a numerical fitting failure: **zero
fits and zero experiments were attempted**, despite the laboratory's empty-fit
summary using its existing `OPTIMIZATION_FAILURE` label. Eight fit calls, sixteen
optimization starts, one experiment and sixteen simulated seconds remained.
Configuration evaluation stayed disabled. No second recovery investigation or
higher-token retry was attempted.

Both real attempts remain separately preserved outside the checkout, in
`/workspace/nautilus-local/muse-phase-b/` and
`/workspace/nautilus-local/muse-phase-b-recovery/`. The recovery original ledger,
allowlisted public export and provenance were validated; both old and new
provenance import successfully. The recovery record and explicit incomplete reason
loaded through the existing TypeScript importer/report builder and generated a
local `investigation_report.md`. Private settings, seeds, raw provider bodies,
credentials and generated data were not committed or published.

Final regression results: **312 Python tests passed**, all **9 frontend test files
passed**, **5 exporter unittest cases passed**, TypeScript and Vite production
build passed, and `git diff --check` passed. Thirteen focused new Python cases
cover compact-context reconstruction, every allowed optional argument shape,
private isolation, explicit/absent/unknown incomplete reasons, real-transport
output-limit forwarding and matched continuation IDs using fake responses,
usage-aware output reservation, CLI forwarding, old provenance compatibility and
malformed-argument diagnostics. Offline tests execute the real laboratory; they
are not live model successes. The existing replay chunk-size warning remains.

**Recovery and full live Phase B acceptance remain unmet.** Another real run
requires separate authorization; the available free credits do not extend the
single-investigation permission. The next narrow step is to verify supported
reasoning controls or review an explicit output allowance (up to 8,192 only after
review), while preserving the overall limits and avoiding prompt searches. No
reasoning-control parameter was guessed. Live laboratory dispatch and real
`function_call_output` continuation still need direct evidence before integration
can be called end-to-end verified. No diagnostic accuracy, repair or configuration
improvement is claimed.

## Read-only tool-dispatch diagnostic — latest result

**The isolated live dispatch/continuation milestone passed; full autonomous Phase B
remains unverified.** Branch: `feature/muse-investigator`. Base commit:
`2f4238375711ce8432b999a15c44f14238111b77`. The tested runtime source used for this
diagnostic is captured unchanged in `0e01f85c0b62e4adc25efb22334ae39c8489004d`.
Earlier failed attempts above remain infrastructure failures, not voluntary abstentions.

Changes are limited to a separate `muse_diagnostic` harness/runner, safe reasoning
usage/configuration instrumentation, compatible provenance validation and tests.
The diagnostic exposes only the existing strict `get_fit_report()` declaration and
uses actual `Laboratory.call()`; production still exposes the original four tools.
Only one model-requested read is allowed. Request 2 is conditional on a valid first
call and returns its exact result, original `call_id` and `previous_response_id`.
Failures stop immediately; there is no third request, automatic retry, additional
experiment, configuration comparison or full-investigator run.

Official reasoning/tool documentation remained unreachable. No confirming account
excerpt was available, so **no reasoning override was sent**. Both actual responses
reported `reasoning.effort: max`. Support for the proposed `reasoning.effort: low`
remains **unverified**; the nonsecret low-only candidate option is tested offline
but must not be described as account-verified. No `none`, forced tool choice or
undocumented thinking-budget field was used.

Canonical UTF-8 component bytes (not per-component provider tokens):

| Component | Minimal diagnostic | Production presentation with same short telemetry |
| --- | ---: | ---: |
| Instructions | 330 | 1,367 |
| Tool declarations | 223 | 14,427 |
| Initial observations/episode wrapper | 1,654 | 914 (columnar) |
| Approved controller context | Not needed for read-only diagnostic | 3,865 |
| Public supervisor summary | Not included | 241 |
| Hypothesis registry/defaults | Not included | 3,376 |
| Experiment menu | Not exposed | 388 |
| Remaining budgets | 70 | 70 |
| Safety constraints | 107 | 107 |
| Redundant schema/history | 0 | 0 |

Total diagnostic initial context: 2,263 bytes. Both columns use fresh 0.3-second
public telemetry, not the earlier full-investigation scenario. Production context
compaction and strict union representation were not rewritten in this milestone.
Full authoritative evidence stays on the host; the diagnostic's actual tool output
returns the original public report, including its history and capability schemas.

Exactly **two authenticated requests** were made to the unchanged Responses endpoint
using `muse-wonder-1.0`, `tool_choice: auto`, `parallel_tool_calls: false`, and
`store: true`. Each allowed at most 4,096 output tokens; the diagnostic reserved
8,192 total. Zero retries, numerical fits, experiments or evaluations occurred.
The input-token stop threshold, byte, timeout and wall limits remained separate.

| Actual request | HTTP/status | Input | Output | Reasoning output | Cached input | Provider latency |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1: retrieve public state | 200/completed | 1,273 | 226 | 161 | 0 | 2.825 s |
| 2: return actual report | 200/completed | 4,433 | 291 | 230 | 0 | 7.936 s |

Total: **5,706 input + 517 output = 6,223 tokens**, including **391 reported
reasoning tokens**. Overall host duration: **10.766 s**. Reasoning tokens are included
within output, not added again. Pricing remains unverified; no dollar-spend claim.
Only allowlisted counters/settings/statuses are retained, never hidden reasoning.

| Acceptance check | Classification and actual evidence |
| --- | --- |
| Authentication | Passed: both real HTTP 200 responses |
| Low-effort request support | Unverified: omitted, documentation unavailable |
| Effective reasoning setting | Passed observation: both responses reported `max` |
| Completed first response | Passed: `completed` |
| Structured request | Passed: `get_fit_report`, validated arguments `{}` |
| Real execution | Passed: existing laboratory returned its actual public report |
| Continuation linkage | Passed: original provider call ID and response ID preserved |
| Meta continuation | Passed: second HTTP 200, `completed` |
| Follow-up decision | Passed: genuine acknowledgement, no further tool call |
| Reasoning usage | Passed: provider-reported 161 and 230 tokens |

Muse acknowledged one evidence reference, no fits, the actual remaining budgets,
and the report's existing empty-fit `OPTIMIZATION_FAILURE` label. That label does
not indicate an attempted numerical failure: no fits were requested. The read
changes no evidence ledger entries. The host subsequently closed the diagnostic
with an explicit **host-enforced abstention**, labeled `diagnostic_completed`, not
a voluntary Muse scientific conclusion. No diagnosis or experiment was invented.

The real report's hash matches the retained actual tool result; original ledger,
public exporter, old/new provenance and TypeScript importer/report generation all
passed. Local review artifacts are outside the checkout at
`/workspace/nautilus-local/muse-tool-dispatch-diagnostic/`. No raw API bodies,
credentials, private scenario settings or generated records are committed/published.
Regressions: **338 Python tests passed**, all **9 frontend test files passed**,
**5 exporter tests passed**, production TypeScript/Vite build and diff checks passed.
The existing replay chunk-size warning remains. Fake-provider tests exercise real
laboratories and are explicitly separate from the two live responses above.

This proves one real tool dispatch and stored-response continuation. It does not
prove informative experiment selection, cause identification, autonomous finalization
or repairs. Success at the observed default `max` effort shows that this setting
alone does not universally prevent tool calling. It does **not** establish the
reasoning-token breakdown of earlier runs, which was not retained, or isolate the
causal effect of context, schema complexity and first-turn task demands.
The next step is a separately authorized concise first-action run with the full
four-tool interface and approved public evidence; use low effort only after support
is verified. That future full investigation was **not** run here. For later evaluation,
report completion over all attempts separately from accuracy conditional on completion.

## Offline preparation for a future four-tool run (not executed)

No authenticated requests were made in this preparation. The successful isolated
`get_fit_report` diagnostic above and both earlier incomplete attempts are preserved.
The user subsequently confirmed Meta's documentation for nested `reasoning.effort`
and the accepted `low` value for `muse-wonder-1.0`, citing
<https://dev.meta.ai/docs/reasoning>,
<https://dev.meta.ai/docs/protocols/responses>, and
<https://dev.meta.ai/docs/overview>. This establishes the documented format;
**live acceptance of low effort remains unverified in this environment**.

The production interface already retained all four tools. Its strict declarations,
validation, public context and numerical/safety behavior remain unchanged. The
full-investigation CLI now explicitly selects `low` by default (also exposed as
`--reasoning-effort low`). Initial instructions are shortened from 1,367 to 1,051
bytes and ask for the first useful, model-selected laboratory action before a full
case solution, retaining numerical caveats, untrusted-text handling and valid
finalization requirements. Offline transport tests exercise the real laboratory
with all four declarations, low-effort serialization, matched continuation IDs and
an unsupported-setting HTTP 400 that stops without retry/fallback.

For the existing approved development setup, the complete initial JSON payload is
**33,244 UTF-8 bytes**: 1,051 instruction bytes, 14,911 canonical public-context
bytes and 14,427 canonical tool-schema bytes, plus host notice, fields and JSON
encoding overhead. All 41 initial observation samples remain unchanged. These are
serialization measurements, not exact provider input-token estimates.

Proposed configuration, pending separate explicit live authorization:

| Setting | Proposed value |
| --- | --- |
| Model/endpoint | `muse-wonder-1.0`, `https://api.meta.ai/v1/responses` |
| Reasoning/tool policy | `reasoning.effort: low`, `tool_choice: auto`, `parallel_tool_calls: false` |
| Requests / model action attempts | At most 10 / 10 |
| Output tokens | At most 4,096 per request, 16,000 aggregate; reasoning included |
| Input stop threshold | 120,000 measured cumulative tokens, checked between requests; not a guaranteed input-charge cap |
| Outbound context/tool bytes | 1 MB cumulative host-accounted bytes |
| Transport retries / timeout / wall deadline | 0 / 60 seconds per request / 600 seconds checked between actions |
| Numerical budget | 8 fits, 16 optimization starts |
| Simulation budget | 1 experiment, at most 16 simulated seconds; existing advisory safety semantics |
| Configuration evaluation | Disabled |

Unsupported-parameter/authentication errors, network/provider errors and incomplete
or malformed responses stop without an alternate-parameter retry. Invalid model
actions receive sanitized correction results within the existing three-error and
host action/request bounds. Repeated call IDs reuse cached outcomes; collisions
stop. Exhaustion produces an explicitly labeled host-enforced abstention, never an
invented model diagnosis. No benchmark, prompt search, additional isolated diagnostic
or automatic allowance increase is proposed. Monetary cost is unavailable without a
verified tariff. Full low-effort autonomous tool selection/finalization remains the
unverified live step; it was not attempted during this offline task.

Offline preparation validation: **340 Python tests passed**, all **9 frontend test
files passed**, **5 exporter unittest cases passed**, TypeScript/Vite production
build and `git diff --check` passed. The existing large replay-chunk warning remains.
Changes are local and uncommitted for review; no authenticated request, commit,
push or merge was performed for this preparation.

## Authorized full four-tool low-effort run — latest result

**The real engineering end-to-end acceptance criteria were met with a valid
host-enforced termination after genuine model actions and continuations.** A
model-initiated scientific finalization remains unverified. One full development
investigation was run under the newly authorized limits, using the same approved
external development settings, never a frozen evaluation case. Single-agent,
sequential execution and all four original tool declarations were preserved.
No controller changes, parallel model calls, new product features, configuration
evaluations or additional live runs were introduced.

Meta accepted and reported `reasoning.effort: low` on **all five** actual requests
for `muse-wonder-1.0` at `https://api.meta.ai/v1/responses`. Every response was
HTTP 200 and `completed`, with no incomplete reason, transport retry, provider
error or rejected model action. This is direct live confirmation of the documented
low setting; earlier claims of unverified low effort above are retained history.

### Genuine model-selected actions and scientific outcomes

| Action | Actual laboratory outcome |
| --- | --- |
| 1. `request_experiment` | Executed `differential_step`, 12 s, differential 4 N, cruise 8 N, phase 3 s. These are resolved execution settings, not a reconstructed complete original argument transcript. |
| 2. `propose_hypothesis`: `nominal` | Converged; weighted RMSE 1.016091; penalized score 870.348136; no free parameters. |
| 3. `propose_hypothesis`: `port_degradation` | Converged; fitted port efficiency 0.785410; weighted RMSE 0.985521; score 826.013740. |
| 4. `propose_hypothesis`: `starboard_degradation` | Converged; fitted starboard efficiency approximately 1.0, upper-bound hit; weighted RMSE 1.016091; score 877.595929. |
| 5. `propose_hypothesis`: `heading_bias` | Converged; fitted bias 0.00423083 rad; weighted RMSE 1.014783; score 875.356534. |

The actual tool results for actions 1–4 were returned using their matching original
provider call IDs. Requests 2–5 used the corresponding `previous_response_id` and
were accepted with completed subsequent model decisions. The last heading-bias
fit was executed and recorded but **was not returned to Muse**: the host's next
iteration stopped before request 6. Muse never requested `get_fit_report` or
`finalize` in this run, although both were available. No model conclusion is inferred
from free text or from the laboratory's conditional ranking.

The experiment's predictive screen marked `would_reject_enforced: true`, elevated
risk, and predictive acceptance false. Existing `simulation_advisory` semantics
permitted the bounded offline execution; no safety behavior was weakened.
The measured public observed maximum lateral displacement was **6.512357 m**, beyond
the 1.5 m corridor. A hypothetical guard trigger was recorded at 4.95 s, but no
intervention occurred; the requested waveform continued to 12 s as designed.
`observed_corridor_excursion` is retained in execution metadata. This is an adverse
experimental outcome, not safe containment or physical stopping evidence.

All four fits used the original 41-row initial episode and 240 actual pre-endpoint
experiment rows. Command residual WRMS was 0; physical WRMS equals the reported
weighted RMSE in these fits. Port, starboard and bias fits had one-dimensional local
sensitivity ranks of 1, explicitly **not** model-identity guarantees. The nominal
fit has no fitted parameter. Recorded warnings preserve conditional measured-state
innovations, missing longitudinal/speed channels, known-reset assumptions and the
starboard bound hit. No private evaluator or answer-key correctness check was run.
The numerical summary selected port degradation among these requested fits; that
is **not** a Muse final diagnosis, physical attribution or measured accuracy claim.

### Measured usage and exact stopping point

| Request | Input tokens | Output tokens | Reasoning tokens (within output) | Provider latency |
| --- | ---: | ---: | ---: | ---: |
| 1 | 10,125 | 620 | 482 | 7.190 s |
| 2 | 26,890 | 342 | 185 | 9.586 s |
| 3 | 27,592 | 154 | 14 | 8.288 s |
| 4 | 28,322 | 133 | 0 | 8.318 s |
| 5 | 29,066 | 232 | 54 | 7.853 s |
| Total | **121,995** | **1,481** | **735** | **41.235 s** |

Total provider tokens were **123,476**; reported cached input tokens were 0 on all
requests. Overall host duration was **42.850 s**. Output remained within 4,096 per
request and 16,000 overall, including reasoning. No precise monetary cost is
claimed without verified pricing.

The existing 120,000 **measured-input-token threshold** is checked between requests;
request 5 crossed it to 121,995. This was an acknowledged soft stop threshold, not
an exact provider input-charge cap. The host recorded `termination_reason:
input_token_limit` and finalized a null-hypothesis abstention citing both genuine
observation references, with an explicit `HOST-ENFORCED ABSTENTION` label. That is
not voluntary Muse scientific caution. The pending last fit result was not sent
because no sixth request was authorized by the active host policy.

Actual consumption was five of ten request/action attempts, four of eight fits,
three of sixteen optimization starts, and one 12-second experiment. Remaining
budgets: four fit calls, thirteen optimization starts, zero experiments and four
simulated seconds. The experiment-count ceiling prevents a second experiment
regardless of unused seconds. Configuration evaluation remained disabled.

### Acceptance, validation and remaining limitations

| Real end-to-end requirement | Result |
| --- | --- |
| Muse generated structured laboratory calls | Passed: five actual calls, all validated and accepted |
| Existing laboratory executed actual actions | Passed: one experiment and four recorded fits |
| Actual tool output returned and accepted | Passed: four matched call-ID/response-ID continuations |
| Valid finalization or explicit host termination | Passed: input-budget host-enforced abstention |
| Original laboratory constraints/privacy retained | Passed: original bounds/safety/budgets and public-only export checks |
| Public evidence and model provenance import | Passed: Python export, TypeScript importer and report generation |
| Autonomous model finalization or scientific accuracy | Not established; no such claim |

The original ledger/hash chain, action anchors, numerical evidence references,
four actual continuation links, allowlisted public export and linked provenance
were validated. The actual record loaded through the existing dashboard importer,
and an investigation report was generated. Local review files remain outside the
checkout in `/workspace/nautilus-local/muse-phase-b-low-full/`; no private settings,
raw provider responses, hidden reasoning or generated datasets are committed or
published. Earlier failed and successful diagnostic attempts remain unchanged.

The full public experiment output and accumulated conversation increased measured
input usage substantially. Before another authorized investigation, review this
input growth and any proposed lossless presentation/budget change offline. No such
runtime change or additional live run was made here. The differing prompts, context
and reasoning setting across historical attempts prevent an isolated causal claim
about why earlier attempts exhausted output. A useful voluntary diagnosis still
needs separate evidence; the present result establishes bounded integration only.

Post-run regression validation: **342 Python tests passed**, all **9 frontend test
files passed**, **5 exporter unittest cases passed**, and TypeScript/Vite production
build passed. New offline boundary tests verify that reaching or crossing the input
threshold preserves the last executed fit while sending no further model request,
and records a host rather than voluntary model abstention. `git diff --check` passed;
the existing replay chunk-size warning remains. Source-only changes and this report
are prepared for normal commit/push to the same feature branch; no generated run
records, private configuration, source-controller changes or deployment are included.
