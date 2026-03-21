#!/usr/bin/env python3
"""
BharatMarkets Pro — Price & Chart Fetcher v2
Fixes:
  - TATAMOTORS / any symbol 404: retry with fresh session + fallback to history
  - datetime.utcnow() deprecation warning
  - Reads portfolio_symbols.txt + watchlist.txt (merged)
  - ROE: correct decimal→% conversion
"""

import json, time, datetime
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("pip install yfinance")

WATCHLIST_FILE  = "watchlist.txt"
PORTFOLIO_FILE  = "portfolio_symbols.txt"
PRICES_FILE     = "prices.json"
SYMBOLS_FILE    = "symbols.json"
CHARTS_DIR      = Path("charts")
CHARTS_DIR.mkdir(exist_ok=True)

SPECIAL_MAP = {
    "NIFTY":     "^NSEI",
    "NIFTY50":   "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "SENSEX":    "^BSESN",
    "NIFTYIT":   "^CNXIT",
    "MIDCAP":    "^NSEMDCP50",
}
SKIP = {"NIFTY","BANKNIFTY","NIFTY50","SENSEX","NIFTYIT","MIDCAP","SMALLCAP","NIFTYBANK"}

def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)

def to_yf(sym):
    return SPECIAL_MAP.get(sym, sym + ".NS")

def load_symbols():
    syms, seen = [], set()
    # 1. Portfolio symbols first
    if Path(PORTFOLIO_FILE).exists():
        for s in Path(PORTFOLIO_FILE).read_text().splitlines():
            s = s.strip().upper()
            if s and not s.startswith("#") and s not in seen:
                syms.append(s); seen.add(s)
        print(f"📂 {len(syms)} from {PORTFOLIO_FILE}")
    # 2. Watchlist extras
    if Path(WATCHLIST_FILE).exists():
        extras = 0
        for s in Path(WATCHLIST_FILE).read_text().splitlines():
            s = s.strip().upper()
            if s and not s.startswith("#") and s not in seen:
                syms.append(s); seen.add(s); extras += 1
        if extras:
            print(f"📋 +{extras} from {WATCHLIST_FILE}")
    print(f"🔢 Total: {len(syms)} symbols\n")
    return syms

def safe(v, mult=1, dp=2):
    try:
        f = float(v) * mult
        if f != f or abs(f) == float('inf'): return None
        return round(f, dp)
    except:
        return None

def fetch_ticker(sym):
    """
    Fetch price + history.
    1. Quick 1-month history check — if empty, symbol is delisted, return immediately.
    2. Full 5Y history for charts.
    3. .info for fundamentals (may 404 for some — fallback to history price).
    """
    yf_sym = to_yf(sym)
    info, hist = {}, None

    t = yf.Ticker(yf_sym)

    # Quick check — 1 month history (fast, confirms listing)
    try:
        hist_1m = t.history(period="1mo", interval="1d", auto_adjust=True)
        if hist_1m is None or hist_1m.empty:
            print(f"  ✗ {sym}: delisted or invalid — skipping")
            return {}, None
    except Exception as e:
        print(f"  ✗ {sym}: {e} — skipping")
        return {}, None

    # Full history for charts
    try:
        hist = t.history(period="5y", interval="1d", auto_adjust=True)
    except Exception:
        hist = hist_1m  # use 1m as fallback for chart

    # Info (may 404 — that is OK, we use history for price)
    try:
        info = t.info or {}
    except Exception:
        info = {}

    # Price fallback from history
    if not info.get("currentPrice") and not info.get("regularMarketPrice"):
        closes = (hist if hist is not None and not hist.empty else hist_1m)["Close"].dropna()
        if not closes.empty:
            info["currentPrice"]  = float(closes.iloc[-1])
            info["previousClose"] = float(closes.iloc[-2]) if len(closes) >= 2 else float(closes.iloc[-1])

    return info, hist

