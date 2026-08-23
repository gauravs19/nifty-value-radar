# nifty-value-radar

A free, fully automated daily stock screener for the Nifty 500, built for a
mid/long-term value-and-trend approach (not intraday, not day trading). It
scans the market once a day after close, applies four rules-based strategies,
and pushes hits to Telegram — no manual monitoring required. Runs entirely on
GitHub Actions' free tier.

**This is a screening tool, not a signal of guaranteed returns.** See
[Honest expectations](#honest-expectations) before relying on it.

## Strategies

| Strategy | Logic | Basis |
|---|---|---|
| 💎 Value + Trend | Cheap on P/E/P/B/ROE/D/E **and** in an uptrend (price>200DMA, 50DMA>200DMA) but pulled back (RSI 35-55) | Classic "buy a good business on a dip" |
| 📈 Pure Technical Swing | RSI oversold + volume spike, or a genuine pullback-and-reclaim of the 50DMA (not just "still trending") | Trend-following, no fundamentals |
| 🏷️ Pure Value | Statistically cheap **and** Piotroski-lite F-Score ≥ 6/8 (fundamentals improving, not a value trap) | Value investing, filtered against value traps |
| ☕ Coffee Can Compounder | 4-5y avg ROCE ≥ 15% and revenue CAGR ≥ 10% | Saurabh Mukherjea's Coffee Can Investing (adapted from 10y to the ~5y yfinance provides) |
| 📐 Minervini Trend Template | Price above a rising, correctly-stacked 50/150/200-DMA, ≥30% above the 52w low, within 25% of the 52w high | Mark Minervini's trend template (*Trade Like a Stock Market Wizard*) — deliberately strict |
| 🚀 52-Week High Breakout | Price within 3% of a fresh 52-week high on ≥1.5x average volume | Classic Chartink/Darvas-box momentum breakout |
| 🏁 Relative Strength Leader | Stock's 3-month return beats the Nifty 50's by ≥8 percentage points | IBD-style relative strength — filters out laggards even if cheap or technically fine |

Thresholds live in one place: `screener/strategies.py`.

### Conviction scoring and the shortlist

More strategies means a stock can stack multiple independent signals, so
instead of dumping every hit into Telegram, `screener/scoring.py` weights and
combines a stock's fired strategies into one 0-10 conviction score (adjusted
slightly for the day's [macro pulse](#macro-pulse)). Only stocks scoring at
least 5/10 reach Telegram, capped at 10 even on a very strong day — see
`MIN_CONVICTION_SCORE` / `MAX_TO_TELEGRAM` in `main.py`. The CSV and HTML
artifacts still carry every single hit for anyone who wants to dig further.

### Macro pulse

Each run checks the S&P 500, Nasdaq, Nikkei 225, and Brent Crude's 1-day move
(`screener/macro.py`) and labels the day a tailwind, headwind, or neutral.
This doesn't filter anything out — it's a small conviction-score adjustment
and a one-line header on the report, so a technical signal firing against a
strongly negative global tape is visibly discounted rather than presented
with false confidence.

## How it runs

- **Daily** (`daily-screen.yml`, weekdays 4:30pm IST): fetches 1y price history
  for all Nifty 500 tickers plus the Nifty 50 benchmark, computes technical
  indicators, combines with the cached fundamentals, scores and ranks hits by
  conviction, sends a short Telegram shortlist, and uploads CSV/HTML artifacts
  with the full breakdown.
- **Weekly** (`weekly-fundamentals.yml`, Sunday): refreshes the Nifty 500
  constituent list and the fundamentals cache (P/E, P/B, ROE, D/E, Coffee Can,
  Piotroski score) — this is the slow part (~2 requests/ticker), so it's kept
  off the daily critical path and committed back to the repo.

## Setup (10 minutes, all free)

1. **Create a Telegram bot**: message [@BotFather](https://t.me/BotFather) on
   Telegram, send `/newbot`, follow the prompts. You'll get a bot token like
   `123456789:AAF...`.
2. **Get your chat ID**: message your new bot anything, then visit
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser — your
   chat ID is in the JSON response under `message.chat.id`.
3. **Fork/push this repo** to your own GitHub account.
4. In the repo, go to **Settings → Secrets and variables → Actions** and add:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
5. Go to the **Actions** tab and manually run "Weekly Fundamentals Refresh"
   once (via "Run workflow") to seed the cache before the first daily run.
6. That's it — the daily screen runs automatically on the schedule, or trigger
   it manually anytime via **Actions → Daily Stock Screen → Run workflow**.

GitHub disables scheduled workflows after 60 days without any repo activity —
if the weekly job hasn't committed anything and you haven't pushed, re-enable
it manually from the Actions tab every couple of months.

## Backtesting

```
python scripts/backtest.py --sample 100 --years 5
```

Runs the two pure-technical strategies against real historical price data and
reports average forward return + hit rate at 3/6/12 months, benchmarked
against Nifty 500 buy-and-hold over the same period.

**The value/quality strategies are not backtested** — yfinance only exposes
*today's* P/E, ROE, etc., not what they were on a past date, so testing them
against historical prices would be look-ahead bias (using information that
wasn't actually available at the time).

## Honest expectations

- No number below is a promise. Run the backtest yourself and read the actual
  output before trusting any strategy here with money.
- The backtest also carries **survivorship bias**: today's Nifty 500 list
  excludes companies that were delisted or dropped for poor performance, so
  even a good backtest result is somewhat optimistic versus what a live signal
  stream would have produced.
- This is a screening aid to narrow down ~500 stocks to a shortlist — always
  verify the actual financials and read recent news before acting on any hit.
- Nothing here is investment advice.

## Tuning

- Strategy thresholds: `screener/strategies.py`
- Fundamentals/quality thresholds: `screener/quality.py`
- Universe: `data/nifty500.csv` (swap for Nifty 50, a custom watchlist, etc.
  and update `screener/universe.py` if the CSV schema differs)
