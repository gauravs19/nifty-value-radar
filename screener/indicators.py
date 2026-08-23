"""Technical indicator calculations on a per-ticker OHLCV DataFrame."""
import numpy as np
import pandas as pd


def sma(series, window):
    return series.rolling(window=window, min_periods=window).mean()


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_indicators(hist: pd.DataFrame) -> pd.DataFrame:
    """hist must have a 'Close' and 'Volume' column, DatetimeIndex ascending."""
    out = hist.copy()
    out["sma50"] = sma(out["Close"], 50)
    out["sma200"] = sma(out["Close"], 200)
    out["rsi14"] = rsi(out["Close"], 14)
    out["vol_avg20"] = out["Volume"].rolling(20, min_periods=20).mean()
    out["52w_high"] = out["Close"].rolling(252, min_periods=60).max()
    out["52w_low"] = out["Close"].rolling(252, min_periods=60).min()
    return out
