# Pre-Muse readiness

## Status

The dashboard was manually merged by PR #2. Remote main is
`f55a0f7fe4d0ea877a7bb8b2ce065f1d6597e742`; its parents are
`5fd3e9a088f9baa4c815cdc7fd2a69abf224fbdc` and
`b8432b9053a847e8e34a7dbdb49cb2b1be8fdcb2`.
The dashboard feature head remains `b8432b9053a847e8e34a7dbdb49cb2b1be8fdcb2`;
the numerical feature head remains `52074d44a3cef8b8f24e9bdb0d2139009201414e`.

Local `feature/pre-muse-readiness` starts at main's merge commit. The old
six-file staged checkout is untouched. Its original candidate tree was
`d7cd72b3bd02007d45b40e7f159095bc1a115718`; the patch applied cleanly because
merged main has exactly the original dashboard tree. No new commit, push, PR or
merge was performed. An unresolved automatic approval rejection blocked earlier
GitHub tree uploads. This milestone supplies a source-only patch without retrying
alternative upload routes. PR #2 is closed/merged, not a pending readiness PR.

## Implemented and verified

- Reconciled six-file startup patch; default-disabled demo loading, shared strict
  validators, atomic four-file loading and manual-selection preservation.
- Manual-only Pages workflow: lockfile install, frontend tests, TypeScript/build,
  static-output artifact; publication defaults false and is restricted to main.
  Demo loading is explicitly false in the workflow. No workflow was dispatched.
- Existing replay contract documented, including unsupported model provenance,
  usage metrics and experimental report fields; no schema or backend extension.
- 192 Python tests passed in 27.08 seconds; 19 frontend tests passed.
- TypeScript and repository-base production build passed. Vite retains a warning
  for the roughly 545 kB replay chunk; no performance redesign was attempted.
- Real enabled-loader check loaded four sanitized files and 3,615 aligned poses;
  default-off test makes no requests. Hash/ledger/schema/time alignment and
  private-key rejection tests pass. Base-path assets and font notices are present;
  the ordinary build contains no JSON datasets.
- All numerical module, existing Python test and scientific protocol bytes match
  main. Existing baseline investigators and four laboratory tools pass the full
  regression suite. No Muse, repairs, physics or benchmark changes.

A fresh offline `npm ci` failed with ENOTCACHED for Vite. Tests/build used preserved
lockfile-version dependencies. Clean network installation and Actions execution
remain unverified in this environment; the workflow has not run on GitHub.

## Rendering acceptance

A fresh private-QA browser run automatically loaded both recordings. Trajectory
showed the recorded disturbance at 100 s: cross-track 2.805 m, outside corridor.
Investigator showed no conclusion or current fits; Analytics showed actual
observation units and unavailable prediction curves. QA loader/main/config match
the candidate source exactly. The browser reports GPU unavailable and uses the
Three.js SVG fallback. Prior 1440x900 and 1920x1080 layout, camera, synchronization,
remount and fallback checks remain preserved; those full layout checks were not
repeated here. Hardware WebGL2 materials, headlights, shadows, fog, detailed
underwater scene, mouse controls, GPU memory and sustained frame rate are still
unverified. No 60 FPS claim is made.

## Demonstration proposal, not publication

Synthetic simulation-only development recordings, not repaired runs. All 3,615
poses and every six-channel observation exactly match retained original CSVs.
Simulator and exporter fingerprints match the preserved review manifest:

- Simulator SHA-256: `c4f5035d81bc51778ba0447b794541af0d6cb49c3da135742a8f9d1c821ef074`
- Exporter SHA-256: `ed1cd77bf7cf62690fb064582149b0d8182e97fb3a43f69c8a1b22c0571ae14b`

| Proposed filename | SHA-256 |
| --- | --- |
| `disturbance.public.json` | `47c3d026bd616095dc8dda969c135c273fe8a54d41f5d40f86f10e4325ec3626` |
| `disturbance.visualization.json` | `3d8f0cc34614e08f2de5d82efb8e5e10abf16f73151402c8b66b5db4777bc300` |
| `reference.public.json` | `46dc99efe3ab6cb6e5514de31fdd0133d117a4dfa098f7fc60637266bb3e2ebc` |
| `reference.visualization.json` | `f0f764cbdfcf1858ac8732d3cf1baa61e375be1f670192dc0c66cacb821ecdb2` |

Disturbance: 2,001 samples, 100 s, maximum |y| 2.8106494042077035 m,
1,900 samples outside the recorded +/-1.5 m corridor. Reference: 1,614 samples,
80.639357483649 s, maximum |y| 0.010639052099994165 m, zero outside samples.
These are visualization-only derived statistics, not investigator evidence or
benchmark results. The public observations have no x-position. Visualization
truth is separate and never sent to the investigator. No fits, agent decisions
or repairs exist in these recordings. The proposed four-file bundle is unchanged
and remains outside the repository; private source recordings remain preserved.

The sanitized verification is reproducible without private inputs. Full simulator
regeneration requires excluded private configuration; earlier private exact
regeneration checks are preserved, not claimed as public reproducibility.

## Source inventory

- `.github/workflows/dashboard-pages.yml`
- `PRE_MUSE_INTERFACE_CONTRACT.md`
- `PRE_MUSE_READINESS_REPORT.md`
- `README.md`
- `frontend/README.md`
- `frontend/src/demo.ts`
- `frontend/src/main.ts`
- `frontend/tests/demo.test.ts`
- `frontend/vite.config.ts`

No generated records, raw truth CSVs, private configuration, evaluator answers,
benchmark results, secrets, screenshots, checkpoints, caches or build output are
included. Free-text records still require human privacy review before approval.

## Remaining approval and deployment steps

1. Apply/review the source-only patch on updated main in a user-controlled checkout;
   run `npm ci`, tests and build with network access. Commit the reviewed nine
   source/documentation files, push `feature/pre-muse-readiness`, and open a PR.
2. Inspect the full PR diff and merge preview; require green checks before a normal
   merge. Preserve history and existing feature branches.
3. Finish hardware WebGL2 desktop acceptance. Independently approve the exact four
   demo hashes before installing them under `frontend/public/demo/` and enabling
   `NAUTILUS_DEMO_ENABLED=true` in a separate reviewed deployment change.
4. Separately authorize publication, configure Pages for Actions and any environment
   review protection, then manually dispatch publication from main. Treat the site
   as public regardless of repository visibility. Verify the hosted base path,
   assets, both recordings and fallback after publication.
5. Start `feature/muse-investigator` from verified integrated main. Resolve the
   documented missing metadata/schema support there; keep API keys in Python.

Prepared but awaiting approval: dataset installation, autoload enablement and
Pages publication. Implemented but not GPU-tested: the existing Three.js scene.
Not implemented: Muse client/loop, live services, repair verification and new
schema fields. Public deployment is not complete.
