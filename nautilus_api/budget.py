"""Dollar budget for live Muse runs, priced from measured provider token usage.

Rates are the published Muse Wonder (muse-wonder-1.0) prices in USD per million tokens.
Reasoning tokens are billed at the output rate, so only output_tokens is priced here.

Reservations are made before a run starts, at the worst case the run's limits allow.
After the run, the reservation is settled to the measured cost. Application counters are
not a provider billing cap; the provider monthly spend cap remains the hard stop.
"""
import math
import os
import time

WONDER_RATES = {"input": 4.00, "cached_input": 0.20, "output": 20.00}
MONTHLY_BUDGET_USD = 10.00
# The demo token is one shared credential, so every live run draws from one bucket.
DEMO_BUCKET = "demo"
PER_USER_DAILY_RUNS = 10
PER_USER_DAILY_USD = 1.00

# Worst case for one live run at DEMO_MUSE_LIMITS: 8192 output and 60000 input tokens.
WORST_CASE_INPUT_TOKENS = 60000
WORST_CASE_OUTPUT_TOKENS = 8192


def cost_usd(usage, rates=WONDER_RATES):
    """Dollar cost of one provider usage dict. Missing values count as zero."""
    cached = int(usage.get("cached_input_tokens", 0) or 0)
    total_in = int(usage.get("input_tokens", 0) or 0)
    out = int(usage.get("output_tokens", 0) or 0)
    uncached = max(0, total_in - cached)
    return (uncached * rates["input"] + cached * rates["cached_input"] + out * rates["output"]) / 1_000_000


def reservation_usd(rates=WONDER_RATES):
    """Worst-case reserve for one live run, charged before it starts."""
    return cost_usd({"input_tokens": WORST_CASE_INPUT_TOKENS, "output_tokens": WORST_CASE_OUTPUT_TOKENS}, rates)


def month_key(now=None):
    return time.strftime("%Y-%m", time.gmtime(now))


def day_key(now=None):
    return time.strftime("%Y-%m-%d", time.gmtime(now))


def rounded_up_cents(amount):
    """Round a reservation up to the next cent so the ledger never undercounts."""
    return math.ceil(amount * 100) / 100


def monthly_budget_usd():
    try:
        return float(os.environ.get("NAUTILUS_MUSE_MONTHLY_BUDGET_USD", MONTHLY_BUDGET_USD))
    except ValueError:
        return 0.0
