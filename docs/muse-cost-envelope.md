# Muse controller-engineering cost envelope

This envelope is separate from the $0.41 investigation budget. The engineering session makes more
calls (inspect, propose, validate, trial, inspect results, compare, robustness, finalize), so the
investigation figure does not cover it and is not reused.

## Ceilings (enforced in `nautilus/studio_muse_live.py`, before each request)

| Ceiling | Value | Enforced by |
|---|---|---|
| Model requests per session | 12 | `LiveEnvelope.reserve` |
| Input tokens per session | 60,000 | `LiveEnvelope.reserve` |
| Output tokens per session | 4,000 | `LiveEnvelope.reserve` |
| Spend per session | $0.25 | `LiveEnvelope.reserve` |
| Transcript sent per request | 6,000 characters | `_trim` |
| Wall-clock per session | 180 s | `studio_muse.Budget` |

## Worst-case estimate

- Requests: 12 × (≈ 1,500 input + 600 output) ≈ 18,000 input and 7,200 output tokens in the typical path.
- The 60,000-token input ceiling is 3.3× that estimate, and the 4,000-token output ceiling is below the
  7,200 estimate, so the output ceiling is the binding constraint. The session stops at that ceiling rather
  than running past it.
- Spend is computed from per-token prices read from configuration. **No verified price is configured in
  this branch.** With prices at zero, `reserve` refuses every request, so the live path cannot spend money.

## Status

Live Muse is **disabled**. Three independent blocks apply:

1. `NAUTILUS_MUSE_ENABLED` must be exactly `true`; it defaults to unset.
2. `live_available()` returns False, so the public API never selects the live provider.
3. No verified per-token price is configured, so the spend ceiling cannot be enforced and no request is allowed.

Remaining limitation to clear before enabling: confirm the current provider price sheet, set the two
per-token prices from it, and run one approved low-cost test under a separate authorization. No real
Muse request has been made in this work.
