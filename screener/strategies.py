"""Screening rules. Each strategy takes the latest indicator row + fundamentals
for one stock and returns (fired: bool, reasons: list[str]).

All thresholds are deliberately simple and inspectable -- tune them in one place.
"""

VALUE_PE_MAX = 25          # trailing P/E below this is considered "not expensive"
VALUE_PB_MAX = 4           # price-to-book below this
VALUE_ROE_MIN = 0.12       # return on equity above 12%
VALUE_DE_MAX = 100         # debt/equity below 100 (yfinance reports this as a ratio*100)

TREND_RSI_LOW = 35         # pullback zone lower bound (not a crash)
TREND_RSI_HIGH = 55        # upper bound (not already overbought)

SWING_RSI_OVERSOLD = 32
SWING_VOL_SPIKE_MULT = 1.5
SWING_RECLAIM_LOOKBACK = 10  # trading days to look back for a genuine pullback+reclaim

NEAR_52W_LOW_PCT = 0.15    # within 15% of the 52-week low
PIOTROSKI_MIN = 6          # out of 8 -- "fundamentals improving, not deteriorating"

MIN_AVG_TURNOVER = 10_000_000  # INR; 20d avg (Close * Volume) below this is too illiquid to act on

MINERVINI_ABOVE_LOW_PCT = 0.30    # price at least 30% above the 52-week low
MINERVINI_WITHIN_HIGH_PCT = 0.25  # price within 25% of the 52-week high
MINERVINI_TREND_LOOKBACK = 20     # trading days used to confirm the 200-DMA is rising, not just above it

BREAKOUT_NEAR_HIGH_PCT = 0.03     # within 3% of the 52w high counts as a fresh breakout zone
BREAKOUT_VOL_MULT = 1.5

RS_LOOKBACK_DAYS = 63             # ~3 months
RS_OUTPERFORMANCE_MIN = 8.0       # percentage points of outperformance vs Nifty required

# Longest history any single-row strategy below needs; main.py slices indicators to this.
INDICATOR_LOOKBACK = max(SWING_RECLAIM_LOOKBACK, MINERVINI_TREND_LOOKBACK)


def value_signal(fund):
    if not fund:
        return False, []
    ok = True
    pe, pb, roe, de = fund.get("trailingPE"), fund.get("priceToBook"), fund.get("returnOnEquity"), fund.get("debtToEquity")
    if not (pe is not None and 0 < pe <= VALUE_PE_MAX):
        ok = False
    if not (pb is not None and 0 < pb <= VALUE_PB_MAX):
        ok = False
    if not (roe is not None and roe >= VALUE_ROE_MIN):
        ok = False
    if not ok:
        return False, []
    debt_note = ", with manageable debt" if de is not None and de <= VALUE_DE_MAX else ""
    reasons = [f"Reasonably priced for what it earns (P/E {pe:.1f}, P/B {pb:.1f}x) and profitable (ROE {roe*100:.0f}%){debt_note}"]
    return True, reasons


def trend_pullback_signal(row):
    """row: latest indicator row (pandas Series) with sma50/sma200/rsi14/Close."""
    close, sma50, sma200, r = row.get("Close"), row.get("sma50"), row.get("sma200"), row.get("rsi14")
    if None in (close, sma50, sma200, r) or any(v != v for v in (close, sma50, sma200, r)):  # NaN check
        return False, []
    uptrend = close > sma200 and sma50 > sma200
    pullback = TREND_RSI_LOW <= r <= TREND_RSI_HIGH
    if uptrend and pullback:
        return True, [f"In a healthy uptrend but has cooled off a bit (RSI {r:.0f}) — a reasonable entry point, not a chase"]
    return False, []


