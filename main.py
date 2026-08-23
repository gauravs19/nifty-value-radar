"""Daily entrypoint: fetch prices, run strategies against cached fundamentals,
send the Telegram report, and save a CSV artifact of the day's hits."""
import csv
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from screener.universe import load_universe
from screener.price_data import fetch_history
from screener.indicators import compute_indicators
from screener.fundamentals import load_cache
from screener.strategies import evaluate_all
from screener.report import format_report
from screener.notify import send_telegram

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def run():
    universe = load_universe()
    yf_symbols = [u["yf_symbol"] for u in universe]
    by_symbol = {u["yf_symbol"]: u for u in universe}

    print(f"Fetching price history for {len(yf_symbols)} tickers...")
    histories = fetch_history(yf_symbols, period="1y")
    print(f"Got history for {len(histories)}/{len(yf_symbols)} tickers.")

    fundamentals_cache = load_cache()
    if not fundamentals_cache:
        print("WARNING: no fundamentals cache found -- run scripts/refresh_fundamentals.py first. "
              "Value/quality-based strategies will not fire.")

    results_by_strategy = {}
    csv_rows = []

    for sym, hist in histories.items():
        if len(hist) < 60:
            continue
        indicators = compute_indicators(hist)
        latest = indicators.iloc[-1]
        fund = fundamentals_cache.get(sym)
        hits = evaluate_all(latest, fund)
        if not hits:
            continue
        meta = by_symbol.get(sym, {})
        for strategy, (fired, reasons) in hits.items():
            if not fired:
                continue
            results_by_strategy.setdefault(strategy, []).append(
                (meta.get("company", sym), meta.get("symbol", sym), reasons)
            )
            csv_rows.append({
                "strategy": strategy, "symbol": meta.get("symbol", sym),
                "company": meta.get("company", sym), "reasons": "; ".join(reasons),
            })

    report_text = format_report(results_by_strategy, len(histories))
    print(report_text)
    send_telegram(report_text)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "latest_signals.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["strategy", "symbol", "company", "reasons"])
        writer.writeheader()
        writer.writerows(csv_rows)


if __name__ == "__main__":
    sys.exit(run() or 0)
