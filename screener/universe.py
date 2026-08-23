"""Loads the Nifty 500 ticker universe from the bundled NSE constituent list."""
import csv
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
NIFTY500_CSV = os.path.join(DATA_DIR, "nifty500.csv")


def load_universe():
    """Returns list of (symbol, company_name, industry) for yfinance (.NS suffix)."""
    rows = []
    with open(NIFTY500_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            symbol = r["Symbol"].strip()
            rows.append({
                "yf_symbol": f"{symbol}.NS",
                "symbol": symbol,
                "company": r["Company Name"].strip(),
                "industry": r["Industry"].strip(),
            })
    return rows
