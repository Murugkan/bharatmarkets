#!/usr/bin/env python3
"""
BharatMarkets Pro — Price & Chart Fetcher
Reads:  unified-symbols.json  (source of truth)
        unified-symbols.json (shared exchange overrides)
Writes: prices.json, charts/*.json
        unified-symbols.json (resolved sym+yf written back when RESOLVE=true)

ENV vars (set by workflow):
  RESOLVE=true     → resolve unconfirmed symbols via Yahoo search (import/add only)
  CLEAN_STALE=true → wipe data for symbols not in unified-symbols.json (delete/clear only)
"""

import json, time, datetime, os
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("pip install yfinance")

SYMBOLS_FILE   = "unified-symbols.json"
SYMBOL_MAP_FILE= "symbol_map.json"
PRICES_FILE    = "prices.json"
CHARTS_DIR     = Path("charts")
CHARTS_DIR.mkdir(exist_ok=True)

DO_RESOLVE     = os.environ.get("RESOLVE",      "").lower() in ("true","1")
DO_CLEAN       = os.environ.get("CLEAN_STALE",  "").lower() in ("true","1")

# ── Load shared symbol map ─────────────────────────────────────────────
def load_symbol_map():
    try:
        d = json.loads(Path(SYMBOL_MAP_FILE).read_text())
        overrides = d.get("overrides", {})
        indices   = d.get("indices",   {})
        return {**overrides, **indices}, set(indices.keys())
    except Exception as e:
        print(f"⚠ symbol_map.json not found: {e}")
        return {}, set()

SYMBOL_MAP, INDICES = load_symbol_map()

def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)

def to_yf(sym):
    mapped = SYMBOL_MAP.get(sym)
    if mapped:
        return mapped if ("." in mapped or mapped.startswith("^")) else mapped + ".NS"
    return sym + ".NS"

# ── Yahoo search — only called when RESOLVE=true ───────────────────────
def search_yahoo_symbol(name, isin=""):
    import urllib.request, urllib.parse
    queries = [name]
    if isin: queries.insert(0, isin)
    for q in queries:
        try:
            url = ("https://query2.finance.yahoo.com/v1/finance/search"
                   f"?q={urllib.parse.quote(q)}&lang=en-IN&region=IN"
                   "&quotesCount=5&newsCount=0&enableFuzzyQuery=true")
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=8)
            for qt in json.loads(resp.read()).get("quotes", []):
                sym_yf = qt.get("symbol","")
                if (sym_yf.endswith(".NS") or sym_yf.endswith(".BO")) and \
                   qt.get("quoteType","") in ("EQUITY",""):
                    sym = sym_yf.replace(".NS","").replace(".BO","")
                    if sym_yf.endswith(".BO"):
                        SYMBOL_MAP[sym] = sym_yf  # register BSE-only at runtime
                    print(f"  🔍 '{name}' → {sym_yf}")
                    return sym
        except Exception as e:
            print(f"  ⚠ Yahoo search '{q}': {e}")
        time.sleep(0.3)
    return None

# ── Load symbols ───────────────────────────────────────────────────────
def load_symbols():
    try:
        data = json.loads(Path(SYMBOLS_FILE).read_text())
    except Exception as e:
        print(f"⚠ Cannot read {SYMBOLS_FILE}: {e}")
        return [], []

    # Handle unified-symbols.json format (has "symbols" array with "ticker" field)
    if isinstance(data, dict) and "symbols" in data:
        data = data["symbols"]
    
    # Convert "ticker" field to "sym" for backward compatibility
    for entry in data:
        if "ticker" in entry and "sym" not in entry:
            entry["sym"] = entry["ticker"]
        # Mark as resolved since unified-symbols.json only has confirmed tickers
        entry["resolved"] = True

    resolved_any = False

    for entry in data:
        if entry.get("resolved") is True:
            continue  # already confirmed — skip
        if not DO_RESOLVE:
            # Scheduled run — skip unresolved, use existing sym as-is
            if not entry.get("sym"):
                print(f"  ⚠ Skipping unresolved: {entry.get('name','?')} (run 'all' to resolve)")
            continue
        # RESOLVE=true — confirm via Yahoo
        name = entry.get("name","")
        isin = entry.get("isin","")
        sym  = search_yahoo_symbol(name, isin) if name else ""
        if sym:
            entry["sym"]      = sym
            entry["resolved"] = True
            resolved_any = True
        else:
            entry["resolved"] = True  # mark done to avoid retry every run
            print(f"  ⚠ Unresolvable: '{name}' — keeping sym={entry.get('sym','?')}")

    if resolved_any:
        Path(SYMBOLS_FILE).write_text(json.dumps(data, separators=(",",":")))
        print(f"✓ {SYMBOLS_FILE} updated with confirmed symbols")

    syms = [s["sym"] for s in data if s.get("sym") and s.get("resolved")]
    print(f"📋 {len(syms)} resolved symbols from {SYMBOLS_FILE}")
    return syms, data

