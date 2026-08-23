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

NEAR_52W_LOW_PCT = 0.15    # within 15% of the 52-week low
PIOTROSKI_MIN = 6          # out of 8 -- "fundamentals improving, not deteriorating"


def value_signal(fund):
    if not fund:
        return False, []
    reasons = []
    ok = True
    pe, pb, roe, de = fund.get("trailingPE"), fund.get("priceToBook"), fund.get("returnOnEquity"), fund.get("debtToEquity")
    if pe is not None and 0 < pe <= VALUE_PE_MAX:
        reasons.append(f"P/E {pe:.1f}")
    else:
        ok = False
    if pb is not None and 0 < pb <= VALUE_PB_MAX:
        reasons.append(f"P/B {pb:.1f}")
    else:
        ok = False
    if roe is not None and roe >= VALUE_ROE_MIN:
        reasons.append(f"ROE {roe*100:.0f}%")
    else:
        ok = False
    if de is not None and de <= VALUE_DE_MAX:
        reasons.append(f"D/E {de:.0f}")
    # debt/equity missing is not disqualifying, just not confirmed
    return ok, reasons


def trend_pullback_signal(row):
    """row: latest indicator row (pandas Series) with sma50/sma200/rsi14/Close."""
    reasons = []
    close, sma50, sma200, r = row.get("Close"), row.get("sma50"), row.get("sma200"), row.get("rsi14")
    if None in (close, sma50, sma200, r) or any(v != v for v in (close, sma50, sma200, r)):  # NaN check
        return False, []
    uptrend = close > sma200 and sma50 > sma200
    pullback = TREND_RSI_LOW <= r <= TREND_RSI_HIGH
    if uptrend:
        reasons.append("above 200-DMA, 50>200 (uptrend)")
    if pullback:
        reasons.append(f"RSI {r:.0f} (pullback zone)")
    return uptrend and pullback, reasons


def swing_technical_signal(row):
    reasons = []
    close, sma50, sma200, r, vol, vol_avg = (
        row.get("Close"), row.get("sma50"), row.get("sma200"), row.get("rsi14"),
        row.get("Volume"), row.get("vol_avg20"),
    )
    fired = False
    if None not in (r,) and r == r and r <= SWING_RSI_OVERSOLD and vol and vol_avg and vol_avg == vol_avg and vol >= SWING_VOL_SPIKE_MULT * vol_avg:
        reasons.append(f"RSI oversold ({r:.0f}) + volume spike ({vol/vol_avg:.1f}x avg)")
        fired = True
    if sma50 == sma50 and sma200 == sma200 and close == close:
        # golden-cross style: price just reclaimed sma50 from below, sma50 turning up toward sma200
        if close > sma50 and sma50 > sma200:
            reasons.append("uptrend continuation (price>50DMA>200DMA)")
            fired = True
    return fired, reasons


def near_52w_low_signal(row):
    close, low52 = row.get("Close"), row.get("52w_low")
    if None in (close, low52) or close != close or low52 != low52 or low52 == 0:
        return False, []
    pct_above_low = (close - low52) / low52
    if pct_above_low <= NEAR_52W_LOW_PCT:
        return True, [f"{pct_above_low*100:.0f}% above 52w low"]
    return False, []


def piotroski_ok(fund):
    score = (fund or {}).get("piotroskiScore")
    if score is None:
        return False, []
    return score >= PIOTROSKI_MIN, [f"F-Score {score}/8"]


def coffee_can_signal(fund):
    if not fund or not fund.get("coffeeCan"):
        return False, []
    reasons = [r for r in (fund.get("coffeeCanReasons") or "").split("; ") if r]
    return True, reasons


def evaluate_all(row, fund):
    """Returns dict of strategy_name -> (fired, reasons)."""
    v_ok, v_reasons = value_signal(fund)
    t_ok, t_reasons = trend_pullback_signal(row)
    s_ok, s_reasons = swing_technical_signal(row)
    low_ok, low_reasons = near_52w_low_signal(row)
    p_ok, p_reasons = piotroski_ok(fund)
    cc_ok, cc_reasons = coffee_can_signal(fund)

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
    return results
