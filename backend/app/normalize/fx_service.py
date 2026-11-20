"""Live FX Rate Service with SQLite caching and deterministic offline fallback.

Base currency is INR (1.0). All returned values represent ``rate_to_inr``
(how many INR equal 1 unit of the given currency, e.g. USD -> 88.0).
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import sqlite3
from typing import Any
import urllib.request

from ..http_guard import guarded_urlopen
from .normalize import REFERENCE_FX_RATES

logger = logging.getLogger(__name__)

FRANKFURTER_LATEST_URL = "https://api.frankfurter.app/latest?from=INR"

_CREATE_FX_RATES_SQL = """
CREATE TABLE IF NOT EXISTS fx_rates (
    currency    TEXT PRIMARY KEY,
    rate_to_inr REAL NOT NULL,
    as_of_date  TEXT NOT NULL,
    source      TEXT NOT NULL
)
"""


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def ensure_fx_table(conn: sqlite3.Connection) -> None:
    """Create the fx_rates cache table if it does not already exist."""
    conn.execute(_CREATE_FX_RATES_SQL)
    conn.commit()


def load_cached_fx_rates(conn: sqlite3.Connection) -> dict[str, float]:
    """Load cached FX rates from the fx_rates table."""
    ensure_fx_table(conn)
    rows = conn.execute("SELECT currency, rate_to_inr FROM fx_rates").fetchall()
    return {str(row[0]).upper(): float(row[1]) for row in rows}


def cache_fx_rates(
    conn: sqlite3.Connection,
    rates: dict[str, float],
    as_of_date: str | None = None,
    source: str = "reference",
) -> None:
    """Persist FX rates into the fx_rates cache table."""
    ensure_fx_table(conn)
    date_str = as_of_date or _today_iso()
    rows = [
        (str(ccy).upper(), float(rate), date_str, source)
        for ccy, rate in rates.items()
    ]
    conn.executemany(
        "INSERT OR REPLACE INTO fx_rates (currency, rate_to_inr, as_of_date, source) "
        "VALUES (?, ?, ?, ?)",
        rows,
    )
    conn.commit()


def fetch_live_fx_rates(
    url: str = FRANKFURTER_LATEST_URL,
    timeout: float = 3.0,
) -> tuple[dict[str, float], str]:
    """Fetch latest FX rates from Frankfurter/ECB and invert to rate_to_inr.

    Frankfurter with ``from=INR`` returns ``1 INR = X <CCY>``; we invert each
    positive rate to ``1 <CCY> = (1 / X) INR``.
    """
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    # SSRF guard: https-only, hostname denylist, public-IP resolution,
    # redirect targets re-validated (see app.http_guard).
    with guarded_urlopen(req, timeout=timeout) as resp:
        payload: dict[str, Any] = json.loads(resp.read().decode("utf-8"))

    raw_rates = payload.get("rates")
    if not isinstance(raw_rates, dict) or not raw_rates:
        raise ValueError("Frankfurter response missing 'rates' dictionary")

    rates: dict[str, float] = {"INR": 1.0}
    for ccy, per_inr in raw_rates.items():
        val = float(per_inr)
        if val > 0:
            rates[str(ccy).upper()] = round(1.0 / val, 6)

    as_of_date = str(payload.get("date") or _today_iso())
    return rates, as_of_date


def get_fx_rates(
    conn: sqlite3.Connection | None = None,
    fetch_live: bool = False,
    timeout: float = 3.0,
) -> dict[str, float]:
    """Return FX rates (base INR=1.0) using live fetch, DB cache, or offline fallback.

    Resolution order:
    1. If ``fetch_live`` is True, attempt Frankfurter/ECB HTTP fetch. On success,
       cache to ``conn`` (if provided) and return merged rates.
    2. If ``conn`` is provided and ``fx_rates`` has cached rows, return them
       (merged on top of ``REFERENCE_FX_RATES`` with ``INR=1.0``).
    3. Otherwise return ``REFERENCE_FX_RATES`` (and seed ``fx_rates`` if ``conn``
       is provided).
    """
    if fetch_live:
        try:
            live_rates, as_of_date = fetch_live_fx_rates(timeout=timeout)
            merged = dict(REFERENCE_FX_RATES)
            merged.update(live_rates)
            merged["INR"] = 1.0
            if conn is not None:
                cache_fx_rates(conn, merged, as_of_date=as_of_date, source="frankfurter")
            return merged
        except Exception as exc:
            logger.warning("Live FX fetch failed (%s); falling back to cache/reference.", exc)

    if conn is not None:
        cached = load_cached_fx_rates(conn)
        if cached:
            merged = dict(REFERENCE_FX_RATES)
            merged.update(cached)
            merged["INR"] = 1.0
            return merged
        fallback = dict(REFERENCE_FX_RATES)
        cache_fx_rates(conn, fallback, as_of_date=_today_iso(), source="reference")
        return fallback

    return dict(REFERENCE_FX_RATES)
