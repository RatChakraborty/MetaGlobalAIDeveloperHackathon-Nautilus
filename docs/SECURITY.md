# Nautilus security model

This document describes the controls the code enforces and the limits of those controls. It is not a certification.

## Secrets

- Server secrets are read from environment variables only: `MODEL_API_KEY`, `NAUTILUS_DEMO_TOKEN`, `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`. Names are listed in `.env.example`; values are never committed.
- No real env file is tracked by git. `.env` and `.vercel/` are local only.
- The bundle secret scan (release gate) checks that none of the server secret values appear in `frontend/dist`.
- Provider error bodies are discarded. Only a short, lowercase `error.code` or `error.type` token is kept, and only when it matches a strict identifier pattern (`nautilus/muse.py`, `_safe_error_token`). Messages that could echo a key or request content are never stored.
- A provider response that contains the API key is rejected (`credential_echo`).

## Paid model access

- Paid Muse routes are off by default. Only the exact value `true` for `NAUTILUS_MUSE_ENABLED` opens them.
- Public visitors cannot trigger a paid call. Operator-only routes check `NAUTILUS_DEMO_TOKEN` with a constant-time comparison.
- Each generate makes exactly one HTTP request. Retries are not performed inside the provider client and are not repeated by the host for identical rejected requests.
- Unknown pricing, missing credentials, Redis unavailability and budget exhaustion all fail closed.
- Per-session ceilings for the live Studio run: 120k input tokens, 12k output tokens, 12 requests, and a $0.25 cap (`nautilus/studio_muse_live.py`).
- The aggregate Muse spend authorization is $30 USD, including all prior spend. Recorded spend is listed in `docs/MUSE_LIVE_TEST_RESULTS.md`.

## Model output is untrusted

- Muse proposes; the host validates and decides. A model response cannot grant a Host Recommended decision.
- Structural controller code is never executed from model output. Parameter and source proposals go through the trusted validator (`TOOLS`) and the host's gates.
- Once the candidate budget is spent, the `propose_*` tools are withdrawn from the model.
- Recorded and live Muse content is labelled as model output in the UI.

## Browser

- The browser build reads only `NAUTILUS_*` build variables from `frontend/.env.local`.
- Uploaded public exports are parsed locally and their SHA-256 ledger chain is verified in the browser. Nothing is uploaded.
- Operator notes are shown as unverified testimony.

## CORS and API

- The API allows only the exact origin in `NAUTILUS_ALLOWED_ORIGIN`.
- Request bodies are size-limited; oversized requests are rejected before transport (`request_size_limit`, `response_size_limit`).

## Known limits

- No formal security audit has been performed.
- The shared demo token is a single operator secret, not per-user authentication.
- Public hosting does not protect against someone who holds `NAUTILUS_DEMO_TOKEN`.
- Spend guards depend on the configured budget store. Without Redis the paid path is closed, not metered.
