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


def _html_escape(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def format_html_report(results_by_strategy, universe_size):
    """Same data as format_report, rendered as a standalone HTML page with
    every hit listed (no 25-row cap — this is a file, not a chat message)."""
    total_hits = sum(len(v) for v in results_by_strategy.values())
    today = date.today().isoformat()

    sections = []
    for key, label in STRATEGY_LABELS.items():
        hits = results_by_strategy.get(key, [])
        rows = "\n".join(
            f"<tr><td>{_html_escape(symbol)}</td><td>{_html_escape(company)}</td>"
            f"<td>{_html_escape('; '.join(reasons))}</td></tr>"
            for company, symbol, reasons in hits
        )
        table = (
            f"<table><thead><tr><th>Symbol</th><th>Company</th><th>Reasons</th></tr>"
            f"</thead><tbody>{rows}</tbody></table>" if hits
            else "<p class='none'>No hits.</p>"
        )
        sections.append(
            f"<section><h2>{_html_escape(label)} — {len(hits)} hit(s)</h2>{table}</section>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Daily Stock Screen — {today}</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }}
h1 {{ margin-bottom: 0.25rem; }}
.meta {{ color: #555; margin-top: 0; }}
section {{ margin: 2rem 0; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #ddd; font-size: 0.9rem; }}
th {{ background: #f4f4f4; }}
.none {{ color: #888; font-style: italic; }}
footer {{ margin-top: 2rem; color: #777; font-size: 0.85rem; }}
</style>
</head>
<body>
<h1>Daily Stock Screen — {today}</h1>
<p class="meta">Scanned {universe_size} Nifty 500 stocks — {total_hits} total hit(s)</p>
{''.join(sections)}
<footer>Not investment advice. Rules-based screen only — verify fundamentals and do your own research before acting.</footer>
</body>
</html>
"""