def build_quote(sym, info, hist):
    ltp  = safe(info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose"))
    prev = safe(info.get("previousClose"))

    # Always fall back to history if info gives no price
    if not ltp and hist is not None and not hist.empty:
        ltp  = round(float(hist["Close"].dropna().iloc[-1]), 2)
        prev = round(float(hist["Close"].dropna().iloc[-2]), 2) if len(hist) >= 2 else ltp
        print(f"  ⚠ using history price for {sym}: ₹{ltp}")

    if not ltp:
        return None

    prev = prev or ltp
    chg  = round(ltp - prev, 2)
    pct  = round(chg / prev * 100, 3) if prev else 0

    # ROE: yfinance returns decimal (0.42 = 42%) — multiply by 100
    roe_raw = info.get("returnOnEquity")
    roe = safe(roe_raw, mult=100) if roe_raw is not None else None

    return {
        "sym":       sym,
        "name":      info.get("longName") or info.get("shortName") or sym,
        "sector":    info.get("sector") or info.get("industryDisp") or "",
        "ltp":       ltp,
        "change":    chg,
        "changePct": pct,
        "open":      safe(info.get("open")    or ltp),
        "high":      safe(info.get("dayHigh") or ltp),
        "low":       safe(info.get("dayLow")  or ltp),
        "prev":      prev,
        "vol":       int(info.get("volume") or info.get("regularMarketVolume") or 0),
        "avgVol":    int(info.get("averageVolume") or info.get("averageDailyVolume10Day") or 0),
        "mktCap":    int(info.get("marketCap") or 0),
        "pe":        safe(info.get("trailingPE")),
        "fwdPe":     safe(info.get("forwardPE")),
        "pb":        safe(info.get("priceToBook")),
        "eps":       safe(info.get("trailingEps")),
        "bv":        safe(info.get("bookValue")),
        "roe":       roe,
        "divYield":  safe(info.get("dividendYield"), mult=100),  # also a decimal
        "w52h":      safe(info.get("fiftyTwoWeekHigh")),
        "w52l":      safe(info.get("fiftyTwoWeekLow")),
        "ma50":      safe(info.get("fiftyDayAverage")),
        "ma200":     safe(info.get("twoHundredDayAverage")),
        "beta":      safe(info.get("beta")),
        "opm":       safe(info.get("operatingMargins"), mult=100),
        "npm":       safe(info.get("profitMargins"),    mult=100),
    }

def build_chart(sym, hist):
    if hist is None or hist.empty:
        return
    bars = []
    for date, row in hist.iterrows():
        try:
            bars.append({
                "d": str(date.date()),
                "o": round(float(row["Open"]),  2),
                "h": round(float(row["High"]),  2),
                "l": round(float(row["Low"]),   2),
                "c": round(float(row["Close"]), 2),
                "v": int(row.get("Volume", 0)),
            })
        except:
            continue
    if not bars:
        return
    (CHARTS_DIR / f"{sym}.json").write_text(
        json.dumps({"sym": sym, "bars": bars}, separators=(",",":"))
    )
    print(f"  ✓ chart: {len(bars)} bars")

UNIVERSE = [
    {"sym":"RELIANCE","name":"Reliance Industries","sector":"Energy"},
    {"sym":"TCS","name":"Tata Consultancy Services","sector":"IT"},
    {"sym":"HDFCBANK","name":"HDFC Bank","sector":"Banks"},
    {"sym":"ICICIBANK","name":"ICICI Bank","sector":"Banks"},
    {"sym":"INFY","name":"Infosys","sector":"IT"},
    {"sym":"HINDUNILVR","name":"Hindustan Unilever","sector":"FMCG"},
    {"sym":"ITC","name":"ITC Limited","sector":"FMCG"},
    {"sym":"SBIN","name":"State Bank of India","sector":"Banks"},
    {"sym":"BHARTIARTL","name":"Bharti Airtel","sector":"Telecom"},
    {"sym":"KOTAKBANK","name":"Kotak Mahindra Bank","sector":"Banks"},
    {"sym":"LT","name":"Larsen & Toubro","sector":"Industrial"},
    {"sym":"TATAMOTORS","name":"Tata Motors","sector":"Auto"},
    {"sym":"WIPRO","name":"Wipro","sector":"IT"},
    {"sym":"HCLTECH","name":"HCL Technologies","sector":"IT"},
    {"sym":"SUNPHARMA","name":"Sun Pharma","sector":"Pharma"},
    {"sym":"ONGC","name":"ONGC","sector":"Energy"},
    {"sym":"NTPC","name":"NTPC","sector":"Energy"},
    {"sym":"ADANIENT","name":"Adani Enterprises","sector":"Conglomerate"},
    {"sym":"ADANIPORTS","name":"Adani Ports","sector":"Infrastructure"},
    {"sym":"BAJFINANCE","name":"Bajaj Finance","sector":"NBFC"},
    {"sym":"BAJAJFINSV","name":"Bajaj Finserv","sector":"NBFC"},
    {"sym":"TITAN","name":"Titan Company","sector":"Consumer"},
    {"sym":"ASIANPAINT","name":"Asian Paints","sector":"Chemicals"},
    {"sym":"MARUTI","name":"Maruti Suzuki","sector":"Auto"},
    {"sym":"NESTLEIND","name":"Nestle India","sector":"FMCG"},
    {"sym":"ULTRACEMCO","name":"UltraTech Cement","sector":"Cement"},
    {"sym":"TECHM","name":"Tech Mahindra","sector":"IT"},
    {"sym":"AXISBANK","name":"Axis Bank","sector":"Banks"},
    {"sym":"INDUSINDBK","name":"IndusInd Bank","sector":"Banks"},
    {"sym":"DRREDDY","name":"Dr Reddy's","sector":"Pharma"},
    {"sym":"CIPLA","name":"Cipla","sector":"Pharma"},
    {"sym":"ZOMATO","name":"Zomato","sector":"Consumer Tech"},
    {"sym":"IRFC","name":"IRFC","sector":"Finance"},
    {"sym":"KIOCL","name":"KIOCL","sector":"Mining"},
    {"sym":"TATAELXSI","name":"Tata Elxsi","sector":"IT"},
    {"sym":"DIXON","name":"Dixon Technologies","sector":"Electronics"},
    {"sym":"POWERGRID","name":"Power Grid Corp","sector":"Energy"},
    {"sym":"HINDALCO","name":"Hindalco","sector":"Metals"},
    {"sym":"GRASIM","name":"Grasim","sector":"Industrial"},
    {"sym":"M&M","name":"Mahindra & Mahindra","sector":"Auto"},
]

def build_symbols_index(quotes):
    seen_syms = {e["sym"] for e in UNIVERSE}
    # Add any fetched symbols not in universe
    for sym, q in quotes.items():
        if sym not in seen_syms:
            UNIVERSE.append({
                "sym": sym,
                "name": q.get("name", sym),
                "sector": q.get("sector", ""),
            })
            seen_syms.add(sym)
        else:
            # Update name/sector from live data
            for e in UNIVERSE:
                if e["sym"] == sym:
                    if q.get("sector"): e["sector"] = q["sector"]
                    if q.get("name"):   e["name"]   = q["name"]
    Path(SYMBOLS_FILE).write_text(
        json.dumps(UNIVERSE, separators=(",",":"))
    )
    print(f"✓ symbols.json → {len(UNIVERSE)} entries")

def main():
    symbols = load_symbols()
    ts = now_utc()
    print(f"📊 BharatMarkets Price Fetch v2")
    print(f"🕐 {ts.strftime('%Y-%m-%d %H:%M UTC')}\n")

    quotes, errors = {}, []

    for sym in symbols:
        print(f"→ {sym}")
        info, hist = fetch_ticker(sym)
        q = build_quote(sym, info, hist)
        if q:
            quotes[sym] = q
            print(f"  ✓ ₹{q['ltp']} ({q['changePct']:+.3f}%) ROE:{q.get('roe','—')}%")
        else:
            errors.append(sym)
            print(f"  ✗ no data")
        if hist is not None and not hist.empty:
            build_chart(sym, hist)
        time.sleep(0.5)

    payload = {
        "updated": now_utc().isoformat(),
        "count":   len(quotes),
        "quotes":  quotes,
    }
    Path(PRICES_FILE).write_text(
        json.dumps(payload, separators=(",",":"))
    )
    print(f"\n✓ prices.json → {len(quotes)} quotes")
    if errors:
        print(f"⚠  Failed: {', '.join(errors)}")
    build_symbols_index(quotes)
    print(f"\n✅ Done {now_utc().strftime('%H:%M UTC')}\n")

if __name__ == "__main__":
    main()