def swing_technical_signal(hist_tail):
    """hist_tail: last SWING_RECLAIM_LOOKBACK+1 rows of indicators (ascending
    date order, latest row last)."""
    if hist_tail is None or len(hist_tail) < 2:
        return False, []
    row = hist_tail.iloc[-1]
    reasons = []
    close, sma50, sma200, r, vol, vol_avg = (
        row.get("Close"), row.get("sma50"), row.get("sma200"), row.get("rsi14"),
        row.get("Volume"), row.get("vol_avg20"),
    )
    fired = False
    if r == r and r <= SWING_RSI_OVERSOLD and vol and vol_avg and vol_avg == vol_avg and vol >= SWING_VOL_SPIKE_MULT * vol_avg:
        reasons.append(f"Sold off sharply but buyers are stepping in — trading volume is {vol/vol_avg:.1f}x the usual pace")
        fired = True
    if sma50 == sma50 and sma200 == sma200 and close == close and close > sma50 > sma200:
        # Only a real "continuation" entry if price recently pulled back to/through
        # the 50DMA and reclaimed it -- otherwise this is trivially true for any
        # stock that has been trending for months, which is not a signal.
        prior = hist_tail.iloc[:-1]
        recently_pulled_back = (prior["Close"] <= prior["sma50"]).any()
        if recently_pulled_back:
            reasons.append(f"Dipped toward its 50-day average and bounced back within the last {len(prior)} trading days — the uptrend held")
            fired = True
    return fired, reasons


def liquidity_ok(row):
    close, vol_avg = row.get("Close"), row.get("vol_avg20")
    if close != close or vol_avg != vol_avg or not close or not vol_avg:
        return False
    return (close * vol_avg) >= MIN_AVG_TURNOVER


def near_52w_low_signal(row):
    close, low52 = row.get("Close"), row.get("52w_low")
    if None in (close, low52) or close != close or low52 != low52 or low52 == 0:
        return False, []
    pct_above_low = (close - low52) / low52
    if pct_above_low <= NEAR_52W_LOW_PCT:
        return True, [f"Trading just {pct_above_low*100:.0f}% above its 52-week low — not chasing a rally"]
    return False, []


def piotroski_ok(fund):
    score = (fund or {}).get("piotroskiScore")
    if score is None:
        return False, []
    return score >= PIOTROSKI_MIN, [f"Fundamentals are improving, not deteriorating (F-Score {score}/8)"]


def coffee_can_signal(fund):
    if not fund or not fund.get("coffeeCan"):
        return False, []
    reasons = [r for r in (fund.get("coffeeCanReasons") or "").split("; ") if r]
    return True, reasons


def minervini_trend_signal(hist_tail):
    """Mark Minervini's Trend Template: price above a rising, correctly-stacked
    50/150/200-DMA, well off the 52w low and not too extended from the 52w high.
    Deliberately strict -- usually only a small slice of any universe passes all of it.
    hist_tail: last MINERVINI_TREND_LOOKBACK+1 rows of indicators (ascending, latest last)."""
    if hist_tail is None or len(hist_tail) < MINERVINI_TREND_LOOKBACK + 1:
        return False, []
    row = hist_tail.iloc[-1]
    close, sma50, sma150, sma200, high52, low52 = (
        row.get("Close"), row.get("sma50"), row.get("sma150"), row.get("sma200"),
        row.get("52w_high"), row.get("52w_low"),
    )
    vals = (close, sma50, sma150, sma200, high52, low52)
    if any(v is None or v != v for v in vals) or not low52 or not high52:
        return False, []

    sma200_prior = hist_tail["sma200"].iloc[0]
    if sma200_prior != sma200_prior:
        return False, []

    above_low = (close - low52) / low52
    below_high = (high52 - close) / high52
    checks = (
        close > sma150 and close > sma200,
        sma150 > sma200,
        sma200 > sma200_prior,
        sma50 > sma150 and sma50 > sma200,
        close > sma50,
        above_low >= MINERVINI_ABOVE_LOW_PCT,
        below_high <= MINERVINI_WITHIN_HIGH_PCT,
    )
    if all(checks):
        return True, [
            f"Textbook strong uptrend (Minervini trend template): {above_low*100:.0f}% above its 52-week low "
            f"without being overextended ({below_high*100:.0f}% below the 52-week high)"
        ]
    return False, []


