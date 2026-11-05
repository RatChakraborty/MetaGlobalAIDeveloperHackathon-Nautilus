# V4 release readiness

V4 is an opt-in research branch, not a fully accepted autonomous or hardware-safe
release. Default policy is Strict; joint fitting is explicitly enabled only by a
trusted caller. V3 remains available at `f3e3a33b406a2360282b4733e056340df7eaaa5b`.
No merge, deployment or real V4 API request occurred.

| Gate | Evidence | Release status |
|---|---|---|
| A: approval boundary | All modes, signed local authority, single-use/expiry/denial/stale/interrupt/stop tests and continuation preservation pass | Genuine foreground-human acceptance still required; operator mode experimental opt-in |
| B: minimal joint diagnosis | Six pairs, physics regression, joint optimizer, parsimony/rank/residual checks, structured finalization and fake critic pass | Offline research core available; no unique-cause calibration or real-model result |
| C: expanded evaluation | 60 development cases,120 terminal outputs, two equal-capability numerical policies | Development only;11 failed physical gates retained, C/J not ready for independent freeze |
| D: application/replay | 446 Python tests,11 frontend files,5 exporter tests, build and real Chromium replay/export checks pass | Existing application and optional V4 evidence viewer usable; no public approval endpoint |

Numerical evaluation checkpoint: `2d97c4cfabc7a5576d04e943df516f0b463c8695`.
Recovery checkpoint: `81744fedf5753eaece5dd9aeafe42b306709bdc5`.
The final UI/report commit does not alter scientific results. Use the recorded source
for reproduction; do not force an old private checkpoint through a changed source guard.

## Demonstration

Follow [OPERATOR_APPROVAL_SAFETY_REPORT.md](OPERATOR_APPROVAL_SAFETY_REPORT.md) for the
four-command local CLI walkthrough. A real operator must perform `decide` in their
foreground terminal; automated simulated decisions are not human acceptance. Open
only the generated public record/V4 companion in the existing dashboard. The browser
cannot approve anything. For joint numerical verification run
`pytest tests/test_v4_models.py`; public test fixtures are not private evaluation answers.

Local browser regression is reproducible with the standalone
`frontend/tests/v4-browser.mjs`: start Vite bound to127.0.0.1, temporary Chromium CDP
bound to127.0.0.1, and pass a private fixture directory containing pending/joint public
records, V4 companions and visualization-only pose. Do not publish the private fixtures,
sessions or authority directory. There is no cinematic redesign or renderer replacement.

## Remaining cut lines

Do not advertise safe active experimentation: the finite36-candidate screen accepts
none. Do not advertise Muse/critic superiority: real V4 API usage is zero. Do not
advertise genuine human acceptance until the terminal walkthrough is complete.
Missing-channel/gap/stuck preprocessing, triples, time-structured faults, battery or
new platforms, controller-source repair and new controller policies are disabled or
deferred. The core 60 is not a validated independent holdout; no full 100-case physical
catalog was generated. Full blueprint supports88 static constructor slots (not all physically qualified) and explicitly excludes
G/K; only60 were actually evaluated.

Maintain the existing known-good submission branch. Before the November 3 noon ET
feature-freeze target, either complete manual acceptance or retain Strict/V3 as the
submission path. Preserve November 4 for verification/submission as requested. Any
future deployment, merge, real-provider pilot or larger study needs its own explicit
authorization/admission. The deadline remains November 4, 2026, 9:00 PM ET.
