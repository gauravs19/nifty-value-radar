"""Formats screening results: a short conviction-ranked Telegram message,
and a full standalone HTML report with every hit."""
from datetime import date

STRATEGY_LABELS = {
    "value_trend_combo": "\U0001F48E Value + Trend (buy-the-dip in a good stock)",
    "pure_technical_swing": "\U0001F4C8 Pure Technical Swing",
    "pure_value": "\U0001F3F7️ Pure Value (F-Score filtered, research candidate)",
    "coffee_can_compounder": "☕ Coffee Can Compounder (long-term hold candidate)",
    "minervini_trend": "\U0001F4D0 Minervini Trend Template",
    "breakout_52w_high": "\U0001F680 52-Week High Breakout",
    "relative_strength_leader": "\U0001F3C1 Relative Strength Leader (vs Nifty)",
}


def format_ranked_report(ranked, universe_size, macro_line, total_symbols_with_hits):
    """ranked: stocks that cleared the conviction floor (screener.scoring +
    main.py's MIN_CONVICTION_SCORE), already capped to a small max. Sent to
    Telegram -- kept short by design; the CSV/HTML artifacts carry every hit."""
    lines = [f"*Daily Stock Screen — {date.today().isoformat()}*",
             f"Scanned {universe_size} stocks · {macro_line}",
             f"{len(ranked)} of {total_symbols_with_hits} stock(s) with signals cleared the conviction bar:\n"]

    if not ranked:
        lines.append("No stock cleared the conviction bar today -- no signals worth acting on.")
        return "\n".join(lines)

    for i, hit in enumerate(ranked, 1):
        strategy_names = ", ".join(hit["strategies"])
        reason_str = "; ".join(hit["reasons"])
        price_line = f" — ₹{hit['price']:.2f}, {hit['trend']}" if hit.get("price") is not None else ""
        lines.append(
            f"{i}. *{hit['symbol']}* ({hit['company']}){price_line} — conviction {hit['score']}/10\n"
            f"   {strategy_names}\n   {reason_str}"
        )

    lines.append(
        "\n_Not investment advice. Rules-based screen only — verify fundamentals "
        "and do your own research before acting._"
    )
    return "\n".join(lines)


