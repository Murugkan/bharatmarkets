#!/usr/bin/env python3
"""
BharatMarkets Pro — Price & Chart Fetcher v2
Fixes:
  - TATAMOTORS / any symbol 404: retry with fresh session + fallback to history
  - datetime.utcnow() deprecation warning
  - Reads portfolio_symbols.txt + watchlist.txt (merged)
  - ROE: correct decimal→% conversion
"""

import json, time, datetime, os
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
    # ── Indices ────────────────────────────────────────────────────────
    "NIFTY":         "^NSEI",
    "NIFTY50":       "^NSEI",
    "BANKNIFTY":     "^NSEBANK",
    "SENSEX":        "^BSESN",
    "NIFTYIT":       "^CNXIT",
    "MIDCAP":        "^NSEMDCP50",
    # ── Company renamed — Yahoo dropped old ticker ─────────────────────
    "ZINKA":         "BLACKBUCK.NS",   # Renamed to BlackBuck Aug 2025
    "CIGNITI":       "CIGNITITEC.NS",  # Relisted after Coforge acquisition
    "CIGNITITECH":   "CIGNITITEC.NS",
    # ── Renamed/merged companies ───────────────────────────────────────
    "AMARAJAB":      "ARE&M.NS",
    "AMARAJABAT":    "ARE&M.NS",
    "ASSALCOHOL":    "ASALCBR.NS",
    "AZADINDIA":     "AZADIND.BO",     # Indian Bright Steel — BSE only
    "MINDTREE":      "LTIM.NS",
    "LTIMINDTREE":   "LTIM.NS",
    "HDFC":          "HDFCBANK.NS",
    "RUCHI":         "RUCHISOYA.NS",
    "BLACKBOXLIMI":  "BBOX.NS",
    # ── CDSL truncation mismatches ─────────────────────────────────────
    "GRAUERWEIL":    "GRAUWEIL.NS",
    "ROSSELLTECH":   "ROSSTECH.NS",
    "INDOTECHTR":    "INDOTECH.NS",
    "SHILCHAR":      "SHILCTECH.NS",
    "HBLPOWER":      "HBLENGINE.NS",
    "KPENERGI":      "KPEL.NS",
    "MBENGINEERING": "MBEL.NS",      # Confirmed Yahoo ticker: MBEL.NS
    "CAPITALNUMB":   "CNINFOTECH.BO",  # BSE only
    "KWALYPH":       "KPL.BO",         # BSE only
    "KWALITYPHARM":  "KPL.BO",         # BSE only
    # ── Special characters ─────────────────────────────────────────────
    "M&M":           "M%26M.NS",
    "M&MFIN":        "M%26MFIN.NS",
    "MCDOWELL-N":    "UNITDSPR.NS",    # Hyphen breaks yfinance
    "SSPOWERSWIT":   "S%26SPOWER.NS",  # & must be %26
    # ── BSE-only ───────────────────────────────────────────────────────
    "TITANBIOTE":    "TITANBIO.BO",
    "HIGHENERGYB":   "HIGHENE.BO",
    "SIKAINTERP":    "SIKA.BO",
    "SHREEREFRI":    "SHREEREF.BO",
    "SKMEPEX":       "SKMEGGPROD.NS",
    # ── CDSL truncation — name search works in fundamentals but not here ─
    "REVATHI":       "RVTH.NS",      # REVATHI EQUIPMENT INDIA L → RVTH
    "IGI":           "IGIL.NS",      # INTERNATIO GEMM INS (I) L → IGIL
    "SUYOGTELE":     "SUYOG.NS",     # Suyog Telematics Ltd → SUYOG
    "QUALPOWER":     "QPOWER.NS",    # QUALITY POWER ELEC EQUP L → QPOWER
    "CELLOWORLD":    "CELLO.NS",     # CELLO WORLD LIMITED → CELLO
    "HINDRECTIF":    "HIRECT.NS",    # Hind Rectifiers Ltd → HIRECT
    # ── Merged banks ───────────────────────────────────────────────────
    "ORIENTBANK":    "PNB.NS",
    "CORPBANK":      "UCOBANK.NS",
    "SYNDIBANK":     "CANBK.NS",
    "ANDHRBANK":     "UCOBANK.NS",
    "ALLBANK":       "INDIANB.NS",
    "DENABANK":      "BANKBARODA.NS",
    "VIJAYABANK":    "BANKBARODA.NS",
}
SKIP = {"NIFTY","BANKNIFTY","NIFTY50","SENSEX","NIFTYIT","MIDCAP","SMALLCAP","NIFTYBANK"}

def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)

def to_yf(sym):
    mapped = SPECIAL_MAP.get(sym)
    if mapped:
        # If mapped value already has .NS or starts with ^, use as-is
        return mapped if ("." in mapped or mapped.startswith("^")) else mapped + ".NS"
    return sym + ".NS"

