"""Atomicity, idempotency and recovery tests for the Redis budget ledger.

Runs against a real Redis server (redislite, test-only) behind a local HTTP shim that speaks
Upstash's REST protocol (POST a JSON array of command arguments), so the production
`ledger._command` path is what gets exercised.
"""
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

redislite = pytest.importorskip("redislite")
import redis  # noqa: E402

from nautilus_api import budget, ledger  # noqa: E402

CAPS = dict(daily_runs=10, daily_usd=1.00, monthly_usd=10.00)
NOW = 1_770_000_000  # fixed UTC instant so the day and month keys are stable


@pytest.fixture()
def rest(monkeypatch, tmp_path):
    server = redislite.Redis(str(tmp_path / "redis.db"))

    class Shim(BaseHTTPRequestHandler):
        def do_POST(self):
            args = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            def plain(value):
                if isinstance(value, bytes):
                    return value.decode()
                if isinstance(value, list):
                    return [plain(v) for v in value]
                return value

            try:
                body = {"result": plain(server.execute_command(*args))}
            except redis.ResponseError as exc:
                body = {"error": str(exc)}
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            return

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Shim)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", f"http://127.0.0.1:{httpd.server_address[1]}")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "test-token")
    yield server
    httpd.shutdown()
    server.close()


def test_reserve_refuses_past_daily_usd_cap(rest):
    assert ledger.reserve("demo", 0.41, run_id="a", now=NOW, **CAPS)
    assert ledger.reserve("demo", 0.41, run_id="b", now=NOW, **CAPS)
    assert not ledger.reserve("demo", 0.41, run_id="c", now=NOW, **CAPS)


def test_reserve_refuses_past_daily_run_count(rest):
    for i in range(3):
        assert ledger.reserve("demo", 0.01, run_id=f"r{i}", now=NOW, daily_runs=3, daily_usd=5, monthly_usd=50)
    assert not ledger.reserve("demo", 0.01, run_id="r3", now=NOW, daily_runs=3, daily_usd=5, monthly_usd=50)


def test_reserve_refuses_past_monthly_cap_across_days(rest):
    assert ledger.reserve("demo", 4.00, run_id="m1", now=NOW, daily_runs=99, daily_usd=99, monthly_usd=5.00)
    next_day = NOW + 86400
    assert not ledger.reserve("demo", 2.00, run_id="m2", now=next_day, daily_runs=99, daily_usd=99, monthly_usd=5.00)


def test_reserve_is_idempotent_per_run_id(rest):
    assert ledger.reserve("demo", 0.41, run_id="same", now=NOW, **CAPS)
    assert ledger.reserve("demo", 0.41, run_id="same", now=NOW, **CAPS)
    day = f"nautilus:demo:day:{ledger.day_key(NOW)}"
    assert int(rest.hget(day, "runs")) == 1
    assert int(rest.hget(day, "usd")) == 410_000


def test_refused_run_id_stays_refused_on_retry(rest):
    assert ledger.reserve("demo", 1.50, run_id="big", now=NOW, **CAPS) is False
    assert ledger.reserve("demo", 0.01, run_id="big", now=NOW, **CAPS) is False


def test_concurrent_reserves_cannot_exceed_cap(rest):
    """Many simultaneous reservations: exactly the number that fits is granted."""
    def attempt(i):
        return ledger.reserve("demo", 0.41, run_id=f"c{i}", now=NOW, **CAPS)

    with ThreadPoolExecutor(max_workers=16) as pool:
        granted = sum(pool.map(attempt, range(40)))
    # $1.00 daily cap at $0.41 each: exactly two fit ($0.82), a third would reach $1.23.
    assert granted == 2
    day = f"nautilus:demo:day:{ledger.day_key(NOW)}"
    assert int(rest.hget(day, "usd")) == 820_000


def test_settle_moves_hold_to_actual_and_frees_room(rest):
    assert ledger.reserve("demo", 0.41, run_id="s1", now=NOW, **CAPS)
    ledger.settle("demo", "s1", 0.18, now=NOW)
    day = f"nautilus:demo:day:{ledger.day_key(NOW)}"
    assert int(rest.hget(day, "usd")) == 180_000
    # Freed room lets a later run through.
    assert ledger.reserve("demo", 0.41, run_id="s2", now=NOW, **CAPS)


def test_settle_is_idempotent(rest):
    assert ledger.reserve("demo", 0.41, run_id="once", now=NOW, **CAPS)
    ledger.settle("demo", "once", 0.10, now=NOW)
    ledger.settle("demo", "once", 0.10, now=NOW)
    ledger.settle("demo", "once", 0.41, now=NOW)
    day = f"nautilus:demo:day:{ledger.day_key(NOW)}"
    assert int(rest.hget(day, "usd")) == 100_000


def test_settle_never_raises_counters_above_hold(rest):
    assert ledger.reserve("demo", 0.10, run_id="low", now=NOW, **CAPS)
    ledger.settle("demo", "low", 9.00, now=NOW)  # actual above hold is clamped to the hold
    day = f"nautilus:demo:day:{ledger.day_key(NOW)}"
    assert int(rest.hget(day, "usd")) == 100_000


def test_settle_of_unknown_run_is_a_noop(rest):
    ledger.settle("demo", "never-reserved", 0.50, now=NOW)
    day = f"nautilus:demo:day:{ledger.day_key(NOW)}"
    assert rest.hget(day, "usd") is None


def test_timed_out_run_keeps_worst_case_hold(rest):
    """A run that never settles stays counted at its full reservation (conservative)."""
    assert ledger.reserve("demo", 0.41, run_id="lost", now=NOW, **CAPS)
    assert ledger.reserve("demo", 0.41, run_id="other", now=NOW, **CAPS)
    assert not ledger.reserve("demo", 0.41, run_id="blocked", now=NOW, **CAPS)


def test_hold_expiry_does_not_release_budget(rest):
    """After the reservation TTL the run key is gone, but the daily counter is not reduced."""
    assert ledger.reserve("demo", 0.41, run_id="stale", now=NOW, **CAPS)
    rest.delete(f"nautilus:run:stale")
    day = f"nautilus:demo:day:{ledger.day_key(NOW)}"
    assert int(rest.hget(day, "usd")) == 410_000
    ledger.settle("demo", "stale", 0.0, now=NOW)  # late settle of an expired hold is a no-op
    assert int(rest.hget(day, "usd")) == 410_000


def test_counters_keep_at_least_the_period_length(rest):
    assert ledger.reserve("demo", 0.10, run_id="ttl", now=NOW, **CAPS)
    day = f"nautilus:demo:day:{ledger.day_key(NOW)}"
    month = f"nautilus:month:{ledger.month_key(NOW)}"
    assert rest.ttl(day) >= 2 * 24 * 3600 and rest.ttl(month) >= 30 * 24 * 3600


def test_missing_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        ledger.reserve("demo", 0.41, run_id="x", now=NOW, **CAPS)


def test_run_id_required(rest):
    with pytest.raises(ValueError):
        ledger.reserve("demo", 0.41, run_id="", now=NOW, **CAPS)
