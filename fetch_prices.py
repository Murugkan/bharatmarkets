#!/usr/bin/env python3
"""
BharatMarkets Pro — Price & Chart Fetcher
Reads: symbols.json (single source of truth)
Writes: prices.json, charts/*.json, symbols.json (updated sector/name from live data)
"""

import json, time, datetime
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("pip install yfinance")

SYMBOLS_FILE = "symbols.json"
PRICES_FILE  = "prices.json"
CHARTS_DIR   = Path("charts")
CHARTS_DIR.mkdir(exist_ok=True)

# NSE symbol → Yahoo Finance ticker (only exceptions — most work as SYM.NS)
SPECIAL_MAP = {
    "NIFTY":         "^NSEI",
    "BANKNIFTY":     "^NSEBANK",
    "SENSEX":        "^BSESN",
    "NIFTYMIDCAP100":"^NSEMDCP50",
    "CNXIT":         "^CNXIT",
    "NIFTYPSE":      "^NSEI",      # fallback
    "ZINKA":         "BLACKBUCK.NS",
    "CIGNITI":       "CIGNITITEC.NS",
    "AMARAJAB":      "ARE&M.NS",
    "AMARAJABAT":    "ARE&M.NS",
    "ASSALCOHOL":    "ASALCBR.NS",
    "AZADINDIA":     "AZADIND.BO",
    "MINDTREE":      "LTIM.NS",
    "HDFC":          "HDFCBANK.NS",
    "BLACKBOXLIMI":  "BBOX.NS",
    "ROSSELLTECH":   "ROSSTECH.NS",
    "INDOTECHTR":    "INDOTECH.NS",
    "SHILCHAR":      "SHILCTECH.NS",
    "HBLPOWER":      "HBLENGINE.NS",
    "KPENERGI":      "KPEL.NS",
    "MBENGINEERING": "MBEL.NS",
    "CAPITALNUMB":   "CNINFOTECH.BO",
    "KWALITYPHARM":  "KPL.BO",
    "M&M":           "M%26M.NS",
    "M&MFIN":        "M%26MFIN.NS",
    "MCDOWELL-N":    "UNITDSPR.NS",
    "SSPOWERSWIT":   "S%26SPOWER.NS",
    "TITANBIOTE":    "TITANBIO.BO",
    "TITANBIO":      "TITANBIO.BO",      # CDSL truncated
    "TRUALTBIO":     "TRUALT.NS",         # CDSL truncated → TruAlt Bioenergy
    "ZENTECH":       "ZENTEC.NS",         # CDSL truncated → Zen Technologies
    "SHILCTECH":     "SHILCTECH.NS",      # Shilchar Technologies
    "AMARAJABAT":    "ARE&M.NS",          # legacy symbol
    "HIGHENERGYB":   "HIGHENE.BO",
    "SIKAINTERP":    "SIKA.BO",
    "SHREEREFRI":    "SHREEREF.BO",
    "SKMEPEX":       "SKMEGGPROD.NS",
    "REVATHI":       "RVTH.NS",
    "IGI":           "IGIL.NS",
    "SUYOGTELE":     "SUYOG.NS",
    "QUALPOWER":     "QPOWER.NS",
    "CELLOWORLD":    "CELLO.NS",
    "HINDRECTIF":    "HIRECT.NS",
    "ORIENTBANK":    "PNB.NS",
    "DENABANK":      "BANKBARODA.NS",
    "VIJAYABANK":    "BANKBARODA.NS",
}

INDICES = {"NIFTY","BANKNIFTY","SENSEX","NIFTYMIDCAP100","CNXIT","NIFTYPSE","NIFTYSMALLCAP100","NIFTYBANK"}

def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)

def to_yf(sym):
    mapped = SPECIAL_MAP.get(sym)
    if mapped:
        return mapped if ("." in mapped or mapped.startswith("^")) else mapped + ".NS"
    return sym + ".NS"

