"""Historical backtest for the two PURE TECHNICAL strategies (trend-pullback and
swing) against real multi-year price history.

IMPORTANT LIMITATION: the value/quality strategies (value_trend_combo, pure_value,
coffee_can_compounder) are NOT backtested here. yfinance only exposes today's P/E,
ROE etc., not what they were on a historical date -- backtesting them with today's
fundamentals against yesterday's prices would be look-ahead bias (using information
that wasn't actually available at the time). Only strategies that depend purely on
price/volume history, which we do have historically, get a real backtest.

Also note: today's Nifty 500 list excludes stocks that were delisted or dropped for
poor performance (survivorship bias), so even these results will be somewhat
optimistic versus what a live signal stream would have produced.

Usage: python scripts/backtest.py [--sample N] [--years 5]
"""
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screener.universe import load_universe
from screener.price_data import fetch_history
from screener.indicators import compute_indicators
from screener.strategies import trend_pullback_signal, swing_technical_signal

HOLDING_PERIODS = {"3mo": 63, "6mo": 126, "12mo": 252}


def forward_return(closes, i, n_days):
    if i + n_days >= len(closes):
        return None
    entry, exit_ = closes.iloc[i], closes.iloc[i + n_days]
    if entry <= 0:
        return None
    return (exit_ - entry) / entry


def backtest_strategy(name, signal_fn, histories):
    all_returns = {k: [] for k in HOLDING_PERIODS}
    n_signals = 0
    for sym, hist in histories.items():
        if len(hist) < 300:
            continue
        indicators = compute_indicators(hist)
        closes = indicators["Close"]
        for i in range(252, len(indicators) - 1):  # need warmup for 200-DMA
            row = indicators.iloc[i]
            fired, _ = signal_fn(row)
            if not fired:
                continue
            n_signals += 1
            for label, n_days in HOLDING_PERIODS.items():
                r = forward_return(closes, i, n_days)
                if r is not None:
                    all_returns[label].append(r)
    return name, n_signals, all_returns


def summarize(name, n_signals, all_returns):
    print(f"\n=== {name} ===")
    print(f"Total signals fired: {n_signals}")
    for label, rets in all_returns.items():
        if not rets:
            print(f"  {label}: no completed samples yet")
            continue
        avg = sum(rets) / len(rets)
        hit_rate = sum(1 for r in rets if r > 0) / len(rets)
        print(f"  {label} forward return -- avg: {avg*100:+.1f}%, hit rate: {hit_rate*100:.0f}%, n={len(rets)}")


def benchmark_nifty500(years):
    hist = fetch_history(["^CRSLDX"], period=f"{years}y")
    df = hist.get("^CRSLDX")
    if df is None or df.empty:
        print("\n(Could not fetch Nifty 500 index benchmark)")
        return
    closes = df["Close"]
    total_return = (closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0]
    annualized = (1 + total_return) ** (1 / years) - 1
    print(f"\n=== Benchmark: Nifty 500 buy & hold over {years}y ===")
    print(f"  Total return: {total_return*100:+.1f}%  |  Annualized: {annualized*100:+.1f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=100, help="number of tickers to sample (full 500 is slow)")
    ap.add_argument("--years", type=int, default=5)
    args = ap.parse_args()

    universe = load_universe()
    yf_symbols = [u["yf_symbol"] for u in universe]
    if args.sample < len(yf_symbols):
        random.seed(42)
        yf_symbols = random.sample(yf_symbols, args.sample)

    print(f"Fetching {args.years}y history for {len(yf_symbols)} sampled tickers...")
    histories = fetch_history(yf_symbols, period=f"{args.years}y")
    print(f"Got history for {len(histories)} tickers.")

    for name, fn in [("pure_technical_swing", swing_technical_signal),
                      ("value_trend_combo (trend leg only)", trend_pullback_signal)]:
        _, n, rets = backtest_strategy(name, fn, histories)
        summarize(name, n, rets)

    benchmark_nifty500(args.years)

    print("\nReminder: value_trend_combo above tests ONLY its technical leg (the value "
          "leg can't be backtested with point-in-time fundamentals from this free data "
          "source). pure_value and coffee_can_compounder are not backtested at all.")


if __name__ == "__main__":
    main()