def high_breakout_signal(row):
    """Fresh 52-week-high breakout confirmed by volume -- the momentum-leadership
    counterpart to near_52w_low_signal's value-trap-avoidance check."""
    close, high52, vol, vol_avg = row.get("Close"), row.get("52w_high"), row.get("Volume"), row.get("vol_avg20")
    vals = (close, high52, vol, vol_avg)
    if any(v is None or v != v for v in vals) or not high52 or not vol_avg:
        return False, []
    near_high = (high52 - close) / high52 <= BREAKOUT_NEAR_HIGH_PCT
    vol_confirmed = vol >= BREAKOUT_VOL_MULT * vol_avg
    if near_high and vol_confirmed:
        return True, [f"Breaking out to a new 52-week high on strong buying ({vol/vol_avg:.1f}x normal volume)"]
    return False, []


def relative_strength_signal(hist, nifty_return_pct):
    """IBD-style relative strength: only surface stocks genuinely outperforming
    the benchmark, not just cheap or technically fine while lagging the market.
    hist: raw OHLCV history (needs RS_LOOKBACK_DAYS+1 rows). nifty_return_pct:
    Nifty 50's % return over the same window, computed once per run."""
    if hist is None or len(hist) <= RS_LOOKBACK_DAYS or nifty_return_pct is None:
        return False, []
    closes = hist["Close"]
    stock_return = (closes.iloc[-1] / closes.iloc[-RS_LOOKBACK_DAYS - 1] - 1) * 100
    outperformance = stock_return - nifty_return_pct
    if outperformance >= RS_OUTPERFORMANCE_MIN:
        return True, [
            f"Beating the market: up {stock_return:+.0f}% over 3 months vs the Nifty's {nifty_return_pct:+.0f}% "
            f"({outperformance:.0f} points ahead)"
        ]
    return False, []


def evaluate_all(hist_tail, hist, fund, nifty_return_pct=None):
    """hist_tail: last INDICATOR_LOOKBACK+1 rows of indicators (ascending, latest
    last). hist: raw OHLCV history for the same ticker (for relative-strength).
    Returns dict of strategy_name -> (fired, reasons)."""
    row = hist_tail.iloc[-1]
    v_ok, v_reasons = value_signal(fund)
    t_ok, t_reasons = trend_pullback_signal(row)
    s_ok, s_reasons = swing_technical_signal(hist_tail.tail(SWING_RECLAIM_LOOKBACK + 1))
    low_ok, low_reasons = near_52w_low_signal(row)
    p_ok, p_reasons = piotroski_ok(fund)
    cc_ok, cc_reasons = coffee_can_signal(fund)
    m_ok, m_reasons = minervini_trend_signal(hist_tail)
    b_ok, b_reasons = high_breakout_signal(row)
    rs_ok, rs_reasons = relative_strength_signal(hist, nifty_return_pct)

    results = {}
    if v_ok and t_ok:
        results["value_trend_combo"] = (True, v_reasons + t_reasons)
    if s_ok:
        results["pure_technical_swing"] = (True, s_reasons)
    if v_ok:
        # Only surface as a value idea if the F-Score says fundamentals are
        # improving, not deteriorating -- avoids flagging value traps.
        if p_ok:
            pure_value_reasons = v_reasons + p_reasons + (low_reasons if low_ok else [])
            results["pure_value"] = (True, pure_value_reasons)
    if cc_ok:
        results["coffee_can_compounder"] = (True, cc_reasons)
    if m_ok:
        results["minervini_trend"] = (True, m_reasons)
    if b_ok:
        results["breakout_52w_high"] = (True, b_reasons)
    if rs_ok:
        results["relative_strength_leader"] = (True, rs_reasons)
    return results