def search_yahoo_symbol(name, isin=""):
    """Search Yahoo Finance to resolve company name → NSE/BSE symbol."""
    import urllib.request, urllib.parse
    queries = [name, name.split(" ")[0] + " " + name.split(" ")[1] if len(name.split())>1 else name]
    if isin:
        queries.insert(0, isin)
    for q in queries:
        try:
            url = ("https://query2.finance.yahoo.com/v1/finance/search"
                   f"?q={urllib.parse.quote(q)}&lang=en-IN&region=IN"
                   "&quotesCount=5&newsCount=0&enableFuzzyQuery=true")
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            resp = urllib.request.urlopen(req, timeout=8)
            quotes = json.loads(resp.read()).get("quotes", [])
            for qt in quotes:
                sym_yf = qt.get("symbol","")
                if (sym_yf.endswith(".NS") or sym_yf.endswith(".BO")) and qt.get("quoteType","") in ("EQUITY",""):
                    sym = sym_yf.replace(".NS","").replace(".BO","")
                    print(f"  🔍 Resolved '{name}' → {sym_yf}")
                    return sym
        except Exception as e:
            print(f"  ⚠ Yahoo search '{q}': {e}")
        time.sleep(0.3)
    return None

def load_symbols():
    """Load symbols from symbols.json — resolve names to symbols if needed."""
    try:
        data = json.loads(Path(SYMBOLS_FILE).read_text())
        resolved_any = False
        for entry in data:
            if not entry.get("sym") or len(entry.get("sym","")) < 2:
                # No symbol yet — resolve from name
                name = entry.get("name","")
                isin = entry.get("isin","")
                if name:
                    sym = search_yahoo_symbol(name, isin)
                    if sym:
                        entry["sym"] = sym
                        resolved_any = True
        if resolved_any:
            Path(SYMBOLS_FILE).write_text(json.dumps(data, separators=(",",":")))
            print(f"✓ symbols.json updated with resolved symbols")
        syms = [s["sym"] for s in data if s.get("sym")]
        print(f"📋 {len(syms)} symbols from {SYMBOLS_FILE}")
        return syms, data
    except Exception as e:
        print(f"⚠ Could not read {SYMBOLS_FILE}: {e}")
        return [], []

def safe(v, mult=1, dp=2):
    try:
        f = float(v) * mult
        if f != f or abs(f) == float('inf'): return None
        return round(f, dp)
    except:
        return None

def fetch_ticker(sym):
    yf_sym = to_yf(sym)
    t = yf.Ticker(yf_sym)
    try:
        hist_1m = t.history(period="1mo", interval="1d", auto_adjust=True)
        if hist_1m is None or hist_1m.empty:
            # Try BSE fallback
            try:
                t_bo = yf.Ticker(sym + ".BO")
                hist_bo = t_bo.history(period="1mo", interval="1d", auto_adjust=True)
                if hist_bo is not None and not hist_bo.empty:
                    print(f"  ⚠ {sym}: using BSE")
                    try:    info_bo = t_bo.info or {}
                    except: info_bo = {}
                    return info_bo, hist_bo
            except: pass
            print(f"  ✗ {sym}: not found")
            return {}, None
    except Exception as e:
        print(f"  ✗ {sym}: {e}")
        return {}, None

    try:    hist = t.history(period="5y", interval="1d", auto_adjust=True)
    except: hist = hist_1m
    try:    info = t.info or {}
    except: info = {}

    if not info.get("currentPrice") and not info.get("regularMarketPrice"):
        closes = (hist if hist is not None and not hist.empty else hist_1m)["Close"].dropna()
        if not closes.empty:
            info["currentPrice"]  = float(closes.iloc[-1])
            info["previousClose"] = float(closes.iloc[-2]) if len(closes) >= 2 else float(closes.iloc[-1])
    return info, hist

