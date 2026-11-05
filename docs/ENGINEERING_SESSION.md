# Continuous engineering session

Public telemetry → diagnosis and supported experiments → **Engineer this failure** →
Policy Studio → exact source/parameter candidate → matched development trial → existing
held-out split → host gates → combined JSON report. No manual file transfer is needed.

`nautilus.engineering-context.v1` is a bounded public-evidence envelope. Its canonical body
and session identity are hash checked in Python and TypeScript. It carries six-channel
recorded sample subsets, complete episode hashes, fits, uncertainty and experiment references.
The combined report retains canonical host ledger and controller JSON strings; parsed display
copies cannot replace those strings when verifying Python fingerprints.

Generation inputs travel separately to the trusted host. They are never supplied to the
engineer or included in the public report. Before a linked trial, the host must exactly
reproduce the initial observation hash. It appends the investigated scenario to the complete
four-scenario development split; baseline and candidate use identical inputs and noise.
A mismatch fails closed. Cross-runtime numerical changes can require a new investigation.

Candidate source, parameters, IR and fingerprint are retained. Editing invalidates earlier
evaluations. Final recommendation requires development and held-out results for the same
fingerprint. Manual robustness requests recompute the development screen; mocked sessions
reuse their executed results without extra trials. Candidate selection closes after
held-out inspection in the normal Studio workflow. These published fixed scenarios are
regression checks, not a new unseen benchmark or evidence for unrestricted generalization.

## Execution provenance

- Deterministic investigation and mock engineering are explicitly labeled. No provider call
  is made by the free Studio endpoint. Numerical tools execute the actual Python simulator.
- The authentic 11-event recorded real Muse parameter-engineering case is unchanged and
  remains a separate study. It is not relabeled as a new continuous live session.
- Protected live investigation can produce the same handoff. Full live Muse investigation
  through live source engineering is unverified here: no securely injected credentials were
  available. The Studio live engineer remains disabled. No paid probe was attempted.
- Simulation truth in controller plots is visualization-only and never diagnostic telemetry.
  Tracking improvement does not prove the original physical explanation or a hardware repair.

## Physical navigation source

`python scripts/verify_navigation.py INPUT.csv --output verification.json` reproduces the
source checks for `nature1949/AUV_navigation_dataset/20220712_0_1.csv` (CC0-1.0).
The checked source has SHA-256
`3287424eafd36f5e3129ad9bd2c21c827fc9779338f4136e84b2a6ea6369973c`.
The public verification record contains source-derived checks and a small coordinate preview,
not private Nautilus scenarios or evaluator records. The raw source CSV is not bundled.

940 rows are finite and geographically in range; timestamps strictly increase. The first
20 source time units select 158 rows. A local tangent-plane preview explicitly assumes
latitude/longitude degrees and time seconds. Heading, velocity conventions and original
units documentation were not independently retrieved, so a simulation bridge is withheld.
No thrust, current, physical fault or vehicle repair is inferred.

## Rehearsal

1. In Workspace set a fresh development seed, run an investigation and inspect its ledger.
2. Choose **Engineer this failure** and check the same session ID in Engineering Trace.
3. Run the free mocked engineer or load a declared host example. Review its origin and source.
4. The mocked route loads its executed trial, robustness and host decision automatically.
   For a host example, validate, run the paired trial, then run held-out robustness.
5. Read the final host decision and export the combined engineering report.
6. Keep the recorded real Muse study separate when presenting it on Overview.

Reproduction of public fit evidence uses the retained full public observations. Exact private
scenario replay additionally requires the host's original generation inputs and the same
runtime; the public report deliberately does not reconstruct hidden inputs. No new campaign
or frozen protocol was changed.

## Checkpoint verification

- Offline core regression: 652 passed, 4 subtests; final export-fix recheck: 89 passed (overlapping tests).
- Frontend: 152 passed; TypeScript and production build passed.
- Redis-backed checks remain blocked by the runtime's Unix-socket denial; no budget controls were weakened.
- Browser: investigation, executed experiment, automatic Studio handoff, five development cases,
  three held-out cases, host gates and downloaded report verified. Canonical ledger and both
  controller fingerprints verify again in Python. No model API call was made.
- Numerical simulator, fitter, compiler, frozen protocols and authentic recorded Muse case are unchanged.
- Feature checkpoint only. Main, deployment configuration and Production were not changed.
