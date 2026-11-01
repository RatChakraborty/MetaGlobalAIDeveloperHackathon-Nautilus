# Muse Phase B integration

## Outcome

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
