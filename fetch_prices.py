"""
fetch_prices.py
───────────────
Fetches NSE stock quotes via yfinance and writes prices.json.
Run by GitHub Actions on a schedule.

Reads symbols from watchlist.txt (one per line, no .NS suffix).
Falls back to a hardcoded default list if the file doesn't exist.

Output format  prices.json:
{
  "updated": "2024-01-15T09:30:00+00:00",
  "quotes": {
    "RELIANCE": {
      "ltp": 2450.50, "prev": 2430.00, "change": 20.50, "changePct": 0.844,
      "open": 2435.00, "high": 2460.00, "low": 2428.00, "vol": 5234567,
      "w52h": 3024.90, "w52l": 2220.05, "mktCap": 1657000000000,
      "ma50": 2380.42, "ma200": 2301.18, "name": "Reliance Industries Limited",
      "pe": 24.5, "fwdPe": 21.3, "pb": 2.1, "divYield": 0.0034,
      "eps": 100.02, "bv": 1167.30, "avgVol": 4800000
    },
    ...
  }
}
"""

import json
import sys
import os
import time
from datetime import datetime, timezone

try:
    import yfinance as yf
except ImportError:
    print("ERROR: yfinance not installed. Run: pip install yfinance")
    sys.exit(1)


# ── Load symbols ────────────────────────────────────────────────────────────

DEFAULT_SYMBOLS = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
    "SBIN", "BHARTIARTL", "HINDUNILVR", "ITC", "KOTAKBANK",
    "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "TITAN",
]

def load_symbols():
    try:
        with open("watchlist.txt", "r") as f:
            syms = [line.strip().upper() for line in f if line.strip() and not line.startswith("#")]
        if syms:
            print(f"Loaded {len(syms)} symbols from watchlist.txt")
            return syms
    except FileNotFoundError:
        pass
    print(f"watchlist.txt not found — using {len(DEFAULT_SYMBOLS)} default symbols")
    return DEFAULT_SYMBOLS


# ── Fetch ────────────────────────────────────────────────────────────────────

def fetch_quotes(symbols):
    ns_symbols = [s + ".NS" for s in symbols]
    print(f"Fetching {len(ns_symbols)} NSE symbols via yfinance…")

    # Fetch all tickers at once
    tickers = yf.Tickers(" ".join(ns_symbols))

    out = {}
    for raw_sym, sym in zip(ns_symbols, symbols):
        print(f"  {sym}…", end=" ", flush=True)
        try:
            t   = tickers.tickers[raw_sym]

            # fast_info is lighter-weight than .info
            fi  = t.fast_info

            # 1-year daily history for MA50/MA200
            hist = t.history(period="1y", interval="1d", auto_adjust=True)

            ltp  = round(float(fi.last_price),    2)
            prev = round(float(fi.previous_close), 2)
            chg  = round(ltp - prev, 2)
            pct  = round((chg / prev) * 100, 3) if prev else 0.0

            ma50  = None
            ma200 = None
            if len(hist) >= 50:
                ma50  = round(float(hist["Close"].tail(50).mean()),  2)
            if len(hist) >= 200:
                ma200 = round(float(hist["Close"].tail(200).mean()), 2)

            # .info for fundamentals (slightly slower)
            info = {}
            try:
                info = t.info
            except Exception:
                pass

            out[sym] = {
                "ltp":       ltp,
                "prev":      prev,
                "change":    chg,
                "changePct": pct,
                "open":      round(float(fi.open),     2) if fi.open     else None,
                "high":      round(float(fi.day_high),  2) if fi.day_high  else None,
                "low":       round(float(fi.day_low),   2) if fi.day_low   else None,
                "vol":       int(fi.three_month_average_volume) if fi.three_month_average_volume else None,
                "avgVol":    info.get("averageVolume"),
                "w52h":      round(float(fi.year_high), 2) if fi.year_high else None,
                "w52l":      round(float(fi.year_low),  2) if fi.year_low  else None,
                "mktCap":    info.get("marketCap"),
                "ma50":      ma50,
                "ma200":     ma200,
                "name":      info.get("longName") or info.get("shortName") or sym,
                "pe":        info.get("trailingPE"),
                "fwdPe":     info.get("forwardPE"),
                "pb":        info.get("priceToBook"),
                "divYield":  info.get("dividendYield"),
                "eps":       info.get("trailingEps"),
                "bv":        info.get("bookValue"),
            }
            print("✓")

        except Exception as e:
            print(f"⚠  {e}")
            # Write a minimal error entry so the app knows the fetch was attempted
            out[sym] = {"error": str(e)}

        # polite pause to avoid rate limiting
        time.sleep(0.3)

    return out


# ── Write ─────────────────────────────────────────────────────────────────────

def write_output(quotes):
    payload = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "quotes":  quotes,
    }
    with open("prices.json", "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\n✓ Wrote {len(quotes)} entries to prices.json")
    print(f"  Timestamp: {payload['updated']}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    syms   = load_symbols()
    quotes = fetch_quotes(syms)
    write_output(quotes)
