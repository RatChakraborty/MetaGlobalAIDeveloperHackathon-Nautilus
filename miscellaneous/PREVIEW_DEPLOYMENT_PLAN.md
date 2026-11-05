# Nautilus — Vercel Preview Deployment Plan

Status: **prepared, not executed.** Branch `feature/nautilus-integrated-product` is **not pushed to
origin**, no Vercel deployment has been created from this branch, and Production is untouched.

## 1. What this deployment is

One Vercel project serves two surfaces from one build:

- static Vite frontend from `frontend/dist` (`buildCommand` + `outputDirectory` in `vercel.json`),
- three Python functions from `api/`:
  - `POST /api/v1/simulations` — free deterministic simulation,
  - `POST /api/v1/investigations` — free deterministic investigation, run to completion inside the
    request and returned as an already-`succeeded` job,
  - `POST /api/muse` — paid live run, behind the operator token, the Redis ledger and the caps.

`rewrites` maps every path that does not start with `api/` to `/index.html`, so the SPA keeps deep
links and `/api/muse` is still handled by the function.

## 2. Environment variables the code actually reads

Server-side, from `api/`, `nautilus/` and `nautilus_api/`:

| Name | Required | Purpose |
|---|---|---|
| `MODEL_API_KEY` | yes, for a live run | Muse credential; read only by the server provider adapter |
| `NAUTILUS_DEMO_TOKEN` | yes | operator bearer token; unset means every live request is refused (401) |
| `UPSTASH_REDIS_REST_URL` | yes | budget ledger endpoint |
| `UPSTASH_REDIS_REST_TOKEN` | yes | budget ledger credential |
| `NAUTILUS_ALLOWED_ORIGIN` | optional | only for a split frontend/API origin; same-origin needs nothing |
| `NAUTILUS_MUSE_MONTHLY_BUDGET_USD` | optional | default 10.00 |
| `NAUTILUS_MUSE_DAILY_LIMIT` | optional | default 10 runs/day |
| `NAUTILUS_MUSE_MODEL` | optional | **leave unset.** Any value other than `muse-wonder-1.0` makes live runs refuse, by design |
| `NAUTILUS_MUSE_REASONING_EFFORT` | optional | leave at the default |

The frontend reads no secret at build time. `NAUTILUS_API_ENABLED` (`false` disables the whole
Simulation Lab tab) and `NAUTILUS_API_BASE` (empty = same origin) are build-time public settings,
not secrets.

## 3. Pre-flight, to run before deployment

```bash
# 1. names and scopes (values are never printed; Secret-type values cannot be read back)
vercel env ls preview
vercel env ls production

# 2. production branch must be main, so a feature branch can only produce a Preview
vercel project inspect nautilus-demo

# 3. confirm the linked project and that nothing is staged for production
vercel whoami
```

Checks that must all hold:

- [ ] All four required names appear in the **Preview** scope, spelled exactly as in the table.
- [ ] The project's Production Branch is `main`.
- [ ] No `--prod` flag is used at any point below.
- [ ] `NAUTILUS_MUSE_MODEL` is unset (or exactly `muse-wonder-1.0`).

## 4. Deployment procedure (needs explicit approval)

Option A — Git preview (recommended: matches how the project already deploys):

```bash
git push origin feature/nautilus-integrated-product
```

Vercel then builds a **Preview** deployment for the branch. Pushing this branch cannot deploy
Production as long as the Production Branch is `main`; Production only moves when `main` is pushed.

Option B — CLI preview upload (no Git push):

```bash
vercel deploy            # preview only; never add --prod
```

Either way, stop here until the deployment reports ready, and record its preview URL.

## 5. Keep paid execution out of the validation window

The preview function is reachable and protected only by the bearer token plus the Redis caps. For
the validation phase, either of these keeps paid execution inaccessible:

- do not share the preview URL or token outside the operator group, and do not enter a token; or
- stronger: set `NAUTILUS_DEMO_TOKEN` to an empty value in the **Preview** scope only for the
  validation window (`vercel env rm NAUTILUS_DEMO_TOKEN preview`, redeploy preview), then restore
  it. With the variable unset the handler fails closed with 401 and no model call is possible.

Nothing else needs to change: the reservation is taken before the model is called, so a refused
token cannot spend.

## 6. Non-paid validation after the preview is ready

```bash
BASE=https://<preview-url>
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/"                     # 200, HTML shell
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/some/deep/link"       # 200, SPA fallback
curl -sS -X POST "$BASE/api/muse" -H 'Content-Type: application/json' -d '{}'   # 401
curl -sS -X POST "$BASE/api/muse" -H 'Authorization: Bearer wrong' -d '{}'      # 401
curl -sS -X POST "$BASE/api/muse" -H "Authorization: Bearer $TOKEN" -d '{oops'   # 400, and no run
```

