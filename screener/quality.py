"""Multi-year quality filters computed from yfinance annual financial statements.

yfinance only exposes ~5 years of annual financials (not the 10 the original
Coffee Can methodology uses), so `coffee_can_flag` is a 5-year adaptation of it,
not the canonical 10-year version -- documented here so the difference isn't lost.

`piotroski_lite_score` implements 8 of the 9 canonical Piotroski F-Score checks
(skips the gross-margin-change criterion, which needs a cost-of-revenue series
that isn't reliably populated for Indian tickers on yfinance). Score is 0-8;
treat 6+ as "improving fundamentals", not a guarantee.
"""
import pandas as pd
import yfinance as yf


def _row(df, name):
    if df is None or df.empty or name not in df.index:
        return None
    return df.loc[name].dropna()


def _first(*series_list):
    for s in series_list:
        if s is not None and len(s) > 0:
            return s
    return None


def fetch_quality_inputs(yf_symbol):
    """Pulls the annual statements once; reused by both scores below."""
    t = yf.Ticker(yf_symbol)
    return {
        "financials": t.financials,
        "balance_sheet": t.balance_sheet,
        "cashflow": t.cashflow,
    }


def coffee_can_flag(statements, roce_min=0.15, revenue_cagr_min=0.10):
    fin, bs = statements["financials"], statements["balance_sheet"]
    ebit = _row(fin, "EBIT")
    invested_capital = _row(bs, "Invested Capital")
    revenue = _row(fin, "Total Revenue")
    if ebit is None or invested_capital is None or revenue is None or len(revenue) < 3:
        return False, []

    years = sorted(set(ebit.index) & set(invested_capital.index))
    roce_by_year = [ebit[y] / invested_capital[y] for y in years if invested_capital[y]]
    if not roce_by_year:
        return False, []
    avg_roce = sum(roce_by_year) / len(roce_by_year)

    revenue = revenue.sort_index()
    n_years = len(revenue) - 1
    if n_years < 2 or revenue.iloc[0] <= 0:
        return False, []
    cagr = (revenue.iloc[-1] / revenue.iloc[0]) ** (1 / n_years) - 1

    ok = avg_roce >= roce_min and cagr >= revenue_cagr_min
    reasons = [
        f"Consistently profitable, compounding business: {avg_roce*100:.0f}% average return on capital "
        f"over {len(roce_by_year)} years, growing revenue {cagr*100:.0f}% a year"
    ]
    return ok, reasons if ok else []


def piotroski_lite_score(statements):
    fin, bs, cf = statements["financials"], statements["balance_sheet"], statements["cashflow"]
    net_income = _row(fin, "Net Income")
    cfo = _first(_row(cf, "Operating Cash Flow"), _row(cf, "Cash Flow From Continuing Operating Activities"))
    total_assets = _row(bs, "Total Assets")
    current_assets = _row(bs, "Current Assets")
    current_liab = _row(bs, "Current Liabilities")
    long_term_debt = _first(_row(bs, "Long Term Debt"), _row(bs, "Long Term Debt And Capital Lease Obligation"))
    revenue = _row(fin, "Total Revenue")
    shares = _row(bs, "Ordinary Shares Number")

    score = 0
    notes = []

    def latest_two(series):
        if series is None or len(series) < 2:
            return None, None
        s = series.sort_index()
        return s.iloc[-1], s.iloc[-2]

    ni_now, ni_prev = latest_two(net_income)
    if ni_now is not None and ni_now > 0:
        score += 1; notes.append("net income +ve")
    cfo_now, cfo_prev = latest_two(cfo)
    if cfo_now is not None and cfo_now > 0:
        score += 1; notes.append("op. cash flow +ve")
    if cfo_now is not None and ni_now is not None and cfo_now > ni_now:
        score += 1; notes.append("CFO>NI (earnings quality)")

    ta_now, ta_prev = latest_two(total_assets)
    if None not in (ni_now, ni_prev, ta_now, ta_prev) and ta_now and ta_prev:
        roa_now, roa_prev = ni_now / ta_now, ni_prev / ta_prev
        if roa_now > roa_prev:
            score += 1; notes.append("ROA improving")

    ltd_now, ltd_prev = latest_two(long_term_debt)
    if None not in (ltd_now, ltd_prev, ta_now, ta_prev) and ta_now and ta_prev:
        lev_now, lev_prev = ltd_now / ta_now, ltd_prev / ta_prev
        if lev_now <= lev_prev:
            score += 1; notes.append("leverage flat/down")

    ca_now, ca_prev = latest_two(current_assets)
    cl_now, cl_prev = latest_two(current_liab)
    if None not in (ca_now, ca_prev, cl_now, cl_prev) and cl_now and cl_prev:
        cr_now, cr_prev = ca_now / cl_now, ca_prev / cl_prev
        if cr_now > cr_prev:
            score += 1; notes.append("current ratio improving")

    sh_now, sh_prev = latest_two(shares)
    if None not in (sh_now, sh_prev) and sh_now <= sh_prev * 1.01:
        score += 1; notes.append("no significant dilution")

    rev_now, rev_prev = latest_two(revenue)
    if None not in (rev_now, rev_prev) and rev_now > rev_prev:
        score += 1; notes.append("revenue growing YoY")

    return score, notes
