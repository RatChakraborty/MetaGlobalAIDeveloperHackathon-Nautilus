# Completed-investigation replay contract

Muse is not implemented. Live inference will run in protected Python; the static
frontend only replays completed records and never receives model credentials.
[MUSE_LABORATORY_CONTRACT.md](MUSE_LABORATORY_CONTRACT.md) remains the tool contract.

## Existing boundary

Use `Laboratory.call` with `propose_hypothesis`, `request_experiment`,
`get_fit_report`, and `finalize`. `capability_schema()` defines accepted inputs.
The trusted host selects the method, simulation backend, safety mode and budgets.
The investigator sees public snapshots and tool responses, never backend objects.

Export the public history or recorded validation wrapper using
`frontend/export_records.py`. Its `nautilus.public-investigation.v1` envelope has
`run_id`, `source_kind`, `disclosure`, `ledger` and `recorded_conclusion`.
Each ledger entry contains a SHA-256 `hash` and unchanged `body_canonical` JSON.
The body carries `index`, `type`, `previous_hash` and event-specific fields.
Observation hashes are the evidence references for fits and conclusions.
Do not insert metadata into an existing hashed history or silently drop fields.

| Available record | Existing representation |
| --- | --- |
| Observations | `observation.observations`: exactly the six public channels |
| Hypothesis request and rationale | `fit.report`, `fit.rationale`; failed fits use `fit_failure` |
| Numerical evidence | Fit parameters, bounds, scores, convergence, residual and identifiability diagnostics when recorded |
| Experiment and safety | `safety.request`, `safety.screen`, subsequent `observation.request` and `execution` |
| Diagnosis or abstention | `finalized` or separately validated `recorded_conclusion`; hypothesis, evidence refs, qualitative confidence and stop reason |
| Remaining budgets | Live `get_fit_report().remaining`; not a persistent export field |

Experiments invalidate earlier fits. Refit against actual new observations.
Preserve safety accept/reject outcomes and execution/intervention distinctions.
Scores and qualitative confidence are not physical probabilities. Unresolved
alternatives can currently be stated in the final stop reason; no structured list
is defined. A fit event records the resulting fit, not a complete input-request
transcript. Do not claim complete request reconstruction from it.

## Unsupported metadata

Investigator identity/model version, explicit fallback labels, separate reasoning
events, structured alternatives, cumulative budget summaries and API latency,
tokens, retries or cost have no dedicated supported export/UI fields. The future
Muse branch must define a versioned, allowlisted extension and tests before these
can be exported and rendered. Do not put them in arbitrary ledger keys or pretend
they are already displayed. Existing operator notes are untrusted text, not a
substitute for model provenance. This milestone adds no schema or backend changes.

No compatible simulation-verified repair record exists. Repairs remain unavailable.
The development demonstration has only telemetry: no fits, decisions or repairs.

`nautilus.visualization-only.v1` is a separate, run-bound file containing recorded
`time_s`, `x_m`, `y_m`, `heading_rad` and optional recorded corridor dimensions.
It is simulator truth for visualization, never investigator evidence. Private
plant/controller inputs, injected faults, evaluator answers, benchmark records
and credentials must remain outside both exports. Free text needs human privacy
review; key allowlists and hashes alone do not establish publication safety.

Experimental nuisance/discrepancy reports currently add `experimental` and
`warning` keys outside the exporter's report allowlist. Their export is therefore
unsupported without a future explicit schema change. Do not strip those caveats
to force a record through the current exporter.
