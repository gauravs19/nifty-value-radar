"""Global macro pulse: a quick 1-day check against major indices, used to add
context to technical signals (not to filter fundamentals-only strategies)."""
import yfinance as yf

INDICES = {
    "S&P 500": "^GSPC",
    "Nasdaq": "^IXIC",
    "Nikkei 225": "^N225",
    "Brent Crude": "BZ=F",
}
EQUITY_INDICES = ("S&P 500", "Nasdaq", "Nikkei 225")

TAILWIND_THRESHOLD = 0.3   # avg equity index % change at/above this = tailwind
HEADWIND_THRESHOLD = -0.3  # at/below this = headwind


def fetch_macro_pulse():
    """Returns {"changes": {name: pct_change}, "mood": "tailwind"|"headwind"|"neutral",
    "avg_equity_change": float}. Missing tickers are skipped, not fatal."""
    changes = {}
    for name, ticker in INDICES.items():
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if len(hist) >= 2:
                prev, last = hist["Close"].iloc[-2], hist["Close"].iloc[-1]
                changes[name] = (last - prev) / prev * 100
        except Exception:
            continue

    equity_changes = [v for k, v in changes.items() if k in EQUITY_INDICES]
    avg_equity = sum(equity_changes) / len(equity_changes) if equity_changes else 0.0

    if avg_equity >= TAILWIND_THRESHOLD:
        mood = "tailwind"
    elif avg_equity <= HEADWIND_THRESHOLD:
        mood = "headwind"
    else:
        mood = "neutral"

    return {"changes": changes, "mood": mood, "avg_equity_change": avg_equity}


def format_macro_line(pulse):
    parts = [f"{name} {v:+.1f}%" for name, v in pulse["changes"].items()]
    mood_label = {"tailwind": "Global tailwind", "headwind": "Global headwind", "neutral": "Global: mixed/flat"}
    return f"{mood_label[pulse['mood']]} ({', '.join(parts)})" if parts else mood_label[pulse["mood"]]
