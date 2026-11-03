# Nautilus integrated product: status report

Branch: `feature/nautilus-integrated-product`. Not pushed, not merged to `main`, not redeployed. Pushing and deploying need your approval.

## Scope

Phases 0–4 and 6 of the full-stack spec. Phase 5 (Muse) is out of scope.

## Phase status

| Phase | Status | Notes |
|---|---|---|
| 0. Audit | Done | Audit done in the workspace. Coverage matrix not written to a separate file. |
| 1–2. Static demo bundle | Done | Vercel project `nautilus-demo` serves the static bundle. |
| 3. Thin API | Done | `nautilus_api/` (stdlib `http.server`, no new dependency). Bounded worker, `MAX_QUEUED=4`, durable JSON job records, 4096-byte body cap, `Cache-Control: no-store`. |
| 4. Lab tab | Done (not visually checked) | Shown only when `NAUTILUS_API_BASE` is set at build time. Default build embeds no API URL. |
| 6. Evidence and trace | Done | Evidence ledger timeline; observed lateral-deviation trace (`lateralSeries`). |

## Live scene decision

Public telemetry has no along-track `x` position, and the recorded `Replay` needs `x_m`. A plan-view replay of live results would therefore invent motion. The Lab plots observed cross-track deviation over time instead, labelled as observed telemetry rather than a replay. The three.js recorded replay is unchanged.

## Security

- Public API exposes only allow-listed scenario knobs and public telemetry columns.
- Truth fields (`current_x_mps`, `current_y_mps`, `port_actual_n`, `starboard_actual_n`, `heading_rad`, `desired_heading_rad`) stay server-side.
- Checked in the bundle: heading bias and seed value are absent from public files.

## Checks run

- Frontend: `tsc --noEmit` exit 0; `npm test` 86/86 pass; `npm run build` exit 0 (chunk-size warning existed before).
- Python: `tests/test_api.py` 13 passed. Full suite last ran at 510 passed, before the latest frontend-only commits.

## Not verified

- The Lab UI has not been checked in a browser. Only typecheck, unit tests and build ran.
- Live Muse is not built. Phase 5 is out of scope.
- Remote `main` cannot be fetched from this workspace (no GitHub credentials), so whether the deployed site matches `main` is unverified.
- Vercel Hobby terms are unverified. You state the Hobby tier applies because the project is open source.
- `current_y=2.5` is outside the singleton bounds (±1.0). Abstention classification is incomplete for that case.

## Muse key conflict (for later phase)

The spec says the model key lives server-side as `MODEL_API_KEY`. You want to enter a key in the UI for the demo. Planned approach: a one-run key held in server memory only, never stored, logged, returned, or written to artifacts. This decision needs your sign-off before phase 5.

## Next steps

1. Browser-check the Lab (run API locally, dev server, check layout).
2. Approve or decline pushing the branch.
3. Decide on the Muse key approach before phase 5.
