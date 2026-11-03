# Authentic Meta Muse provider test results

These are real provider calls made from a sandbox during the release run. They are reported separately from mock tests. No API key, token or authorization header is recorded here.

## Provider and model

- Endpoint: `https://api.meta.ai/v1/responses` (Responses API, `tool_choice=auto`, `parallel_tool_calls=false`, `store=true`).
- Model: `muse-spark-1.3` (confirmed present by `GET https://api.meta.ai/v1/models`, HTTP 200).
- Pricing used for conservative reservation: $1.25 per 1M input tokens, $4.25 per 1M output tokens. This was not returned by the API; treat it as the documented rate and confirm on the billing dashboard.

## Test A — connectivity

- Result: passed on second attempt. The first call with a 16-token output cap returned `status=incomplete` because reasoning tokens consumed the cap. The second call with a 256-token cap returned `status=completed`, with text.
- Measured usage (second call): 20 input tokens, 207 output tokens, of which 197 were reasoning tokens. Latency about 3.8 s.

## Test C — engineering proposal (live tool loop)

- Artifact: `artifacts/muse-live-engineering-run.json`.
- Seven model turns. Every tool call was dispatched through the trusted `call()` path. All seven tool calls succeeded: `inspect_controller`, `inspect_diagnosis_evidence`, `propose_controller_revision`, `validate_controller`, `execute_controller_trial`, `inspect_experiment_results`, `finalize_controller_recommendation`.
- Model-originated proposal `cand-integral-1`: `integral_ki` 0.0 → 4.0 and `integral_limit` 0.5 (unchanged). Heading gains `heading_kp` 39.0 and `heading_kd` 18.0 kept at baseline values, which Muse set explicitly.
- Host-validated development trial: outcome `Recommended`, all declared gates passed, mean RMS difference −0.208 m (improvement).
- Muse finalized with `recommend` before running the held-out robustness check. This is recorded as a limitation: the final decision was not gated on robustness.
- Usage totals across seven turns: 21,805 input, 1,961 output, 1,400 reasoning tokens.

## Test D — feedback continuation

- Artifact: `artifacts/muse-live-robustness-run.json`.
- Setup: the host replayed Muse's earlier proposal through trusted tools and returned the development result as context. This is a continuation test, not an independent proposal.
- Muse called `evaluate_policy_robustness` for `cand-integral-1`, then finalized `recommend`.
- Stored robustness outcome: `Recommended`, no failed gates, mean RMS difference −0.181 m.
- Usage: 2,622 input, 618 output, 404 reasoning tokens over two turns.

## Cost

- Worst-case reserved spend (conservative per-request reservation, not billed amounts): about $0.14 for Test C and $0.04 for Test D, plus about $0.001 for Test A. Total reserved about $0.18 of the $30 authorization.
- Actual billed charge must be read from the provider dashboard; the API does not return a cost field.

## Limitations

- One proposal in one run. Muse did not generate a rejected or invalid proposal in these runs, so these results do not show failure rates.
- Muse's rationale mentioned "negligible change on model_mismatch" in Test D; the stored artifact does not contain that per-case breakdown, so that claim is not verified.
- Muse's Test C recommendation skipped robustness, which the host did not require. Recommendations must not be treated as final until the robustness gate is enforced in the host.
- Held-out robustness is evaluated by the host, not by Muse. The development split was used for the Test C decision.
- Not validated on hardware. Simulation only.
