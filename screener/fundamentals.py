"""Fetches and caches slow-changing fundamental data (P/E, P/B, ROE, D/E) per ticker.

Fundamentals don't move daily, so we refresh this cache on a schedule (weekly)
instead of hitting yfinance's `.info` endpoint (slow, one request per ticker)
on every daily run.
"""
import csv
import os
import time

import yfinance as yf

from screener.quality import fetch_quality_inputs, coffee_can_flag, piotroski_lite_score

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CACHE_CSV = os.path.join(DATA_DIR, "fundamentals_cache.csv")

FIELDS = [
    "yf_symbol", "trailingPE", "priceToBook", "returnOnEquity",
    "debtToEquity", "coffeeCan", "coffeeCanReasons", "piotroskiScore", "fetched_at",
]


def refresh_cache(yf_symbols, sleep_between=0.3):
    """Fetches .info + annual statements per symbol and writes the cache CSV.
    Slow (~2 requests/symbol) -- meant to run weekly, not daily."""
    rows = []
    for i, sym in enumerate(yf_symbols):
        row = {"yf_symbol": sym, "trailingPE": None, "priceToBook": None,
               "returnOnEquity": None, "debtToEquity": None,
               "coffeeCan": False, "coffeeCanReasons": "", "piotroskiScore": None,
               "fetched_at": int(time.time())}
        try:
            info = yf.Ticker(sym).info
            row["trailingPE"] = info.get("trailingPE")
            row["priceToBook"] = info.get("priceToBook")
            row["returnOnEquity"] = info.get("returnOnEquity")
            row["debtToEquity"] = info.get("debtToEquity")
        except Exception:
            pass
        try:
            statements = fetch_quality_inputs(sym)
            ok, reasons = coffee_can_flag(statements)
            score, _ = piotroski_lite_score(statements)
            row["coffeeCan"] = bool(ok)
            row["coffeeCanReasons"] = "; ".join(reasons)
            row["piotroskiScore"] = score
        except Exception:
            pass
        rows.append(row)
        time.sleep(sleep_between)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CACHE_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def load_cache():
    """Returns dict: yf_symbol -> fundamentals dict. Empty dict if no cache yet."""
    if not os.path.exists(CACHE_CSV):
        return {}
    out = {}
    with open(CACHE_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            def _f(v):
                try:
                    return float(v) if v not in (None, "", "None") else None
                except ValueError:
                    return None
            out[r["yf_symbol"]] = {
                "trailingPE": _f(r.get("trailingPE")),
                "priceToBook": _f(r.get("priceToBook")),
                "returnOnEquity": _f(r.get("returnOnEquity")),
                "debtToEquity": _f(r.get("debtToEquity")),
                "coffeeCan": (r.get("coffeeCan") == "True"),
                "coffeeCanReasons": r.get("coffeeCanReasons") or "",
                "piotroskiScore": int(float(r["piotroskiScore"])) if r.get("piotroskiScore") not in (None, "", "None") else None,
                "fetched_at": int(float(r["fetched_at"])) if r.get("fetched_at") else 0,
            }
    return out


def cache_age_days():
    """Age of the cache file in days, or None if it doesn't exist."""
    if not os.path.exists(CACHE_CSV):
        return None
    return (time.time() - os.path.getmtime(CACHE_CSV)) / 86400
