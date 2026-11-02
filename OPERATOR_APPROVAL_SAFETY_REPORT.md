# V4 safety and operator approval report

Implemented: three explicit offline simulation policies, private local operator CLI,
signed durable requests/checkpoints, independent laboratory/backend admission and
single-use execution. Automated tests pass. **A genuine human foreground-terminal
acceptance walkthrough has not been performed. Gate A must not be claimed fully
accepted until that action occurs.** Operator mode is experimental opt-in; default
V4 policy is Strict. No real model call or hardware execution occurred.

## Policies and invariants

- `simulation_enforced`: original predictive screen must accept. Rejection logs the
  exact request/screen, creates no observation and charges no simulated time.
- `simulation_operator_approved`: deliberately selected by the trusted caller before
  session creation. A predictively rejected valid trial waits for one local human
  decision; Muse cannot select policy or provide an approval object in tool arguments.
- `simulation_advisory`: explicit research selection, original advisory execution;
  never described as safe. Its statistics must remain separate from Strict.

Corridor±1.5 m, predictive1.1 m, guard.9 m and enforced2 s tail are unchanged.
No uncertainty member or threshold was weakened. Trial parameter constraints remain
unchanged, including the 25 N waveform-parameter envelope; the historical feedback
controller can generate different commands up to the original `Vehicle.max_thrust`
clip45 N. These are distinct limits, not a new actuator allowance. Both are retained.
Approved rejected simulations still use original enforced guard/tail monitoring;
approval bypasses only predictive rejection, not validation or budgets.

## Actual authority and recovery

`nautilus/v4/approval.py` uses an owner-only 0700 directory, 0600 local key/database,
HMAC-protected state and atomic SQLite transitions. Trust is the local OS account
plus foreground controlling-terminal interaction, not a typed name or hash alone.
Every process already holding this OS account is trusted: keep model tools limited
to the four laboratory operations; never give an untrusted model shell/file access.
There is no public HTTP authorization endpoint, browser approval button or token
that a replay file can turn into a grant.

Binding: random session/request IDs, observation epoch, canonical validated trial,
trial/screen digests, exact original screen, policy identity, budget and expiry.
Default expiry900 s. Legal request transitions are `AWAITING_OPERATOR` to
`APPROVED|DENIED|CANCELLED|EXPIRED`; approved to `EXECUTING|CANCELLED|EXPIRED`;
executing to `COMPLETED|FAILED`; terminal requests cannot execute again.
Approval is revocable before backend consumption. Laboratory and backend independently
validate the binding; the backend atomically consumes it exactly once.

Private JSON checkpoints are signed, source-bound and atomically replaced; no pickle,
API credential or hidden model reasoning is stored. Host waiting releases the provider
request and retains the original response/call IDs without inventing a premature tool
output. A resolved decision produces the original call's truthful result. Active
investigator time excludes human waiting; requests/actions/tokens never reset.
A file lock and checkpoint digest reject stale concurrent callbacks. An uncertain
provider dispatch is never retried. Unknown execution recovery never repeats a
simulation or invents observations. Recovery fix `81744fedf5753eaece5dd9aeafe42b306709bdc5` makes an old checkpoint
meeting an already-terminal execution explicitly `FAILED`, rather than still pending.
This does not change the numerical benchmark, which remains bound to `2d97c4cfabc7a5576d04e943df516f0b463c8695`.

## Focused zero-excitation audit

V3's 36 candidates/zero accepted result is preserved. Additional audit: three fixed
conditions ×15 original stress members ×4 one-factor ablations =180 simulations.
The zero-command condition is `thrust_step`,4 s, amplitude0, phase2, original 2 s tail.
Its commands are genuinely zero; feedback with target0 is a separate condition.
Only simulated public observations appear in the table; hidden case truth is absent.

| Condition | Maximum absolute observed y, m | Worst margin, m | Largest command, N | Excursion stress members /15 |
|---|---:|---:|---:|---:|
| zero_commands | 2.072517 | -1.112517 | 0.000000 | 6/15 |
| feedback_no_diagnostic_target | 2.175078 | -1.215078 | 30.519847 | 6/15 |
| small_diagnostic | 2.076475 | -1.116475 | 2.500000 | 6/15 |

The zero-command worst case is a signed-current stress member. Removing current
reduces its worst observed displacement to0 m, while removing lag or dead zone leaves
2.072517 m. Feedback/no diagnostic target: ensemble maxima original 2.175078 m,
without current.336602 m, without lag2.072517 m, without dead zone2.189949 m.
These maxima can come from different stress members and are **not additive causal
contributions**. Raw per-member tables retain guard time, post-guard observed drift,
actual physical command saturation and samples above the 25 N parameter level.
Background flow can continue moving the vehicle despite zero commands. Guard
intervention and command fallback are not proof of stopping or containment.
This is a finite diagnostic audit, not a global infeasibility proof or new controller.

## Genuine operator demonstration instructions

Use a local foreground terminal as the operator, not the investigator's model tools.
Use a fresh private directory outside the checkout. The first command queues only;
it does not approve or execute the flagged experiment.

```bash
.venv/bin/python -m nautilus.v4.operator --directory /tmp/nautilus-v4-demo demo --mode simulation_operator_approved
.venv/bin/python -m nautilus.v4.operator --directory /tmp/nautilus-v4-demo decide REQUEST_ID
.venv/bin/python -m nautilus.v4.operator --directory /tmp/nautilus-v4-demo resume
.venv/bin/python -m nautilus.v4.operator --directory /tmp/nautilus-v4-demo export
```

Replace `REQUEST_ID` with the returned identifier. The decision command opens
`/dev/tty`, displays exact risk/margin and asks the operator to type `approve ID`,
`deny ID` or `cancel ID`. It rejects unattended input. Denial/cancellation/expiry
returns a truthful nonexecution result. Approval permits one bounded numerical
simulation; the original negative margin stays in the evidence and actual adverse
outcomes remain visible. A second resume/approval cannot execute again. Do not reuse
an expired or completed session to obtain another outcome. `status` inspects state.
The demo has no model calls. The agent host resumption path is separately tested with
fake providers; provider retention after a real human delay remains live-unverified.

Load only `public-investigation.json` and `v4-provenance.json` into the local dashboard.
Never upload/publish the authority key, database or signed private `session.json`.
Replayed decisions are historical claims, not live execution authority. For the fake
agent host, a local `STOP` file blocks the next request and revokes pending execution;
it is cooperative stopping, not a hardware emergency stop or interruption of an
already executing numerical kernel.

Automated coverage includes all modes, malformed inputs, refusal without observations,
single use, denied/cancelled/expired/revoked grants, stale epochs/budgets/experiments,
forged requests, duplicate callbacks, signed-state tampering, interrupted execution,
uncertain provider dispatch, stop-before-approved-execution, and real continuation IDs.
Test decisions are explicitly labeled simulated humans. They do not satisfy the
manual human-acceptance requirement. No physical robot interface exists here.
