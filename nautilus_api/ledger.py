"""Budget ledger for live Muse runs, stored in Upstash Redis over its REST API (stdlib only).

Why Redis: Vercel functions have no persistent local disk, and separate function instances must
share one budget. Each reserve and settle is a single Lua script. Redis runs a script atomically,
so the cap check and the increment cannot interleave with another request or instance.

Money is stored as integer micro-dollars (1e-6 USD) so the Lua arithmetic is exact.

Keys (bucket = DEMO_BUCKET, day = YYYY-MM-DD UTC, month = YYYY-MM UTC):
  nautilus:{bucket}:day:{day}     hash  runs, usd          committed daily counters
  nautilus:month:{month}          string usd               committed monthly counter
  nautilus:run:{run_id}           hash  bucket, day, month, usd, state   one reservation
      state = "held" | "settled"; held holds expire after RESERVATION_TTL_S

Idempotency: reserve(run_id) twice returns the same answer and adds one hold. settle(run_id)
twice applies once. Failure recovery: a run that times out or crashes before settling keeps its
full worst-case amount in the daily and monthly counters. Counters are never reduced except by
settle, so an expired or unsettled hold stays counted. That overcounts rather than undercounts,
which is the conservative direction and needs no cleanup job.

Environment:
  UPSTASH_REDIS_REST_URL    e.g. https://xxxx.upstash.io   (server-side only)
  UPSTASH_REDIS_REST_TOKEN  bearer token                   (server-side only)
"""
import json
import os
import time
import urllib.request

from nautilus_api.budget import day_key, month_key

RESERVATION_TTL_S = 900  # longer than the 300 s function limit, so a held run cannot outlive its window
DAILY_KEEP_S = 3 * 24 * 3600
MONTHLY_KEEP_S = 40 * 24 * 3600
MICRO = 1_000_000

# KEYS: 1 daily hash, 2 monthly string, 3 run hash
# ARGV (1-based, matches reserve()): 1 amount_micro, 2 daily_runs, 3 daily_cap_micro,
#   4 monthly_cap_micro, 5 hold_ttl_s, 6 daily_keep_s, 7 monthly_keep_s
RESERVE_LUA = """
local existing = redis.call('HGET', KEYS[3], 'state')
if existing then
  return {1, redis.call('HGET', KEYS[3], 'granted')}
end
local runs = tonumber(redis.call('HGET', KEYS[1], 'runs') or '0')
local daily = tonumber(redis.call('HGET', KEYS[1], 'usd') or '0')
local monthly = tonumber(redis.call('GET', KEYS[2]) or '0')
local amount = tonumber(ARGV[1])
if runs + 1 > tonumber(ARGV[2]) or daily + amount > tonumber(ARGV[3]) or monthly + amount > tonumber(ARGV[4]) then
  redis.call('HSET', KEYS[3], 'state', 'refused', 'granted', '0', 'usd', '0')
  redis.call('EXPIRE', KEYS[3], ARGV[5])
  return {0, '0'}
end
redis.call('HINCRBY', KEYS[1], 'runs', 1)
redis.call('HINCRBY', KEYS[1], 'usd', ARGV[1])
redis.call('INCRBY', KEYS[2], ARGV[1])
redis.call('EXPIRE', KEYS[1], ARGV[6])
redis.call('EXPIRE', KEYS[2], ARGV[7])
redis.call('HSET', KEYS[3], 'state', 'held', 'granted', '1', 'usd', ARGV[1])
redis.call('EXPIRE', KEYS[3], ARGV[5])
return {1, '1'}
"""

# KEYS: 1 daily hash, 2 monthly string, 3 run hash
# ARGV: actual_micro, daily_keep, monthly_keep
# A run that is missing, expired or already settled is a no-op. The hold's value is the amount
# that was added at reserve time, so the counters move by exactly the difference.
SETTLE_LUA = """
local state = redis.call('HGET', KEYS[3], 'state')
if state ~= 'held' then
  return 0
end
local held = tonumber(redis.call('HGET', KEYS[3], 'usd'))
local actual = math.min(tonumber(ARGV[1]), held)
local delta = actual - held
if delta ~= 0 then
  redis.call('HINCRBY', KEYS[1], 'usd', string.format('%d', delta))
  redis.call('INCRBY', KEYS[2], string.format('%d', delta))
end
redis.call('HSET', KEYS[3], 'state', 'settled', 'usd', string.format('%d', actual))
redis.call('EXPIRE', KEYS[3], ARGV[2])
return 1
"""


def _url():
    return os.environ.get("UPSTASH_REDIS_REST_URL", "").rstrip("/")


def _token():
    return os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")


def _command(*args):
    """Send one Redis command over the REST API. Raises on transport or Redis errors."""
    url, token = _url(), _token()
    if not url or not token:
        raise RuntimeError("Upstash Redis is not configured")
    req = urllib.request.Request(url, data=json.dumps(list(args)).encode(),
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = json.load(resp)
    if "error" in body:
        raise RuntimeError("Redis error")
    return body.get("result")


def _keys(bucket, run_id, now):
    day, month = day_key(now), month_key(now)
    return (f"nautilus:{bucket}:day:{day}", f"nautilus:month:{month}", f"nautilus:run:{run_id}")


def _micro(usd):
    return int(round(usd * MICRO))


def reserve(bucket, reserve_usd, *, run_id, daily_runs, daily_usd, monthly_usd, now=None):
    """Reserve worst-case dollars for one run. Returns True only if it fits every cap.

    Idempotent: repeating the same run_id returns the original decision without a second hold.
    """
    if not run_id:
        raise ValueError("run_id is required")
    now = time.time() if now is None else now
    daily_key, monthly_key, run_key = _keys(bucket, run_id, now)
    result = _command("EVAL", RESERVE_LUA, "3", daily_key, monthly_key, run_key,
                      str(_micro(reserve_usd)), str(int(daily_runs)), str(_micro(daily_usd)),
                      str(_micro(monthly_usd)), str(RESERVATION_TTL_S), str(DAILY_KEEP_S),
                      str(MONTHLY_KEEP_S))
    return str(result[1]) == "1"


def settle(bucket, run_id, actual_usd, *, now=None):
    """Replace a held reservation with the measured cost. Idempotent; a missing hold is a no-op."""
    if not run_id:
        raise ValueError("run_id is required")
    now = time.time() if now is None else now
    daily_key, monthly_key, run_key = _keys(bucket, run_id, now)
    _command("EVAL", SETTLE_LUA, "3", daily_key, monthly_key, run_key,
             str(_micro(max(0.0, actual_usd))), str(DAILY_KEEP_S), str(MONTHLY_KEEP_S))
