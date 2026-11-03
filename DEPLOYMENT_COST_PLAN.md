# Deployment and cost plan: Vercel Hobby + Upstash Redis

Status: implemented on `feature/nautilus-integrated-product` and tested locally. No Vercel project, Upstash database or secret has been created, no production deploy has been made, and no paid Muse call has been made. Each of those waits for explicit approval.

Goal: Nautilus online at about $0/month hosting, paying only for explicitly authorized Meta Muse usage. Google Cloud is not used.

## Architecture

- **Frontend (static):** the existing Vite build, served by Vercel. It contains no secrets.
- **Public API (deterministic):** simulation and deterministic investigation are pure computation. They make no provider call and use no budget.
- **Live Muse (`api/muse.py`):** one Vercel Python function. `POST /api/muse` runs one investigation to completion inside the request. Vercel functions have no background workers and no persistent local disk, so the run is synchronous, with `maxDuration` 300 s on Hobby.
- **Budget ledger:** Upstash Redis Free over its REST API (`nautilus_api/ledger.py`). Each reserve and settle is one Lua `EVAL`, which Redis runs atomically. Separate function instances therefore share one budget.

## Secrets (server-side only)

| Name | Where it lives | Notes |
| --- | --- | --- |
| `MODEL_API_KEY` | Vercel project env var (Production) | Never sent to the browser, logged, committed or written to artifacts. |
| `NAUTILUS_DEMO_TOKEN` | Vercel project env var (Production) | Bearer token for `/api/muse`. Compared in constant time. |
| `UPSTASH_REDIS_REST_URL` | Vercel project env var | Server-side only. |
| `UPSTASH_REDIS_REST_TOKEN` | Vercel project env var | Server-side only. |
| `NAUTILUS_ALLOWED_ORIGIN` | Vercel project env var (optional) | Exact CORS origin of the frontend. |
| `NAUTILUS_MUSE_MONTHLY_BUDGET_USD` | Vercel project env var (optional) | Default $10. |

## Budget rules

- Rates are the Muse Wonder prices: $4/M input, $0.20/M cached input, $20/M output.
- Each live run reserves its worst case before it starts: 60,000 input and 8,192 output tokens, which is $0.41.
- Caps: $1.00 per UTC day, 10 runs per UTC day, and $10 per UTC month.
- After a successful run the hold is settled to the measured cost from the provider's usage record. Settle never raises a counter above its hold.
- Failed or timed-out runs keep the full worst-case hold. Counters are reduced only by settle, so there is no cleanup job and an unsettled run overcounts rather than undercounts.
- Money is stored as integer micro-dollars so Lua arithmetic is exact.
- Idempotency: reserve and settle are keyed by a per-run ID, so a repeated call applies once.

**Limit of these rules:** these caps are application-side. They do not guarantee a provider-level spending cap. Set a monthly spend cap on the model provider account as the hard stop.

## Limits verified or measured

Vercel Hobby (documented; confirm on the deployed project): Python 3.12 to 3.14, `maxDuration` up to 300 s, 2 GB memory, 500 MB uncompressed bundle, 4.5 MB request body, no persistent disk.

Measured locally:

- NumPy plus SciPy import in about 0.4 s.
- Installed `scipy`, `numpy` and `matplotlib` total about 186 MB before stripping, inside the 500 MB limit. The exact deployed size needs a real Vercel build (`VERCEL_ANALYZE_BUILD_OUTPUT=1`), which has not been run.
- Previous live runs took 78 to 132 s, well inside 300 s. That is a measurement from earlier runs, not a Vercel run. A full live run on Vercel is not yet measured.

Upstash Free: 500K commands per month. A live run uses about 4 commands. The public site uses none.

## Failure behaviour

- Missing or wrong token: 401 before any work.
- Oversized or invalid body: 400.
- Budget exhausted: 429, with no provider call.
- Redis unreachable or unconfigured: 503, fail closed.
- Provider or run error: 500 with a generic message, no detail leaked, and the hold kept.

## Tests

- `tests/test_ledger_redis.py`: caps, run-count cap, monthly cap across days, idempotent reserve and settle, concurrency (40 threads granted exactly the cap), settle clamping, unknown-run no-op, hold expiry, TTLs, fail-closed configuration.
- `tests/test_muse_vercel.py`: end-to-end over HTTP: 401, 400 (invalid and oversized), success settled to measured cost, failure keeps hold and hides detail, 429 on budget and run limits, concurrent requests never exceed the cap, Redis outage gives 503.
- All tests use a real Redis (redislite, test only) behind an Upstash-protocol shim and a mocked provider run. None makes a paid call.

## Steps to deploy (need explicit approval first)

1. Create an Upstash Redis Free database. Copy its REST URL and token into Vercel env vars.
2. Set `MODEL_API_KEY` and `NAUTILUS_DEMO_TOKEN` in Vercel. Do not commit them.
3. Set the model provider's monthly spend cap to $10.
4. Set `NAUTILUS_ALLOWED_ORIGIN` to the frontend origin.
5. Deploy a Vercel preview, check the build output size, check a deterministic route, and check a 401 on `/api/muse`.
6. Only after approval, run one live investigation and check its settled cost in Redis.
7. Promote to production only after the preview checks pass.

## Not yet done

- The Lab UI in the frontend does not call `/api/muse`. It still uses the deterministic jobs API. Wiring the live button is a separate step.
- A real Vercel build and a full live run on Vercel have not been measured.
