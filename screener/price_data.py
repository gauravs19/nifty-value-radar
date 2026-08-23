"""Bulk historical price fetch via yfinance, chunked to stay reliable across 500 tickers."""
import time

import pandas as pd
import yfinance as yf

CHUNK_SIZE = 50


def fetch_history(yf_symbols, period="1y", pause=1.0):
    """Returns dict: yf_symbol -> DataFrame(Open,High,Low,Close,Volume), ascending date index."""
    out = {}
    for i in range(0, len(yf_symbols), CHUNK_SIZE):
        chunk = yf_symbols[i:i + CHUNK_SIZE]
        try:
            df = yf.download(chunk, period=period, group_by="ticker", threads=True,
                              progress=False, auto_adjust=True)
        except Exception as e:
            print(f"chunk fetch failed ({chunk[:3]}...): {e}")
            continue
        for sym in chunk:
            try:
                sub = df[sym] if isinstance(df.columns, pd.MultiIndex) else df
                sub = sub.dropna(how="all")
                if not sub.empty:
                    out[sym] = sub
            except KeyError:
                continue
        time.sleep(pause)
    return out


def fetch_benchmark_return(symbol="^NSEI", lookback_days=63):
    """Returns the benchmark's % return over the last lookback_days trading
    days, or None if unavailable -- used as the relative-strength baseline."""
    try:
        hist = yf.Ticker(symbol).history(period="1y", auto_adjust=True)
        closes = hist["Close"].dropna()
        if len(closes) <= lookback_days:
            return None
        return (closes.iloc[-1] / closes.iloc[-lookback_days - 1] - 1) * 100
    except Exception:
        return None