# ── Price fetching ────────────────────────────────────────────────────
def safe(v, mult=1, dp=2):
    try:
        f = float(v) * mult
        if f != f or abs(f) == float('inf'): return None
        return round(f, dp)
    except: return None

def fetch_ticker(sym):
    yf_sym = to_yf(sym)
    t = yf.Ticker(yf_sym)
    try:
        hist_1m = t.history(period="1mo", interval="1d", auto_adjust=True)
        if hist_1m is None or hist_1m.empty:
            t_bo = yf.Ticker(sym + ".BO")
            hist_bo = t_bo.history(period="1mo", interval="1d", auto_adjust=True)
            if hist_bo is not None and not hist_bo.empty:
                print(f"  ⚠ {sym}: falling back to BSE")
                try:    info_bo = t_bo.info or {}
                except: info_bo = {}
                return info_bo, hist_bo
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
            info["previousClose"] = float(closes.iloc[-2]) if len(closes)>=2 else float(closes.iloc[-1])
    return info, hist

def build_quote(sym, info, hist):
    ltp  = safe(info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose"))
    prev = safe(info.get("previousClose"))
    if not ltp and hist is not None and not hist.empty:
        ltp  = round(float(hist["Close"].dropna().iloc[-1]), 2)
        prev = round(float(hist["Close"].dropna().iloc[-2]), 2) if len(hist)>=2 else ltp
    if not ltp: return None
    prev = prev or ltp
    chg  = round(ltp - prev, 2)
    pct  = round(chg / prev * 100, 3) if prev else 0
    roe_raw = info.get("returnOnEquity")
    return {
        "ticker": sym,
        "name": info.get("longName") or info.get("shortName") or sym,
        "sector": info.get("sector") or info.get("industryDisp") or "",
        "ltp": ltp, "change": chg, "changePct": pct,
        "open": safe(info.get("open") or ltp), "high": safe(info.get("dayHigh") or ltp),
        "low": safe(info.get("dayLow") or ltp), "prev": prev,
        "vol": int(info.get("volume") or 0),
        "pe": safe(info.get("trailingPE")), "pb": safe(info.get("priceToBook")),
        "eps": safe(info.get("trailingEps")),
        "roe": safe(roe_raw, mult=100) if roe_raw is not None else None,
        "w52h": safe(info.get("fiftyTwoWeekHigh")), "w52l": safe(info.get("fiftyTwoWeekLow")),
        "beta": safe(info.get("beta")),
        "opm": safe(info.get("operatingMargins"), mult=100),
        "npm": safe(info.get("profitMargins"), mult=100),
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

def main():
    symbols, symbols_data = load_symbols()
    print(f"📊 BharatMarkets Price Fetch | {now_utc().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"   RESOLVE={DO_RESOLVE} CLEAN_STALE={DO_CLEAN}")
    print(f"📋 {len(symbols)} symbols\n")

    quotes, errors = {}, []
    index_syms  = [s for s in symbols if s in INDICES]
    equity_syms = [s for s in symbols if s not in INDICES]

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
            info = yf.Ticker(yf_sym).info or {}
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

    # CLEAN: wipe everything not in current symbols.json
    if DO_CLEAN:
        active = set(symbols)
        removed = [s for s in list(quotes) if s not in active]
        for s in removed:
            del quotes[s]
            cf = CHARTS_DIR / f"{s}.json"
            if cf.exists(): cf.unlink()
        if removed: print(f"  🗑 cleaned prices+charts: {', '.join(removed)}")
        else:       print(f"  ✓ prices already clean")

    Path(PRICES_FILE).write_text(
        json.dumps({
            "updated": now_utc().isoformat(),
            "lastLoadedAt": now_utc().isoformat(),
            "source": "yahoo_finance",
            "count": len(quotes),
            "quotes": quotes
        }, separators=(",",":")))
    print(f"\n✓ prices.json → {len(quotes)} quotes")
    if errors: print(f"⚠  Failed: {', '.join(errors)}")
    print(f"\n✅ Done {now_utc().strftime('%H:%M UTC')}\n")

if __name__ == "__main__":
    main()