def _html_escape(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _conviction_bar(score):
    filled = round(score)
    cells = "".join(f"<span class='cell{' on' if i < filled else ''}'></span>" for i in range(10))
    return f"<span class='meter' aria-label='conviction {score} of 10'>{cells}</span>"


def _sparkline_svg(values, positive):
    if not values or len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    rng = hi - lo or 1
    w, h, pad = 108, 26, 2
    step = (w - 2 * pad) / (len(values) - 1)
    points = " ".join(
        f"{pad + i * step:.1f},{h - pad - ((v - lo) / rng) * (h - 2 * pad):.1f}"
        for i, v in enumerate(values)
    )
    color_var = "var(--bull)" if positive else "var(--bear)"
    return (f"<svg class='spark' viewBox='0 0 {w} {h}' preserveAspectRatio='none' aria-hidden='true'>"
            f"<polyline points='{points}' fill='none' stroke='{color_var}' stroke-width='1.6' "
            f"stroke-linejoin='round' stroke-linecap='round'/></svg>")


def _trend_chip(trend):
    cls = {"Uptrend": "bull", "Downtrend": "bear"}.get(trend, "neutral")
    return f"<span class='trend {cls}'>{_html_escape(trend or '')}</span>"


def _macro_chip(macro_line):
    mood_class = "neutral"
    lowered = macro_line.lower()
    if "tailwind" in lowered:
        mood_class = "bull"
    elif "headwind" in lowered:
        mood_class = "bear"
    return f"<span class='chip {mood_class}'><span class='dot'></span>{_html_escape(macro_line)}</span>"


def format_html_report(results_by_strategy, universe_size, macro_line="", ranked=None):
    """results_by_strategy: full per-strategy breakdown (every hit, for the
    accordions). ranked: top conviction-scored list from screener.scoring
    (same data sent to Telegram) shown as the page's lead shortlist."""
    total_hits = sum(len(v) for v in results_by_strategy.values())
    today = date.today().isoformat()
    ranked = ranked or []

    def _row(i, h):
        spark = h.get("spark") or []
        positive = len(spark) >= 2 and spark[-1] >= spark[0]
        price = h.get("price")
        price_html = f"<span class='price'>₹{price:,.2f}</span>" if price is not None else ""
        return f"""
      <li class="pick">
        <span class="rank">{i:02d}</span>
        <div class="pick-main">
          <div class="pick-head">
            <span class="ticker">{_html_escape(h['symbol'])}</span>
            <span class="company">{_html_escape(h['company'])}</span>
            {price_html}
            {_trend_chip(h.get('trend'))}
          </div>
          <div class="tags">{''.join(f"<span class='tag'>{_html_escape(s)}</span>" for s in h['strategies'])}</div>
          <p class="reasons">{_html_escape('; '.join(h['reasons']))}</p>
        </div>
        <div class="score">
          <span class="score-num">{h['score']}</span>
          {_conviction_bar(h['score'])}
          {_sparkline_svg(spark, positive)}
        </div>
      </li>"""
    shortlist_rows = "\n".join(_row(i, h) for i, h in enumerate(ranked, 1))
    shortlist = (f"<ol class='shortlist'>{shortlist_rows}</ol>" if ranked
                 else "<p class='empty'>No signals fired today.</p>")

    sections = []
    for key, label in STRATEGY_LABELS.items():
        hits = results_by_strategy.get(key, [])
        rows = "\n".join(
            f"<tr><td class='t-ticker'>{_html_escape(symbol)}</td><td>{_html_escape(company)}</td>"
            f"<td class='t-reasons'>{_html_escape('; '.join(reasons))}</td></tr>"
            for company, symbol, reasons in hits
        )
        table = (
            f"<table><thead><tr><th>Symbol</th><th>Company</th><th>Reasons</th></tr>"
            f"</thead><tbody>{rows}</tbody></table>" if hits
            else "<p class='empty'>No hits.</p>"
        )
        sections.append(f"""
      <details>
        <summary>{label} <span class="count">{len(hits)}</span></summary>
        {table}
      </details>""")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nifty Value Radar</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #EEF0EF; --surface: #F7F8F6; --ink: #1B2430; --ink-dim: #5B6470;
  --accent: #C4791E; --bull: #3F7D58; --bear: #B8493D; --line: #D8D5CC;
  --font-display: 'Fraunces', Georgia, serif;
  --font-body: 'IBM Plex Sans', system-ui, sans-serif;
  --font-mono: 'IBM Plex Mono', 'Courier New', monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #14171B; --surface: #1B1F24; --ink: #E8E6DF; --ink-dim: #93998F;
    --accent: #E0A83E; --bull: #6FBE8C; --bear: #E07A6C; --line: #2B2F35;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #14171B; --surface: #1B1F24; --ink: #E8E6DF; --ink-dim: #93998F;
  --accent: #E0A83E; --bull: #6FBE8C; --bear: #E07A6C; --line: #2B2F35;
}}
* {{ box-sizing: border-box; }}
body {{
  background: var(--bg); color: var(--ink); font-family: var(--font-body);
  max-width: 46rem; margin: 0 auto; padding: 2.5rem 1.25rem 4rem;
  font-variant-numeric: tabular-nums;
}}
header {{ display: flex; flex-direction: column; gap: 0.9rem; margin-bottom: 2rem; }}
.eyebrow {{
  font-family: var(--font-mono); font-size: 0.72rem; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--accent); font-weight: 500;
}}
h1 {{
  font-family: var(--font-display); font-weight: 600; font-size: 2.1rem;
  margin: 0; text-wrap: balance; letter-spacing: -0.01em;
}}
.subline {{ color: var(--ink-dim); font-size: 0.92rem; margin: 0; }}
.chip {{
  display: inline-flex; align-items: center; gap: 0.45rem; font-family: var(--font-mono);
  font-size: 0.78rem; padding: 0.35rem 0.7rem; border-radius: 999px;
  background: var(--surface); border: 1px solid var(--line); width: fit-content;
}}
.chip .dot {{ width: 0.5rem; height: 0.5rem; border-radius: 999px; background: var(--ink-dim); }}
.chip.bull .dot {{ background: var(--bull); }}
.chip.bear .dot {{ background: var(--bear); }}

h2.section-title {{
  font-family: var(--font-body); font-size: 0.78rem; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--ink-dim); font-weight: 600;
  margin: 0 0 0.9rem; border-bottom: 1px solid var(--line); padding-bottom: 0.6rem;
}}

