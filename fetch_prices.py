#!/usr/bin/env python3
"""
BharatMarkets Pro — Price & Chart Fetcher
Reads:  unified-symbols.json  (source of truth)
        symbol_map.json (shared exchange overrides + delisted list)
Writes: prices.json, charts/*.json
        unified-symbols.json (resolved sym+yf written back when RESOLVE=true)

Daily metrics only (intraday/daily updates):
- ltp, change, changePct, open, high, low, prev, vol
- w52h, w52l, beta

ENV vars (set by workflow):
  RESOLVE=true     → resolve unconfirmed symbols via Yahoo search (import/add only)
  CLEAN_STALE=true → wipe data for symbols not in unified-symbols.json (delete/clear only)
"""

import json, time, datetime, os, requests
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
        delisted  = set(d.get("delisted", []))
        sgb_map   = d.get("sgb_map", {})
        isin_map  = d.get("isin_map", {})
        
        # Remove _comment from maps if present
        sgb_map = {k: v for k, v in sgb_map.items() if k != "_comment"}
        isin_map = {k: v for k, v in isin_map.items() if k != "_comment"}
        
        return {**overrides, **indices}, set(indices.keys()), delisted, sgb_map, isin_map
    except Exception as e:
        print(f"⚠ symbol_map.json not found: {e}")
        return {}, set(), set(), {}, {}

SYMBOL_MAP, INDICES, DELISTED, SGB_MAP, ISIN_MAP = load_symbol_map()

def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)

def to_yf(sym):
    # If already has exchange suffix (.NS, .BO, ^), return as-is
    if "." in sym or sym.startswith("^"):
        return sym
    # Check symbol_map overrides
    mapped = SYMBOL_MAP.get(sym)
    if mapped:
        return mapped if ("." in mapped or mapped.startswith("^")) else mapped + ".NS"
    # Default to NSE
    return sym + ".NS"

# ── Resolve Ticker/ISIN to Actual NSE Trading Code ────────────────────────
def resolve_trading_code(ticker, isin):
    """
    Resolve demat ticker to actual NSE trading code.
    
    Priority:
    1. Check if ticker is in symbol_map overrides (existing mappings)
    2. Check if ISIN is in isin_map (new CDSL name → NSE code mappings)
    3. Check if ISIN is in sgb_map (legacy SGB mappings)
    4. Use ticker as-is (fallback)
    
    Returns: (trading_code, is_mapped)
       trading_code: code to use for Yahoo Finance
       is_mapped: whether we found a mapping (vs using ticker as-is)
    """
    # Check existing symbol_map overrides first
    if ticker in SYMBOL_MAP:
        mapped = SYMBOL_MAP[ticker]
        # Return without .NS suffix as to_yf will add it
        clean_code = mapped.replace(".NS", "").replace(".BO", "")
        return clean_code, True
    
    # Check isin_map for ISIN-based mappings
    isin_upper = (isin or "").upper()
    if isin_upper in ISIN_MAP:
        mapped = ISIN_MAP[isin_upper]
        return mapped, True
    
    # Check sgb_map for legacy SGB mappings
    if isin_upper in SGB_MAP:
        mapped = SGB_MAP[isin_upper]
        return mapped, True
    
    # No mapping found, use ticker as-is
    return ticker, False
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}

# ── Fetch Mutual Fund NAV via NSE API ──────────────────────────────────────
def fetch_mf_nav(isin):
    """
    Fetch Mutual Fund NAV (Net Asset Value) from NSE API using ISIN.
    Returns: dict with 'ltp' (NAV), 'change', 'changePct' or None if failed.
    """
    try:
        # NSE Mutual Fund Data API
        url = f"https://www.nseindia.com/api/mutual-fund-data?isin={isin}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if data and 'data' in data and len(data['data']) > 0:
            mf_data = data['data'][0]
            nav = float(mf_data.get('nav', 0))
            prev_nav = float(mf_data.get('prevNav', nav))  # fallback to current if not available
            change = nav - prev_nav
            change_pct = (change / prev_nav * 100) if prev_nav != 0 else 0
            
            return {
                'ltp': nav,
                'change': change,
                'changePct': change_pct,
            }
    except Exception as e:
        print(f"  ⚠ MF NAV fetch failed for {isin}: {e}")
    
    return None

