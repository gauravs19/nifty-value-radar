"""Daily entrypoint: fetch prices, run strategies against cached fundamentals,
rank hits by conviction, send a short Telegram report, and save full CSV/HTML
artifacts of every hit."""
import csv
import io
import os
import sys
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from screener.universe import load_universe
from screener.price_data import fetch_history, fetch_benchmark_return
from screener.indicators import compute_indicators, trend_label
from screener.fundamentals import load_cache
from screener.strategies import evaluate_all, liquidity_ok, INDICATOR_LOOKBACK, RS_LOOKBACK_DAYS
from screener.macro import fetch_macro_pulse, format_macro_line
from screener.scoring import score_hits
from screener.report import format_html_report, format_ranked_report
from screener.notify import send_telegram, send_telegram_document

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MIN_CONVICTION_SCORE = 5.0  # a stock must clear this to reach Telegram at all
MAX_TO_TELEGRAM = 10        # even on a very strong day, cap what actually reaches the user
SPARK_DAYS = 30


def run():
    universe = load_universe()
    yf_symbols = [u["yf_symbol"] for u in universe]
    by_symbol = {u["yf_symbol"]: u for u in universe}

    print("Fetching global macro pulse...")
    macro = fetch_macro_pulse()
    macro_line = format_macro_line(macro)
    print(macro_line)

    print("Fetching Nifty 50 benchmark return (for relative-strength)...")
    nifty_return_pct = fetch_benchmark_return(lookback_days=RS_LOOKBACK_DAYS)

    print(f"Fetching price history for {len(yf_symbols)} tickers...")
    histories = fetch_history(yf_symbols, period="1y")
    print(f"Got history for {len(histories)}/{len(yf_symbols)} tickers.")

    fundamentals_cache = load_cache()
    if not fundamentals_cache:
        print("WARNING: no fundamentals cache found -- run scripts/refresh_fundamentals.py first. "
              "Value/quality-based strategies will not fire.")

    results_by_strategy = {}
    hits_by_symbol = {}
    csv_rows = []
    skipped_illiquid = 0

    for sym, hist in histories.items():
        if len(hist) < 60:
            continue
        indicators = compute_indicators(hist)
        latest = indicators.iloc[-1]
        if not liquidity_ok(latest):
            skipped_illiquid += 1
            continue
        hist_tail = indicators.tail(INDICATOR_LOOKBACK + 1)
        fund = fundamentals_cache.get(sym)
        hits = evaluate_all(hist_tail, hist, fund, nifty_return_pct)
        if not hits:
            continue
        meta = by_symbol.get(sym, {})
        company, display_symbol = meta.get("company", sym), meta.get("symbol", sym)
        price = round(float(latest["Close"]), 2)
        trend = trend_label(latest)
        fired_strategies = {}
        for strategy, (fired, reasons) in hits.items():
            if not fired:
                continue
            fired_strategies[strategy] = reasons
            results_by_strategy.setdefault(strategy, []).append((company, display_symbol, reasons))
            csv_rows.append({
                "strategy": strategy, "symbol": display_symbol, "company": company,
                "price": price, "trend": trend, "reasons": "; ".join(reasons),
            })
        if fired_strategies:
            hits_by_symbol[sym] = {
                "company": company, "display_symbol": display_symbol,
                "strategies": fired_strategies, "price": price, "trend": trend,
                "spark": [round(float(c), 2) for c in hist["Close"].tail(SPARK_DAYS).tolist()],
            }

    print(f"Skipped {skipped_illiquid} illiquid tickers (below turnover floor).")

    ranked = score_hits(hits_by_symbol, macro["mood"])
    top_ranked = [h for h in ranked if h["score"] >= MIN_CONVICTION_SCORE][:MAX_TO_TELEGRAM]

    ranked_report = format_ranked_report(top_ranked, len(histories), macro_line, len(ranked))
    print(ranked_report)
    send_telegram(ranked_report)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "latest_signals.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["strategy", "symbol", "company", "price", "trend", "reasons"])
        writer.writeheader()
        writer.writerows(csv_rows)

    html_report = format_html_report(results_by_strategy, len(histories), macro_line, top_ranked)
    html_path = os.path.join(DATA_DIR, "latest_report.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_report)

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    send_telegram_document(
        html_path,
        caption=f"Full report — {len(top_ranked)} conviction pick(s), {len(ranked)} total signal(s) today.",
        filename=f"nifty-value-radar_{stamp}.html",
    )


if __name__ == "__main__":
    sys.exit(run() or 0)
