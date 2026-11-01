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