def load_symbols():
    """Load symbols from portfolio_symbols.txt then watchlist.txt.
    Supports SYM|CDSL Company Name format — name part stripped here,
    only the symbol is needed for price fetching.
    """
    syms, seen = [], set()
    # 1. Portfolio symbols first
    if Path(PORTFOLIO_FILE).exists():
        for line in Path(PORTFOLIO_FILE).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"): continue
            s = line.split("|")[0].strip().upper()  # strip |Name if present
            if s and s not in seen:
                syms.append(s); seen.add(s)
        print(f"📂 {len(syms)} from {PORTFOLIO_FILE}")
    # 2. Watchlist extras
    if Path(WATCHLIST_FILE).exists():
        extras = 0
        for line in Path(WATCHLIST_FILE).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"): continue
            s = line.split("|")[0].strip().upper()
            if s and s not in seen:
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
            # Try BSE (.BO) as fallback before giving up
            try:
                t_bo = yf.Ticker(sym + ".BO")
                hist_bo = t_bo.history(period="1mo", interval="1d", auto_adjust=True)
                if hist_bo is not None and not hist_bo.empty:
                    print(f"  ⚠ {sym}: NSE not found, using BSE (.BO)")
                    try:    info_bo = t_bo.info or {}
                    except: info_bo = {}
                    return info_bo, hist_bo
            except Exception:
                pass
            print(f"  ✗ {sym}: not found on NSE or BSE — skipping")
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

    # ── Single symbol mode (triggered by watchlist add) ──────────────
    single = os.environ.get('SINGLE_SYMBOL','').strip().upper()
    if single:
        print(f"🎯 Single symbol mode: {single}")
        symbols = [single]

    ts = now_utc()
    print(f"📊 BharatMarkets Price Fetch v2")
    print(f"🕐 {ts.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"📋 {len(symbols)} symbols\n")

    quotes, errors = {}, []

    # ── Separate equity symbols from indices ──────────────────────────
    index_syms = [s for s in symbols if s in SPECIAL_MAP]
    equity_syms = [s for s in symbols if s not in SPECIAL_MAP]

    # ── Batch download equities via yfinance.download (much faster) ──
    # yf.download fetches all tickers in parallel in one HTTP session
    yf_tickers = [to_yf(s) for s in equity_syms]
    print(f"⚡ Batch downloading {len(yf_tickers)} equity tickers…")
    try:
        batch_hist = yf.download(
            tickers = " ".join(yf_tickers),
            period  = "5y",
            interval= "1d",
            auto_adjust=True,
            group_by="ticker",
            progress=False,
            threads=True,
        )
        print(f"  ✓ Batch download complete")
    except Exception as e:
        print(f"  ✗ Batch download failed: {e} — falling back to individual")
        batch_hist = None

    # Process each equity symbol
    for sym in equity_syms:
        yf_sym = to_yf(sym)
        hist = None

        # Extract from batch if available
        if batch_hist is not None and not batch_hist.empty:
            try:
                if len(equity_syms) == 1:
                    hist = batch_hist
                elif yf_sym in batch_hist.columns.get_level_values(0):
                    hist = batch_hist[yf_sym].dropna(how='all')
                elif yf_sym in batch_hist.columns.get_level_values(1):
                    hist = batch_hist.xs(yf_sym, axis=1, level=1).dropna(how='all')
            except Exception:
                hist = None

        # Fallback to individual fetch if batch missed this symbol
        if hist is None or hist.empty:
            _, hist = fetch_ticker(sym)

        # Get info separately (batch doesn't provide fundamentals)
        info = {}
        try:
            t = yf.Ticker(yf_sym)
            info = t.info or {}
        except Exception:
            pass

        if hist is not None and not hist.empty:
            # Price fallback from history if info has no price
            if not info.get("currentPrice") and not info.get("regularMarketPrice"):
                closes = hist["Close"].dropna()
                if not closes.empty:
                    info["currentPrice"]  = float(closes.iloc[-1])
                    info["previousClose"] = float(closes.iloc[-2]) if len(closes)>=2 else float(closes.iloc[-1])

        q = build_quote(sym, info, hist)
        if q:
            quotes[sym] = q
            print(f"  ✓ {sym}: ₹{q['ltp']} ({q['changePct']:+.2f}%)")
        else:
            errors.append(sym)
        if hist is not None and not hist.empty:
            build_chart(sym, hist)

    # ── Process indices individually (they don't work in batch) ──
    print(f"\n📈 Fetching {len(index_syms)} indices…")
    for sym in index_syms:
        info, hist = fetch_ticker(sym)
        q = build_quote(sym, info, hist)
        if q:
            quotes[sym] = q
            print(f"  ✓ {sym}: {q['ltp']}")
        if hist is not None and not hist.empty:
            build_chart(sym, hist)
        time.sleep(0.3)


    # In single symbol mode, merge new quote into existing prices.json
    if os.environ.get('SINGLE_SYMBOL','').strip():
        try:
            existing_q = json.loads(Path(PRICES_FILE).read_text()).get("quotes",{})
            existing_q.update(quotes)
            quotes = existing_q
        except: pass

    payload = {
        "updated": now_utc().isoformat(),
        "count":   len(quotes),
        "quotes":  quotes,
    }
    Path(PRICES_FILE).write_text(json.dumps(payload, separators=(",",":")))
    print(f"\n✓ prices.json → {len(quotes)} quotes")
    if errors:
        print(f"⚠  Failed: {', '.join(errors)}")
    build_symbols_index(quotes)
    print(f"\n✅ Done {now_utc().strftime('%H:%M UTC')}\n")
if __name__ == "__main__":
    main()
