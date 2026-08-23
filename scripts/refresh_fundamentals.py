"""Weekly job: rebuilds the fundamentals cache (P/E, P/B, ROE, D/E, Coffee Can, F-Score)
for the whole universe. Slow (~2 requests/ticker) -- not meant to run daily."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screener.universe import load_universe
from screener.fundamentals import refresh_cache

if __name__ == "__main__":
    universe = load_universe()
    yf_symbols = [u["yf_symbol"] for u in universe]
    print(f"Refreshing fundamentals cache for {len(yf_symbols)} tickers...")
    rows = refresh_cache(yf_symbols)
    print(f"Done. Wrote {len(rows)} rows to data/fundamentals_cache.csv")
