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
| 5. Live Muse | Done (fake-provider tests only) | `POST /api/v1/muse-investigations` runs on the server with `MODEL_API_KEY`. It requires `Authorization: Bearer` matching `NAUTILUS_DEMO_TOKEN` (route returns 401 when unset), enforces `NAUTILUS_MUSE_DAILY_LIMIT` (default 10 UTC runs, persisted in `muse-quota.json`), and rejects client-supplied keys. No browser key field. No live provider call has been made. |
| 6. Evidence and trace | Done | Evidence ledger timeline; observed lateral-deviation trace (`lateralSeries`). |

## Live scene decision

Public telemetry has no along-track `x` position, and the recorded `Replay` needs `x_m`. A plan-view replay of live results would therefore invent motion. The Lab plots observed cross-track deviation over time instead, labelled as observed telemetry rather than a replay. The three.js recorded replay is unchanged.

## Security

- Public API exposes only allow-listed scenario knobs and public telemetry columns.
- Truth fields (`current_x_mps`, `current_y_mps`, `port_actual_n`, `starboard_actual_n`, `heading_rad`, `desired_heading_rad`) stay server-side.
- Checked in the bundle: heading bias and seed value are absent from public files.

## Checks run

- Frontend: `tsc --noEmit` exit 0; `npm test` 86/86 pass; `npm run build` exit 0 (chunk-size warning existed before).
- Python: `tests/test_api.py` 16 passed (3 added for phase 5). `tests/test_muse.py` passes. Full suite: 508 passed. The earlier baseline was 510 from a different state; the count is not directly comparable.
- Frontend after phase 5: `tsc --noEmit` exit 0; `npm test` 86/86 pass.

## Not verified

- The Lab UI has not been checked in a browser. Only typecheck, unit tests and build ran.
- Live Muse has not been run against the real provider. Only the fake provider path is tested.
- Failed Muse runs return the fixed message `Investigation failed`, so provider detail is not shown to the user. This hides diagnostic information.
- Remote `main` cannot be fetched from this workspace (no GitHub credentials), so whether the deployed site matches `main` is unverified.
- Vercel Hobby terms are unverified. You state the Hobby tier applies because the project is open source.
- `current_y=2.5` is outside the singleton bounds (±1.0). Abstention classification is incomplete for that case.

## Muse key handling

The model key stays on the server as `MODEL_API_KEY`, read only by `nautilus/muse.py`. The browser never sees it and no request carries it. Live runs need the demo token and count against a daily cap, so the provider-side monthly spend cap is the hard stop. The key is never written to job records or artifacts, and provider errors reach clients only as `Investigation failed`.

## Next steps

1. Browser-check the Lab (run API locally, dev server, check layout).
2. Approve or decline pushing the branch.
3. Choose a host, set `MODEL_API_KEY`, `NAUTILUS_DEMO_TOKEN`, `NAUTILUS_ALLOWED_ORIGIN` and a $10/month cap at the provider, then deploy.
