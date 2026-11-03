# Upstash Redis Free + Vercel setup

Exact steps for the live-Muse deployment. Nothing here requires a credit card, Google Cloud, or
billing verification. Upstash Redis Free and Vercel Hobby are both free tiers.

The only money involved is whatever the Meta Muse API charges for a paid run, and only when the
operator types the demo token and clicks the paid button. Every other path is free.

---

## 1. Create the Upstash Redis Free database

1. Open <https://console.upstash.com> and sign in (GitHub or email). No card is requested for Free.
2. **Create Database**:
   - **Name**: `nautilus-budget`
   - **Type**: Regional
   - **Region**: the one closest to your Vercel functions (for example `us-east-1`, which is
     Vercel's default `iad1`). Keep the two in the same region to hold latency down.
   - **TLS**: enabled (default).
   - **Plan**: **Free**.
3. Create it, then open its **REST API** section (the tab is labelled *REST API*, sometimes under
   *Details* → *REST API*).
4. Copy these two values:
   - `UPSTASH_REDIS_REST_URL` — looks like `https://xxx-yyy-12345.upstash.io`
   - `UPSTASH_REDIS_REST_TOKEN` — a long token string

Use the **REST** URL and token, not the `redis://` connection string. The ledger talks to Upstash
over its REST protocol; the app never opens a raw Redis socket.

Free tier limits that matter here: 10,000 commands/day and 256 MB. One live run costs a handful of
commands (reserve, a few reads, settle), so the run caps below are reached long before the command
limit.

> `UPSTASH_REDIS_REST_URL` must be the bare origin with **no** trailing slash and no path. The
> ledger appends `/pipeline` itself.

---

## 2. Add the four Vercel environment variables

In the Vercel project (`nautilus-demo`) → **Settings** → **Environment Variables**, add all four for
the environments you deploy to (**Preview** for a test deploy, then **Production** when you go live).
Do not add them to a framework public prefix; none of these may be visible to the browser.

| Name | Value | Notes |
| --- | --- | --- |
| `UPSTASH_REDIS_REST_URL` | Upstash REST URL | from step 1 |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash REST token | from step 1 |
| `NAUTILUS_DEMO_TOKEN` | a long random string you generate | the paid-button password |
| `MODEL_API_KEY` | your Meta Muse API key | server-side only |

**Do not prefix any of these with `VITE_`.** A `VITE_` variable is inlined into the browser bundle
by Vite, which would publish the secret. The frontend reads neither secret.

Generate the demo token locally, for example:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Then paste that value into the Vercel variable. It is not stored in the repo. Distribute it to
whoever should be able to spend money, out of band — not in a public README, chat, or screenshot.

Vercel does not reveal a variable again after saving. If you lose the demo token, generate a new one
and update the variable; the old value stops working immediately on the next deployment.

### Optional variables

| Name | Default | Meaning |
| --- | --- | --- |
| `NAUTILUS_ALLOWED_ORIGIN` | same-origin only | Exact frontend origin allowed by CORS, e.g. `https://nautilus-demo-delta.vercel.app`. Set this only when the UI and API are on different origins. A wildcard is never used. |
| `NAUTILUS_MUSE_MONTHLY_BUDGET_USD` | `10.00` | Monthly cap in USD. Lower it for a tighter cap. |

### Changing a variable

Edit it in Settings → Environment Variables, then **redeploy**. Vercel injects variables at build
and deploy time; an existing deployment keeps the old values until it is replaced.

---

## 3. Deploy

The repository deploys as **one** Vercel project:

- `vercel.json` sets `buildCommand` = `cd frontend && npm ci && npm run build` and
  `outputDirectory` = `frontend/dist`, so the static frontend is built and served.
- `api/muse.py` is picked up as a Python serverless function at `/api/muse`
  (with `maxDuration` 300 s).
- `rewrites` sends every non-`/api/` path to `/index.html`, so client-side routes work.
- `api/requirements.txt` pins the Python packages the function needs (`numpy`, `scipy`,
  `matplotlib`). Vercel looks for the nearest requirements file walking up from `api/`, so this one
  is used instead of the repo's root `pyproject.toml`.

CORS: with the frontend and API on the same origin, no CORS configuration is required. If you split
them, set `NAUTILUS_ALLOWED_ORIGIN` to the exact frontend origin. Preflight is answered only for that
origin; other origins get no `Access-Control-Allow-Origin` header.

### Preview deploy (recommended first)

1. Open a PR or push the branch; Vercel builds a Preview deployment.
2. Add the four variables to **Preview**, then redeploy the preview.
3. Open the preview URL. The investigation lab appears when `NAUTILUS_API_ENABLED` is not `false` at
   build time; the free deterministic run works regardless of the API.
4. Enter the demo token in the password field and run a paid investigation **only when you intend to
   spend money**. The token is held in memory for that request, sent as an `Authorization: Bearer`
   header, and cleared from the input afterwards. It is never written to `localStorage`, a cookie, or
   the bundle.

### Production

Promote the verified preview, or deploy the branch after merge. Add the same four variables to
**Production** first.

---

## 4. Verify after deploy

These are all free; none makes a paid call.

```bash
# Unauthenticated request must be refused, and must not leak anything.
curl -i -X POST https://<your-deployment>/api/muse \
  -H 'Content-Type: application/json' -d '{}'
# expect: HTTP/1.1 401  {"error":"Unauthorized"}  and Cache-Control: no-store
```

- Open the site and confirm the deterministic investigation runs and returns a result (free).
- Confirm the paid section is labelled "paid" and states that the token is not stored. The button
  stays enabled; an empty or wrong token is refused by the server with a 401 and runs nothing.
- Check `dist`/browser sources for `NAUTILUS_DEMO_TOKEN`, `MODEL_API_KEY`, `UPSTASH_REDIS_REST` —
  none should appear. (The build check in this repo does the same scan.)

Then, for one paid smoke test with the token:

- One run should succeed and record its measured cost.
- A second immediate run may be refused by the daily cap ($1.00/day, 10 runs/day) — that is the
  cap working, not a failure.
- A wrong token returns 401 and performs no run.

---

## 5. What the caps do and do not do

- The app enforces, per UTC day: **$1.00** and **10 runs**; per UTC month: **$10.00**
  (`NAUTILUS_MUSE_MONTHLY_BUDGET_USD` overrides the monthly figure). Every paid run reserves
  **$0.41** up front, the worst case for the demo limits (60,000 input + 8,192 output tokens at
  Wonder rates), then settles down to the measured cost.
- Reserve and settle are atomic in Upstash, so concurrent requests on separate Vercel instances
  cannot both slip under a cap.
- A fabricated or leaked demo token is still bounded by those caps. Rotating the token stops it.
- **These are application budgets, not a provider-level cap.** The hard stop is the spend limit set
  in the Meta Muse account. Set that in the provider dashboard; nothing in this app can substitute
  for it.

## 6. If something fails

| Symptom | Cause | Fix |
| --- | --- | --- |
| `503 Budget service unavailable` | Upstash URL/token missing or wrong, or Upstash unreachable | Recheck both values; they are REST, not `redis://` |
| Every paid run `401` | demo token differs from `NAUTILUS_DEMO_TOKEN` | Re-enter the current token; rotate if unsure |
| `429 Live-run budget reached` | daily or monthly cap already spent (shared demo bucket) | Wait for the UTC day/month reset, or raise `NAUTILUS_MUSE_MONTHLY_BUDGET_USD` |
| `500 Investigation failed` | provider error; the worst-case hold is kept | Check the Muse account key and spend limit |
| Lab missing | `NAUTILUS_API_ENABLED` set to `false` at build time | Unset it, or set it to `true`, and redeploy (it gates the whole lab, not only the paid form) |
| CORS error in the browser | frontend and API on different origins | Set `NAUTILUS_ALLOWED_ORIGIN` to the exact frontend origin |

A failed or timed-out run keeps its worst-case $0.41 hold until the reservation expires (15
minutes). Counters only move on a successful settle, so the ledger errs toward refusing a run rather
than overspending.