# ── Resolve SGB ISIN to Trading Code ───────────────────────────────────────
def resolve_sgb_code(isin):
    """
    Lookup SGB ISIN in sgb_map to get NSE trading code.
    Returns: trading code (e.g., 'SGB2032IV') or None if not found.
    """
    return SGB_MAP.get(isin, None)

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

    # Filter out delisted symbols
    syms = [s["sym"] for s in data if s.get("sym") and s.get("resolved") and s["sym"] not in DELISTED]
    filtered = len([s["sym"] for s in data if s.get("sym") and s["sym"] in DELISTED])
    if filtered:
        print(f"🗑 Skipped {filtered} delisted symbols")
    print(f"📋 {len(syms)} active symbols from {SYMBOLS_FILE}")
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
    
    return {
        "ticker": sym,
        "name": info.get("longName") or info.get("shortName") or sym,
        "sector": info.get("sector") or info.get("industryDisp") or "",
        "ltp": ltp, "change": chg, "changePct": pct,
        "open": safe(info.get("open") or ltp), "high": safe(info.get("dayHigh") or ltp),
        "low": safe(info.get("dayLow") or ltp), "prev": prev,
        "vol": int(info.get("volume") or 0),
        "w52h": safe(info.get("fiftyTwoWeekHigh")), "w52l": safe(info.get("fiftyTwoWeekLow")),
        "beta": safe(info.get("beta")),
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

    # ── Build symbol-to-entry map for ISIN lookup ─────────────────────────
    sym_to_entry = {s["sym"]: s for s in symbols_data if s.get("sym")}
    
    # ── Categorize symbols by ISIN prefix ──────────────────────────────────
    equity_syms = []    # INE ISINs
    etf_syms = []       # INF ISINs
    sgb_syms = []       # SGB ISINs
    mf_syms = []        # Other ISINs (Mutual Funds)
    unknown_syms = []   # Missing ISIN
    
    for sym in symbols:
        entry = sym_to_entry.get(sym, {})
        isin = (entry.get("isin") or "").upper()
        
        if isin.startswith("INE"):
            equity_syms.append(sym)
        elif isin.startswith("INF"):
            etf_syms.append(sym)
        elif isin.startswith("SGB"):
            sgb_syms.append(sym)
        elif isin.startswith("IN00"):
            # IN00* = Government securities (bonds, treasury securities, etc.)
            # Treat as SGBs for Yahoo fetching, skip MF API
            sgb_syms.append(sym)
        elif isin:
            mf_syms.append(sym)
        else:
            unknown_syms.append(sym)
    
    print(f"  Equities (INE):        {len(equity_syms)}")
    print(f"  ETFs (INF):            {len(etf_syms)}")
    print(f"  Gov Securities (SGB/IN00): {len(sgb_syms)}")
    print(f"  Mutual Funds (other):  {len(mf_syms)}")
    if unknown_syms:
        print(f"  Unknown ISIN:          {len(unknown_syms)} — {', '.join(unknown_syms[:5])}")
    print()

    quotes, errors = {}, []
    index_syms  = [s for s in symbols if s in INDICES]
    all_equity_syms = [s for s in equity_syms + etf_syms if s not in INDICES]

    # ──────────────────────────────────────────────────────────────────────
    # BATCH DOWNLOAD: Equities + ETFs (both use Yahoo Finance)
    # ──────────────────────────────────────────────────────────────────────
    if all_equity_syms:
        # Resolve trading codes and build Yahoo tickers
        yf_tickers = []
        resolved_codes = {}
        for sym in all_equity_syms:
            entry = sym_to_entry.get(sym, {})
            isin = entry.get("isin", "")
            trading_code, is_mapped = resolve_trading_code(sym, isin)
            resolved_codes[sym] = (trading_code, is_mapped)
            yf_tickers.append(to_yf(trading_code))
        
        print(f"⚡ Batch downloading {len(yf_tickers)} equities/ETFs…")
        if any(is_mapped for _, is_mapped in resolved_codes.values()):
            mapped_count = sum(1 for _, is_mapped in resolved_codes.values() if is_mapped)
            print(f"   ({mapped_count} tickers resolved via symbol_map/isin_map)")
        try:
            batch_hist = yf.download(
                tickers=" ".join(yf_tickers), period="5y", interval="1d",
                auto_adjust=True, group_by="ticker", progress=False, threads=True)
            print(f"  ✓ Batch done")
        except Exception as e:
            print(f"  ✗ Batch failed: {e}")
            batch_hist = None
    else:
        batch_hist = None
        resolved_codes = {}

    # ──────────────────────────────────────────────────────────────────────
    # FETCH: Equities + ETFs (from batch or individual)
    # ──────────────────────────────────────────────────────────────────────
    print(f"\n📈 Fetching equities & ETFs…")
    for sym in all_equity_syms:
        # Get resolved trading code
        if sym in resolved_codes:
            trading_code, is_mapped = resolved_codes[sym]
        else:
            entry = sym_to_entry.get(sym, {})
            isin = entry.get("isin", "")
            trading_code, is_mapped = resolve_trading_code(sym, isin)
        
        yf_sym = to_yf(trading_code)
        hist = None
        if batch_hist is not None and not batch_hist.empty:
            try:
                if len(all_equity_syms) == 1:
                    hist = batch_hist
                elif yf_sym in batch_hist.columns.get_level_values(0):
                    hist = batch_hist[yf_sym].dropna(how="all")
                elif yf_sym in batch_hist.columns.get_level_values(1):
                    hist = batch_hist.xs(yf_sym, axis=1, level=1).dropna(how="all")
            except: hist = None
        if hist is None or hist.empty:
            _, hist = fetch_ticker(trading_code)
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
            mapped_str = " (mapped)" if is_mapped else ""
            print(f"  ✓ {sym}: ₹{q['ltp']} ({q['changePct']:+.2f}%){mapped_str}")
        else:
            errors.append(sym)
        if hist is not None and not hist.empty:
            build_chart(sym, hist)

    # ──────────────────────────────────────────────────────────────────────
    # FETCH: Mutual Funds (try Yahoo first, then NSE API)
    # ──────────────────────────────────────────────────────────────────────
    if mf_syms:
        print(f"\n💰 Fetching mutual funds…")
        for sym in mf_syms:
            entry = sym_to_entry.get(sym, {})
            isin = entry.get("isin", "").upper()
            
            # Try Yahoo first (in case it's mapped or has a ticker)
            trading_code, is_mapped = resolve_trading_code(sym, isin)
            yf_sym = to_yf(trading_code)
            q = None
            
            try:
                info = yf.Ticker(yf_sym).info or {}
                hist = yf.Ticker(yf_sym).history(period="1d")
                if hist is not None and not hist.empty:
                    q = build_quote(sym, info, hist)
                    if q:
                        quotes[sym] = q
                        mapped_str = " (mapped via Yahoo)" if is_mapped else " (Yahoo)"
                        print(f"  ✓ {sym}: ₹{q['ltp']} ({q['changePct']:+.2f}%){mapped_str}")
            except:
                pass
            
            # If Yahoo failed, try NSE API
            if not q:
                nav_data = fetch_mf_nav(isin)
                if nav_data:
                    q = {
                        "ticker": sym,
                        "name": entry.get("name", sym),
                        "sector": "",
                        "ltp": nav_data.get('ltp'),
                        "change": nav_data.get('change'),
                        "changePct": nav_data.get('changePct'),
                        "open": None, "high": None, "low": None, "prev": None,
                        "vol": 0, "w52h": None, "w52l": None, "beta": None,
                    }
                    quotes[sym] = q
                    print(f"  ✓ {sym}: ₹{q['ltp']} ({q['changePct']:+.2f}%) (NSE API)")
                else:
                    print(f"  ✗ {sym}: Both Yahoo & NSE API failed → null")
                    errors.append(sym)

    # ──────────────────────────────────────────────────────────────────────
    # FETCH: SGBs (resolve ISIN to trading code, then fetch via Yahoo)
    # ──────────────────────────────────────────────────────────────────────
    if sgb_syms:
        print(f"\n🏆 Fetching SGBs…")
        for sym in sgb_syms:
            entry = sym_to_entry.get(sym, {})
            isin = entry.get("isin", "").upper()
            trading_code, is_mapped = resolve_trading_code(sym, isin)
            
            # If not mapped, try as-is or mark as unmapped
            if not is_mapped:
                print(f"  ⚠ {sym}: ISIN {isin} not in symbol_map → trying as ticker")
            
            yf_sym = to_yf(trading_code)
            try:
                info = yf.Ticker(yf_sym).info or {}
                hist = yf.Ticker(yf_sym).history(period="5y", interval="1d")
                q = build_quote(sym, info, hist)
                if q:
                    quotes[sym] = q
                    mapped_str = " (mapped)" if is_mapped else ""
                    print(f"  ✓ {sym} ({trading_code}): ₹{q['ltp']} ({q['changePct']:+.2f}%){mapped_str}")
                else:
                    print(f"  ✗ {sym}: quote build failed → null")
                    errors.append(sym)
            except Exception as e:
                print(f"  ✗ {sym}: {str(e)[:60]} → null")
                errors.append(sym)

    # ──────────────────────────────────────────────────────────────────────
    # FETCH: Indices
    # ──────────────────────────────────────────────────────────────────────
    print(f"\n📊 Fetching {len(index_syms)} indices…")
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