.shortlist {{ list-style: none; margin: 0 0 2.5rem; padding: 0; display: flex; flex-direction: column; }}
.pick {{
  display: grid; grid-template-columns: 2rem 1fr auto; gap: 1rem; align-items: start;
  padding: 1rem 0; border-bottom: 1px solid var(--line);
}}
.pick:first-child {{ padding-top: 0; }}
.rank {{ font-family: var(--font-mono); color: var(--ink-dim); font-size: 0.85rem; padding-top: 0.15rem; }}
.pick-head {{ display: flex; align-items: baseline; gap: 0.6rem; flex-wrap: wrap; }}
.ticker {{ font-family: var(--font-mono); font-weight: 600; font-size: 1rem; }}
.company {{ color: var(--ink-dim); font-size: 0.88rem; }}
.price {{ font-family: var(--font-mono); font-weight: 500; font-size: 0.88rem; }}
.trend {{
  font-size: 0.68rem; letter-spacing: 0.04em; text-transform: uppercase;
  padding: 0.1rem 0.4rem; border-radius: 3px; background: var(--surface); color: var(--ink-dim);
}}
.trend.bull {{ color: var(--bull); }}
.trend.bear {{ color: var(--bear); }}
.tags {{ display: flex; gap: 0.4rem; flex-wrap: wrap; margin: 0.4rem 0; }}
.tag {{
  font-family: var(--font-mono); font-size: 0.68rem; color: var(--accent);
  border: 1px solid var(--accent); border-radius: 3px; padding: 0.1rem 0.4rem;
}}
.reasons {{ margin: 0.2rem 0 0; font-size: 0.85rem; color: var(--ink-dim); max-width: 34rem; }}
.score {{ display: flex; flex-direction: column; align-items: flex-end; gap: 0.3rem; }}
.score-num {{ font-family: var(--font-mono); font-weight: 600; font-size: 1.1rem; }}
.meter {{ display: flex; gap: 2px; }}
.meter .cell {{ width: 5px; height: 12px; background: var(--line); border-radius: 1px; }}
.meter .cell.on {{ background: var(--accent); }}
.spark {{ width: 96px; height: 24px; display: block; }}

details {{
  border-bottom: 1px solid var(--line); padding: 0.9rem 0;
}}
details:first-of-type {{ border-top: 1px solid var(--line); }}
summary {{
  cursor: pointer; font-weight: 500; display: flex; align-items: center;
  justify-content: space-between; list-style: none;
}}
summary::-webkit-details-marker {{ display: none; }}
summary::after {{ content: '+'; color: var(--ink-dim); font-family: var(--font-mono); }}
details[open] summary::after {{ content: '−'; }}
.count {{ font-family: var(--font-mono); color: var(--ink-dim); font-size: 0.85rem; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 0.9rem; font-size: 0.85rem; }}
th, td {{ text-align: left; padding: 0.5rem 0.6rem; border-bottom: 1px solid var(--line); vertical-align: top; }}
th {{
  font-family: var(--font-mono); font-size: 0.7rem; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--ink-dim); font-weight: 500;
}}
.t-ticker {{ font-family: var(--font-mono); font-weight: 500; white-space: nowrap; }}
.t-reasons {{ color: var(--ink-dim); }}
.wide {{ overflow-x: auto; }}
.empty {{ color: var(--ink-dim); font-style: italic; font-size: 0.88rem; }}
footer {{ margin-top: 2.5rem; color: var(--ink-dim); font-size: 0.8rem; line-height: 1.5; }}
</style>
</head>
<body>
<header>
  <span class="eyebrow">Nifty 500 · Daily Screen</span>
  <h1>{today}</h1>
  <p class="subline">Scanned {universe_size} stocks · {total_hits} total signal(s) across {len(STRATEGY_LABELS)} strategies</p>
  {_macro_chip(macro_line) if macro_line else ""}
</header>

<h2 class="section-title">Top conviction picks</h2>
{shortlist}

<h2 class="section-title">Full breakdown by strategy</h2>
<div class="wide">
{''.join(sections)}
</div>

<footer>Not investment advice. Rules-based screen only — verify fundamentals and do your own research before acting.</footer>
</body>
</html>
"""
