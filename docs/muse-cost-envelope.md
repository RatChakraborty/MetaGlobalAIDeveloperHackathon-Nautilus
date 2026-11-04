# Muse controller-engineering cost envelope

This envelope is separate from the $0.41 investigation budget. The engineering session makes more
calls (inspect, propose, validate, trial, inspect results, compare, robustness, finalize), so the
investigation figure does not cover it and is not reused.

## Ceilings (enforced in `nautilus/studio_muse_live.py`, before each request)

| Ceiling | Value | Enforced by |
|---|---|---|
| Model requests per session | 12 | `LiveEnvelope.reserve` |
| Input tokens per session | 120,000 | `LiveEnvelope.reserve` |
| Output tokens per session | 12,000 | `LiveEnvelope.reserve` |
| Spend per session | $0.25 | `LiveEnvelope.reserve` |
| Transcript sent per request | 6,000 characters | `_trim` |
| Wall-clock per session | 180 s | `studio_muse.Budget` |

## Worst-case estimate

- Requests: 12 × (≈ 1,500 input + 600 output) ≈ 18,000 input and 7,200 output tokens in the typical path.
- Observed: the second complete-workflow run (10 requests) used 43,541 input and 3,483 output tokens, about
  $0.069, and stopped on the 4,000 output ceiling as the next request would have exceeded it. The output
  ceiling was raised to 12,000 for that reason. The worst case (120,000 in and 12,000 out) is about $0.20,
  still under the $0.25 spend ceiling, which is the binding limit.
- Prices are constants (`SPARK_USD_PER_MTOK_IN/OUT`) used as `LiveEnvelope` defaults. Without a configured price,
  `reserve` refuses every request.

## Status

Live Muse is **disabled**. Three independent blocks apply:

1. `NAUTILUS_MUSE_ENABLED` must be exactly `true`; it defaults to unset.
2. `live_available()` returns False, so the public API never selects the live provider.
3. No verified per-token price is configured, so the spend ceiling cannot be enforced and no request is allowed.

Remaining limitation to clear before enabling: confirm the current provider price sheet, set the two
per-token prices from it, and run one approved low-cost test under a separate authorization. No real
Muse request has been made in this work.
