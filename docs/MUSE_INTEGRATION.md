# Meta Muse integration

Meta Muse is used only to propose tool actions. It never runs code, never sees hidden simulator truth, and never decides on its own what is accepted.

## Boundaries

- **Provider adapter:** `nautilus/muse.py` (`MetaProvider`). One HTTP request per `generate` call to `https://api.meta.ai/v1/responses`, authenticated with `MODEL_API_KEY` from the server environment. No SDK retries.
- **Tool dispatch:** `nautilus/studio_muse.py`. Each model-requested tool call goes through `call()`, which schema-checks the arguments and runs a trusted host function. Unknown tools and bad arguments are rejected.
- **Trusted execution:** controller revisions are validated by the policy IR. Muse supplies parameters or structured revisions, never Python or shell.
- **Kill switch and budget:** `NAUTILUS_MUSE_ENABLED` defaults to false. The live engineering session enforces request, trial, candidate and wall-clock limits (`Budget`).

## Engineering tools

`inspect_controller`, `inspect_diagnosis_evidence`, `propose_controller_revision`, `validate_controller`, `execute_controller_trial`, `inspect_experiment_results`, `evaluate_policy_robustness`, `compare_candidates`, `finalize_controller_recommendation`.

## Recommendation gate

`finalize_controller_recommendation` with `decision=recommend` is refused unless:

1. The candidate has a trial whose outcome is `Recommended`, and
2. The held-out robustness evaluation for that candidate has been run, and its outcome is `Recommended`.

`reject` and `abstain` are always accepted. A model claim cannot override a failed gate.

## Authentic provider test results

See `docs/MUSE_LIVE_TEST_RESULTS.md` for the recorded runs, token usage, worst-case reservations, and limitations. These are real provider calls and are kept separate from the mock suite. They are not part of `pytest` or `npm test`.

## Known limitations

- The Test C run finalized `recommend` before the robustness gate existed. The gate now refuses that path; the Test C run is historical and was not repeated after the change.
- The recorded runs produced only accepted proposals; failure rates are not measured.
- Muse's proposal was a parameter change to the integral term, not a structural source edit.
- Structural source generation is not verified. Earlier attempts returned HTTP 503, and one probe returned HTTP 400. The provider's error body is discarded by design, so the 400 cause is unknown. Local checks found no open objects in the strict wire schemas, so the cause is not a client-side closed-object error. No successful structural run exists, and no further paid probe was made without a diagnosis.
- The completed live Studio session (`recommend`, 11 requests, about $0.09 by estimate) used `muse-spark-1.3` through the operator script only.
- Billed cost is not returned by the API; the cost figures are worst-case reservations.