```bash
curl -sS -X POST "$BASE/api/v1/simulations" -H 'Content-Type: application/json' \
  -d '{"scenario":{"current_y":1.0},"seed":5,"duration_s":4.0}' | head -c 400
curl -sS -X POST "$BASE/api/v1/investigations" -H 'Content-Type: application/json' \
  -d '{"scenario":{"current_y":1.0},"seed":5,"duration_s":4.0}' \
  | python -c 'import json,sys;j=json.load(sys.stdin)["job"];print(j["status"], len(j["result"]["investigation"]["ledger"]))'
```

The investigation must print `succeeded` with a non-zero ledger length; that is the proof the real
Python path ran, whereas a 200 alone is not.

Confirm in the browser: the app loads, tabs navigate, Simulation Lab is present, the free
deterministic simulation and the free deterministic investigation both run, and the browser console
is clean. Treat a 200 alone as insufficient: the free investigation must return real observations,
a diagnosis and a hash-linked evidence ledger, which proves the Python path executed.

Do **not** call `/api/muse` with a valid token during this phase. The first live run is a separate,
separately authorised step.

## 7. Rollback

A preview deployment changes nothing in Production. To withdraw it: delete that deployment in the
Vercel dashboard, or redeploy preview from an earlier commit. No database state needs undoing for a
non-paid validation, because no reservation is created unless a live run starts.

## 8. Capacity facts that bound this design (Vercel Hobby)

- Function duration: 300 s default **and** maximum on Hobby; exceeding it returns
  `FUNCTION_INVOCATION_TIMEOUT`. `maxDuration: 300` is therefore valid but grants nothing extra,
  and the investigator's own `wall_s` is set to 240 s to stop before the ceiling.
- Python bundle: 500 MB uncompressed (250 MB for other runtimes); the code itself is about 2.2 MB.
- Request and response bodies: 4.5 MB maximum.
- Memory/CPU: 2 GB / 1 vCPU, fixed on Hobby.
- No persistent disk and no surviving background work: all state lives in Upstash Redis, and one
  request runs its investigation to completion synchronously.

## 9. Secret-rotation warning: interpretation

Vercel shows a rotation recommendation, not a detection of leaked Nautilus credentials. The
meaningful Vercel distinction is the per-variable type:

- **Config** — the value stays readable to team members who can open it.
- **Secret** — write-only after saving; it can be replaced but not read back.

Vercel's April 2026 security bulletin reported that non-sensitive (Config) environment variables
were the ones compromised, and advised reviewing and rotating every credential that was not marked
sensitive, and using the sensitive/Secret setting from then on. That matches a rotation advisory on
three credential variables.

Recommended user-side action, since these are already configured:

1. Regenerate `NAUTILUS_DEMO_TOKEN` locally (e.g. `python -c "import secrets;print(secrets.token_urlsafe(32))"`).
2. Rotate `MODEL_API_KEY` in the Meta provider console.
3. Rotate `UPSTASH_REDIS_REST_TOKEN` in Upstash.
4. Update each value **before** revoking the old one, then set each variable's type to **Secret** so
   it cannot be read back.
5. Redeploy preview and re-check the four names.

Nothing here requires a code change. Rotation is deliberately left to the operator; no credential
was read, printed or written by this work.

## 10. Cost model

- Vercel Hobby: $0, including previews, within the plan's included usage.
- Upstash Free: $0 within the free command and storage allowance.
- Muse: **not** capped by this application at the provider. The app enforces $1.00/day, 10 runs/day
  and $10.00/month against its own ledger, one $0.41 worst-case reservation per run. In the
  application's accounting only, that bounds a month at about $10. Whether Meta enforces a hard
  $10 monthly spend limit on the account has **not** been verified, so total provider spend is not
  guaranteed to stay under $10.

## 11. Security incident log

- Date: during the "verify the budget reservation" work that preceded preview preparation.
- What happened: one real Muse request was made from a verification probe, because that probe called
  the live investigator instead of a stub while `MODEL_API_KEY` was present in the shell.
- Reported usage: 8,547 input tokens and 2,048 output tokens, from one response marked incomplete.
- Authorisation: **not** authorised. Disclosed to the operator afterwards and acknowledged; no
  further paid requests are authorised.
- Remediation: Muse tests now run with the provider stubbed and the key removed from the environment;
  the full suite is executed with `MODEL_API_KEY` unset.
- Credentials: no key, token or provider response body is recorded in this repository, this log, or
  any log produced by the tests.