def build_quote(sym, info, hist):
    ltp  = safe(info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose"))
    prev = safe(info.get("previousClose"))
    if not ltp and hist is not None and not hist.empty:
        ltp  = round(float(hist["Close"].dropna().iloc[-1]), 2)
        prev = round(float(hist["Close"].dropna().iloc[-2]), 2) if len(hist) >= 2 else ltp
    if not ltp: return None
    prev = prev or ltp
    chg  = round(ltp - prev, 2)
    pct  = round(chg / prev * 100, 3) if prev else 0
    roe_raw = info.get("returnOnEquity")
    roe = safe(roe_raw, mult=100) if roe_raw is not None else None
    return {
        "sym":       sym,
        "name":      info.get("longName") or info.get("shortName") or sym,
        "sector":    info.get("sector") or info.get("industryDisp") or "",
        "ltp":       ltp, "change": chg, "changePct": pct,
        "open":      safe(info.get("open") or ltp),
        "high":      safe(info.get("dayHigh") or ltp),
        "low":       safe(info.get("dayLow") or ltp),
        "prev":      prev,
        "vol":       int(info.get("volume") or 0),
        "pe":        safe(info.get("trailingPE")),
        "pb":        safe(info.get("priceToBook")),
        "eps":       safe(info.get("trailingEps")),
        "roe":       roe,
        "w52h":      safe(info.get("fiftyTwoWeekHigh")),
        "w52l":      safe(info.get("fiftyTwoWeekLow")),
        "beta":      safe(info.get("beta")),
        "opm":       safe(info.get("operatingMargins"), mult=100),
        "npm":       safe(info.get("profitMargins"),    mult=100),
    }

def build_chart(sym, hist):
    if hist is None or hist.empty: return
    bars = []
    for date, row in hist.iterrows():
        try:
            bars.append({"d":str(date.date()),
                "o":round(float(row["Open"]),2),"h":round(float(row["High"]),2),
                "l":round(float(row["Low"]),2), "c":round(float(row["Close"]),2),
                "v":int(row.get("Volume",0))})
        except: continue
    if bars:
        (CHARTS_DIR / f"{sym}.json").write_text(
            json.dumps({"sym":sym,"bars":bars}, separators=(",",":")))
        print(f"  ✓ chart: {len(bars)} bars")

def update_symbols_metadata(symbols_data, quotes):
    """Update name/sector in symbols.json from live fetch results."""
    sym_map = {s["sym"]: s for s in symbols_data}
    for sym, q in quotes.items():
        if sym in sym_map:
            if q.get("sector"): sym_map[sym]["sector"] = q["sector"]
            if q.get("name"):   sym_map[sym]["name"]   = q["name"]
    Path(SYMBOLS_FILE).write_text(
        json.dumps(list(sym_map.values()), separators=(",",":")))
    print(f"✓ symbols.json updated — {len(sym_map)} entries")

def main():
    symbols, symbols_data = load_symbols()
    print(f"📊 BharatMarkets Price Fetch")
    print(f"🕐 {now_utc().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"📋 {len(symbols)} symbols\n")

    quotes, errors = {}, []
    index_syms  = [s for s in symbols if s in INDICES]
    equity_syms = [s for s in symbols if s not in INDICES]

    # Batch download equities
    yf_tickers = [to_yf(s) for s in equity_syms]
    print(f"⚡ Batch downloading {len(yf_tickers)} equities…")
    try:
        batch_hist = yf.download(
            tickers=" ".join(yf_tickers), period="5y", interval="1d",
            auto_adjust=True, group_by="ticker", progress=False, threads=True)
        print(f"  ✓ Batch done")
    except Exception as e:
        print(f"  ✗ Batch failed: {e}")
        batch_hist = None

    for sym in equity_syms:
        yf_sym = to_yf(sym)
        hist = None
        if batch_hist is not None and not batch_hist.empty:
            try:
                if len(equity_syms) == 1:
                    hist = batch_hist
                elif yf_sym in batch_hist.columns.get_level_values(0):
                    hist = batch_hist[yf_sym].dropna(how="all")
                elif yf_sym in batch_hist.columns.get_level_values(1):
                    hist = batch_hist.xs(yf_sym, axis=1, level=1).dropna(how="all")
            except: hist = None
        if hist is None or hist.empty:
            _, hist = fetch_ticker(sym)
        info = {}
        try:
            t = yf.Ticker(yf_sym)
            info = t.info or {}
        except: pass
        if hist is not None and not hist.empty:
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

    Path(PRICES_FILE).write_text(
        json.dumps({"updated":now_utc().isoformat(),"count":len(quotes),"quotes":quotes},
                   separators=(",",":")))
    print(f"\n✓ prices.json → {len(quotes)} quotes")
    if errors: print(f"⚠  Failed: {', '.join(errors)}")

    update_symbols_metadata(symbols_data, quotes)

    print(f"\n✅ Done {now_utc().strftime('%H:%M UTC')}\n")

if __name__ == "__main__":
    main()
