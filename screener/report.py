"""Formats screening results into a Telegram-friendly message."""
from datetime import date

STRATEGY_LABELS = {
    "value_trend_combo": "\U0001F48E Value + Trend (buy-the-dip in a good stock)",
    "pure_technical_swing": "\U0001F4C8 Pure Technical Swing",
    "pure_value": "\U0001F3F7️ Pure Value (F-Score filtered, research candidate)",
    "coffee_can_compounder": "☕ Coffee Can Compounder (long-term hold candidate)",
}


def format_report(results_by_strategy, universe_size):
    """results_by_strategy: dict[strategy] -> list of (company, symbol, reasons)."""
    lines = [f"*Daily Stock Screen — {date.today().isoformat()}*",
             f"Scanned {universe_size} Nifty 500 stocks\n"]

    total_hits = sum(len(v) for v in results_by_strategy.values())
    if total_hits == 0:
        lines.append("No signals fired today across any strategy.")
        return "\n".join(lines)

    for key, label in STRATEGY_LABELS.items():
        hits = results_by_strategy.get(key, [])
        lines.append(f"\n{label} — {len(hits)} hit(s)")
        if not hits:
            lines.append("  none")
            continue
        for company, symbol, reasons in hits[:25]:
            reason_str = "; ".join(reasons)
            lines.append(f"  • *{symbol}* ({company}) — {reason_str}")
        if len(hits) > 25:
            lines.append(f"  ...and {len(hits) - 25} more (see CSV artifact)")

    lines.append(
        "\n_Not investment advice. Rules-based screen only — verify fundamentals "
        "and do your own research before acting._"
    )
    return "\n".join(lines)
