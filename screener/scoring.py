"""Combines a stock's fired strategies into one conviction score, so a noisy
day (hundreds of individual strategy fires) still surfaces a short, rankable
shortlist instead of a wall of names -- the CSV/HTML keep the full breakdown."""

STRATEGY_WEIGHTS = {
    "value_trend_combo": 3,
    "pure_technical_swing": 2,
    "pure_value": 3,
    "coffee_can_compounder": 2,
    "minervini_trend": 4,        # strict multi-factor confirmation, rarely fires alone
    "breakout_52w_high": 2,
    "relative_strength_leader": 2,
}

TECHNICAL_STRATEGIES = {
    "value_trend_combo", "pure_technical_swing", "minervini_trend",
    "breakout_52w_high", "relative_strength_leader",
}
MACRO_TAILWIND_BONUS = 0.5
MACRO_HEADWIND_PENALTY = 1.0


def score_hits(hits_by_symbol, macro_mood):
    """hits_by_symbol: dict[yf_symbol] -> {"company": str, "strategies": {name: [reasons]}}.
    Returns list of dicts sorted by score desc:
    {symbol, company, score, strategies: [names], reasons: [str]}."""
    scored = []
    for symbol, entry in hits_by_symbol.items():
        strategies = entry["strategies"]
        if not strategies:
            continue
        base = sum(STRATEGY_WEIGHTS.get(s, 1) for s in strategies)
        if TECHNICAL_STRATEGIES & strategies.keys():
            if macro_mood == "tailwind":
                base += MACRO_TAILWIND_BONUS
            elif macro_mood == "headwind":
                base -= MACRO_HEADWIND_PENALTY
        score = max(0.0, min(10.0, base))

        reasons = []
        for name, r in strategies.items():
            reasons.extend(r)

        scored.append({
            "symbol": entry.get("display_symbol", symbol),
            "company": entry["company"],
            "score": round(score, 1),
            "strategies": sorted(strategies.keys()),
            "reasons": reasons,
            "price": entry.get("price"),
            "trend": entry.get("trend"),
            "spark": entry.get("spark", []),
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored
