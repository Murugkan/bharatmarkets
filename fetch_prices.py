#!/usr/bin/env python3
"""
BharatMarkets Pro — Price & Chart Fetcher
Runs via GitHub Actions every 15 min during NSE hours.
Writes: prices.json, symbols.json, charts/SYM.json
"""

import json, os, time, datetime
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("Run: pip install yfinance")

# ── Config ────────────────────────────────────────────────────
WATCHLIST_FILE = "watchlist.txt"
PRICES_FILE    = "prices.json"
SYMBOLS_FILE   = "symbols.json"
CHARTS_DIR     = Path("charts")
CHARTS_DIR.mkdir(exist_ok=True)

# ── NSE symbol → Yahoo Finance ticker mapping ─────────────────
SPECIAL_MAP = {
    "NIFTY":     "^NSEI",
    "NIFTY50":   "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "SENSEX":    "^BSESN",
    "NIFTYIT":   "^CNXIT",
    "MIDCAP":    "^NSEMDCP50",
}

def to_yf_sym(sym):
    return SPECIAL_MAP.get(sym, sym + ".NS")

# ── Load watchlist ────────────────────────────────────────────
def load_symbols():
    if not Path(WATCHLIST_FILE).exists():
        print(f"⚠  {WATCHLIST_FILE} not found — using defaults")
        return ["RELIANCE","TCS","HDFCBANK","INFY","NIFTY","BANKNIFTY"]
    with open(WATCHLIST_FILE) as f:
        syms = [l.strip().upper() for l in f if l.strip() and not l.startswith("#")]
    print(f"📋 Loaded {len(syms)} symbols from {WATCHLIST_FILE}")
    return syms

# ── Fetch single ticker ───────────────────────────────────────
def fetch_ticker(sym):
    yf_sym = to_yf_sym(sym)
    try:
        t    = yf.Ticker(yf_sym)
        info = t.info or {}
        hist = t.history(period="5y", interval="1d", auto_adjust=True)
        return info, hist
    except Exception as e:
        print(f"  ✗ {sym} ({yf_sym}): {e}")
        return {}, None

# ── Build prices.json quote ───────────────────────────────────
def build_quote(sym, info, hist):
    ltp  = (info.get("currentPrice")
         or info.get("regularMarketPrice")
         or info.get("previousClose"))
    prev = info.get("previousClose") or ltp

    # Fallback to last hist bar if info is empty
    if not ltp and hist is not None and not hist.empty:
        ltp  = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else ltp

    if not ltp:
        return None

    ltp  = round(float(ltp), 2)
    prev = round(float(prev), 2) if prev else ltp
    chg  = round(ltp - prev, 2)
    pct  = round(chg / prev * 100, 3) if prev else 0

    def safe(val, mult=1, dp=2):
        try:
            return round(float(val) * mult, dp) if val not in (None, "N/A", "Infinity") else None
        except:
            return None

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
        "roe":       safe(info.get("returnOnEquity"), mult=100),
        "divYield":  safe(info.get("dividendYield")),
        "w52h":      safe(info.get("fiftyTwoWeekHigh")),
        "w52l":      safe(info.get("fiftyTwoWeekLow")),
        "ma50":      safe(info.get("fiftyDayAverage")),
        "ma200":     safe(info.get("twoHundredDayAverage")),
        "beta":      safe(info.get("beta")),
    }

# ── Build charts/SYM.json bar data ───────────────────────────
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

    path = CHARTS_DIR / f"{sym}.json"
    with open(path, "w") as f:
        json.dump({"sym": sym, "bars": bars}, f, separators=(",", ":"))
    print(f"  ✓ Chart: {len(bars)} bars → charts/{sym}.json")

# ── Build symbols.json (search index) ────────────────────────
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
    {"sym":"AXISBANK","name":"Axis Bank","sector":"Banks"},
    {"sym":"MARUTI","name":"Maruti Suzuki","sector":"Auto"},
    {"sym":"TITAN","name":"Titan Company","sector":"Consumer"},
    {"sym":"SUNPHARMA","name":"Sun Pharmaceutical","sector":"Pharma"},
    {"sym":"WIPRO","name":"Wipro","sector":"IT"},
    {"sym":"HCLTECH","name":"HCL Technologies","sector":"IT"},
    {"sym":"ADANIENT","name":"Adani Enterprises","sector":"Industrial"},
    {"sym":"BAJFINANCE","name":"Bajaj Finance","sector":"NBFC"},
    {"sym":"NESTLEIND","name":"Nestle India","sector":"FMCG"},
    {"sym":"NTPC","name":"NTPC","sector":"Energy"},
    {"sym":"ONGC","name":"ONGC","sector":"Energy"},
    {"sym":"TATASTEEL","name":"Tata Steel","sector":"Metals"},
    {"sym":"JSWSTEEL","name":"JSW Steel","sector":"Metals"},
    {"sym":"TATAMOTORS","name":"Tata Motors","sector":"Auto"},
    {"sym":"ZOMATO","name":"Zomato","sector":"Consumer"},
    {"sym":"DMART","name":"Avenue Supermarts","sector":"Retail"},
    {"sym":"IRCTC","name":"IRCTC","sector":"Consumer"},
    {"sym":"TRENT","name":"Trent","sector":"Retail"},
    {"sym":"DIXON","name":"Dixon Technologies","sector":"Consumer Electronics"},
    {"sym":"IRFC","name":"IRFC","sector":"Finance"},
    {"sym":"KIOCL","name":"KIOCL Limited","sector":"Metals"},
    {"sym":"TATAELXSI","name":"Tata Elxsi","sector":"IT"},
    {"sym":"KPIT","name":"KPIT Technologies","sector":"IT"},
    {"sym":"PERSISTENT","name":"Persistent Systems","sector":"IT"},
    {"sym":"COFORGE","name":"Coforge","sector":"IT"},
    {"sym":"DRREDDY","name":"Dr. Reddy's","sector":"Pharma"},
    {"sym":"CIPLA","name":"Cipla","sector":"Pharma"},
    {"sym":"LUPIN","name":"Lupin","sector":"Pharma"},
    {"sym":"APOLLOHOSP","name":"Apollo Hospitals","sector":"Healthcare"},
    {"sym":"COALINDIA","name":"Coal India","sector":"Energy"},
    {"sym":"BPCL","name":"BPCL","sector":"Energy"},
    {"sym":"TATAPOWER","name":"Tata Power","sector":"Energy"},
    {"sym":"ADANIGREEN","name":"Adani Green Energy","sector":"Energy"},
    {"sym":"DLF","name":"DLF","sector":"Real Estate"},
    {"sym":"VEDL","name":"Vedanta","sector":"Metals"},
    {"sym":"SAIL","name":"SAIL","sector":"Metals"},
    {"sym":"NMDC","name":"NMDC","sector":"Metals"},
    {"sym":"PNB","name":"Punjab National Bank","sector":"Banks"},
    {"sym":"BANKBARODA","name":"Bank of Baroda","sector":"Banks"},
    {"sym":"FEDERALBNK","name":"Federal Bank","sector":"Banks"},
    {"sym":"IDFCFIRSTB","name":"IDFC First Bank","sector":"Banks"},
    {"sym":"GAIL","name":"GAIL India","sector":"Energy"},
    {"sym":"IOC","name":"Indian Oil","sector":"Energy"},
    {"sym":"NYKAA","name":"Nykaa","sector":"Consumer"},
    {"sym":"PAYTM","name":"Paytm","sector":"FinTech"},
    {"sym":"POLICYBZR","name":"PolicyBazaar","sector":"FinTech"},
    {"sym":"ANGELONE","name":"Angel One","sector":"Finance"},
    {"sym":"CDSL","name":"CDSL","sector":"Finance"},
    {"sym":"PIIND","name":"PI Industries","sector":"Chemicals"},
    {"sym":"DEEPAKNTR","name":"Deepak Nitrite","sector":"Chemicals"},
    {"sym":"NAVINFLUOR","name":"Navin Fluorine","sector":"Chemicals"},
    {"sym":"ASTRAL","name":"Astral","sector":"Consumer"},
    {"sym":"GODREJPROP","name":"Godrej Properties","sector":"Real Estate"},
    {"sym":"BAJAJ-AUTO","name":"Bajaj Auto","sector":"Auto"},
    {"sym":"EICHERMOT","name":"Eicher Motors","sector":"Auto"},
    {"sym":"HEROMOTOCO","name":"Hero MotoCorp","sector":"Auto"},
    {"sym":"TVSMOTOR","name":"TVS Motor","sector":"Auto"},
    {"sym":"INDIGO","name":"IndiGo Airlines","sector":"Aviation"},
    {"sym":"MPHASIS","name":"Mphasis","sector":"IT"},
    {"sym":"LTIM","name":"LTIMindtree","sector":"IT"},
    {"sym":"TECHM","name":"Tech Mahindra","sector":"IT"},
    {"sym":"HDFCLIFE","name":"HDFC Life Insurance","sector":"Insurance"},
    {"sym":"SBILIFE","name":"SBI Life Insurance","sector":"Insurance"},
    {"sym":"ICICIGI","name":"ICICI Lombard","sector":"Insurance"},
    {"sym":"CHOLAFIN","name":"Cholamandalam Finance","sector":"NBFC"},
    {"sym":"MUTHOOTFIN","name":"Muthoot Finance","sector":"NBFC"},
    {"sym":"SHREECEM","name":"Shree Cement","sector":"Cement"},
    {"sym":"ULTRACEMCO","name":"UltraTech Cement","sector":"Cement"},
    {"sym":"ASIANPAINT","name":"Asian Paints","sector":"Consumer"},
    {"sym":"BERGEPAINT","name":"Berger Paints","sector":"Consumer"},
    {"sym":"PIDILITIND","name":"Pidilite Industries","sector":"Consumer"},
    {"sym":"BRITANNIA","name":"Britannia Industries","sector":"FMCG"},
    {"sym":"DABUR","name":"Dabur India","sector":"FMCG"},
    {"sym":"MARICO","name":"Marico","sector":"FMCG"},
    {"sym":"GODREJCP","name":"Godrej Consumer","sector":"FMCG"},
    {"sym":"TATACONSUM","name":"Tata Consumer","sector":"FMCG"},
    {"sym":"INDUSINDBK","name":"IndusInd Bank","sector":"Banks"},
    {"sym":"YESBANK","name":"Yes Bank","sector":"Banks"},
    {"sym":"AUBANK","name":"AU Small Finance Bank","sector":"Banks"},
    {"sym":"NAUKRI","name":"Info Edge (Naukri)","sector":"IT"},
    {"sym":"ZYDUSLIFE","name":"Zydus Lifesciences","sector":"Pharma"},
    {"sym":"BIOCON","name":"Biocon","sector":"Pharma"},
    {"sym":"TORNTPHARM","name":"Torrent Pharma","sector":"Pharma"},
    {"sym":"AUROPHARMA","name":"Aurobindo Pharma","sector":"Pharma"},
    {"sym":"DIVISLAB","name":"Divi's Labs","sector":"Pharma"},
    {"sym":"LALPATHLAB","name":"Dr. Lal PathLabs","sector":"Healthcare"},
    {"sym":"POWERGRID","name":"Power Grid Corp","sector":"Energy"},
    {"sym":"HINDALCO","name":"Hindalco","sector":"Metals"},
    {"sym":"GRASIM","name":"Grasim","sector":"Industrial"},
    {"sym":"BAJAJFINSV","name":"Bajaj Finserv","sector":"NBFC"},
    {"sym":"M&M","name":"Mahindra & Mahindra","sector":"Auto"},
]

def build_symbols_index(quotes):
    for entry in UNIVERSE:
        q = quotes.get(entry["sym"])
        if q:
            if q.get("sector"): entry["sector"] = q["sector"]
            if q.get("name"):   entry["name"]   = q["name"]
    with open(SYMBOLS_FILE, "w") as f:
        json.dump(UNIVERSE, f, separators=(",", ":"))
    print(f"✓ symbols.json → {len(UNIVERSE)} symbols")

# ── Main ──────────────────────────────────────────────────────
def main():
    symbols = load_symbols()
    print(f"\n📊 BharatMarkets Pro Fetch")
    print(f"🕐 {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"📋 {len(symbols)} symbols\n")

    quotes = {}
    errors = []

    for sym in symbols:
        print(f"→ {sym}")
        info, hist = fetch_ticker(sym)
        quote = build_quote(sym, info, hist)
        if quote:
            quotes[sym] = quote
            print(f"  ✓ ₹{quote['ltp']} ({quote['changePct']:+.2f}%)")
        else:
            errors.append(sym)
            print(f"  ✗ No data")
        if hist is not None and not hist.empty:
            build_chart(sym, hist)
        time.sleep(0.5)  # polite delay — avoid rate limiting

    # Write prices.json
    payload = {
        "updated": datetime.datetime.utcnow().isoformat() + "Z",
        "count":   len(quotes),
        "quotes":  quotes,
    }
    with open(PRICES_FILE, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    print(f"\n✓ prices.json → {len(quotes)} quotes")

    if errors:
        print(f"⚠  Failed symbols ({len(errors)}): {', '.join(errors)}")

    build_symbols_index(quotes)
    print(f"\n✅ Complete — {datetime.datetime.utcnow().strftime('%H:%M UTC')}\n")

if __name__ == "__main__":
    main()
