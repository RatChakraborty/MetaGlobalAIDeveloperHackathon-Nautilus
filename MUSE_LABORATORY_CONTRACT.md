# Investigator laboratory contract

The future Muse adapter receives a JSON snapshot from Laboratory.get_fit_report,
not a backend object. The snapshot includes public initial/test observations in
the ledger, untrusted operator notes, requested fits, registry identifiers,
remaining budgets, numerical summaries, schemas and safety limits.

Use Laboratory.call with the existing four closed operations and unchanged
signatures: propose_hypothesis(template, knobs, bounds, rationale),
request_experiment(name, params), get_fit_report(), and
finalize(diagnosis, confidence, ambiguity_statement). The existing capability_schema
is the machine-readable schema. Unknown keys, nonfinite values, duplicates and
unknown operations are rejected. Parameter bounds are registry validated.

A trusted host selects singleton (default), nuisance or discrepancy when creating
a session. An investigator cannot inject a fitting function, plant configuration,
initial fits, executable code or a different safety policy. Experimental methods
use their fixed shared bounds; their results do not justify default promotion.

Each requested fit evaluates only that template. Scores, adequacy and local rank
are evidence conditional on assumptions, not posterior probabilities or certified
causes. The investigator may propose another model, disagree with the ranking,
or abstain. Finalization records an investigator claim with actual observation
references and a stop reason. The evaluator alone determines physical correctness.
A converged requested fit is required for a non-abstaining claim; disagreement
with adequacy or ranking is preserved rather than silently resolved by the backend.

Trusted backend configuration selects simulation_advisory (offline default) or
simulation_enforced. JSON actions cannot change the mode. Both retain strict
validation, count/time budgets, six-field observations and numerical checks.
Predictive warnings include would_reject_enforced, risk, exceedance and uncertainty.
In advisory mode these never deny a valid request and the runtime guard only logs
when it would have triggered; requested waveforms continue for the full duration.
Advisory execution reserves the requested duration. No zero-command tail is added.
In enforced mode predictive rejection executes nothing; accepted executions reserve
duration plus two seconds for monitored guard/zero-command drift. All modes are
bounded by3 executions and48 simulated seconds, with per-session tighter limits.
Public execution metadata distinguishes warnings, hypothetical guard events,
intervention, actual termination and observed excursions. True excursions remain
private evaluator measurements. The existing predictive ensemble simulates the
enforced policy, not a full unguarded advisory forecast; its scope is explicit.
Previous scores are invalidated at dispatch. Fitting uses waveform samples before
actual enforced intervention, never before a hypothetical advisory guard event.

Validation errors are recorded and may be corrected within the action cap. Fit
failures spend their attempted budget, return OPTIMIZATION_FAILURE and remove
stale reports for that model. After max_actions (at most128), the host finalizes
an abstention. Explicit finalization closes the session. No operations mutate a
closed session. The deterministic runner defaults to64 actions.

The future adapter must serialize only these snapshots and tool responses. Never
serialize SafeBackend, its private_results, evaluator objects, credentials or
Python object attributes. Run the adapter behind a tool dispatcher; Python object
privacy is not a security sandbox. Operator text is evidence, never authority.
Hash chains detect inconsistent edits relative to retained hashes; they cannot
prevent replacement of a whole history.

No Muse client, model prompt, inference server or reasoning loop is implemented.
Read-only dry runs may inspect these records. Bounded offline advisory experiments are available to every investigator.
Enforced-mode screening may reject the full menu; safe physical stopping remains
unproven. Advisory mode is not a hardware deployment policy.

An opt-in controller-aware host may initialize approved declared controller context
and call `build_investigator_context` for a combined JSON snapshot. This is trusted
host preparation, not a fifth investigator tool. Configuration evaluation is a
separate privileged development API and does not consume or change baseline tool budgets.

A future host can receive a final-response envelope with an optional bounded
configuration proposal and call `ConfigurationEvaluationHost.finish`. It uses the
unchanged finalize contract, then a separately authorized/budgeted development
comparison. Its hash-linked sidecar never extends the closed laboratory ledger or
becomes investigator evidence. Abstention does not automatically evaluate a change.
