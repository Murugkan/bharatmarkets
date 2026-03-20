"""
fetch_prices.py
───────────────
Fetches NSE stock quotes + 5-year chart history via yfinance.
Run by GitHub Actions on a schedule.

Writes:
  prices.json          — latest quotes for all symbols
  charts/SYMBOL.json   — 5yr daily OHLCV for each symbol
"""

import json, sys, os, time
from datetime import datetime, timezone

try:
    import yfinance as yf
except ImportError:
    print("ERROR: yfinance not installed. Run: pip install yfinance")
    sys.exit(1)

DEFAULT_SYMBOLS = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
    "SBIN", "BHARTIARTL", "HINDUNILVR", "ITC", "KOTAKBANK",
    "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "TITAN",
]

def load_symbols():
    try:
        with open("watchlist.txt") as f:
            syms = [l.strip().upper() for l in f if l.strip() and not l.startswith("#")]
        if syms:
            print(f"Loaded {len(syms)} symbols from watchlist.txt")
            return syms
    except FileNotFoundError:
        pass
    print(f"Using {len(DEFAULT_SYMBOLS)} default symbols")
    return DEFAULT_SYMBOLS

def fetch_all(symbols):
    os.makedirs("charts", exist_ok=True)
    ns_syms = [s + ".NS" for s in symbols]
    tickers  = yf.Tickers(" ".join(ns_syms))
    quotes   = {}

    for raw, sym in zip(ns_syms, symbols):
        print(f"  {sym}…", end=" ", flush=True)
        try:
            t    = tickers.tickers[raw]
            fi   = t.fast_info

            # 5-year history — used for both MA calc and chart data
            hist5 = t.history(period="5y", interval="1d", auto_adjust=True)

            ltp  = round(float(fi.last_price),    2)
            prev = round(float(fi.previous_close), 2)
            chg  = round(ltp - prev, 2)
            pct  = round(chg / prev * 100, 3) if prev else 0.0

            ma50  = round(float(hist5["Close"].tail(50).mean()),  2) if len(hist5) >= 50  else None
            ma200 = round(float(hist5["Close"].tail(200).mean()), 2) if len(hist5) >= 200 else None

            info = {}
            try:
                info = t.info
            except Exception:
                pass

            quotes[sym] = {
                "ltp":       ltp,
                "prev":      prev,
                "change":    chg,
                "changePct": pct,
                "open":      round(float(fi.open),      2) if fi.open      else None,
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

            # ── Write chart file ──────────────────────────────────────
            chart_rows = []
            for ts, row in hist5.iterrows():
                try:
                    chart_rows.append({
                        "d": ts.strftime("%Y-%m-%d"),
                        "o": round(float(row["Open"]),   2),
                        "h": round(float(row["High"]),   2),
                        "l": round(float(row["Low"]),    2),
                        "c": round(float(row["Close"]),  2),
                        "v": int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
                    })
                except Exception:
                    pass

            chart_payload = {
                "sym":     sym,
                "updated": datetime.now(timezone.utc).isoformat(),
                "bars":    chart_rows,
            }
            with open(f"charts/{sym}.json", "w") as f:
                json.dump(chart_payload, f, separators=(',', ':'))  # compact — smaller file

            print(f"✓  ({len(chart_rows)} bars)")

        except Exception as e:
            print(f"⚠  {e}")
            quotes[sym] = {"error": str(e)}

        time.sleep(0.3)

    return quotes

def write_prices(quotes):
    payload = {"updated": datetime.now(timezone.utc).isoformat(), "quotes": quotes}
    with open("prices.json", "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\n✓ prices.json  — {len(quotes)} symbols")
    print(f"✓ charts/      — {len(os.listdir('charts'))} files")

if __name__ == "__main__":
    syms   = load_symbols()
    quotes = fetch_all(syms)
    write_prices(quotes)
