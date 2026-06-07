#!/usr/bin/env python3
"""
BharatMarkets Pro — LTP Fetcher
Reads:  unified-symbols.json  (source of truth)
        symbol_map.json (shared exchange overrides + delisted list)
Writes: ltp.json

Daily metrics (last 6 days: current market date + previous 5):
- ltp, change, changePct, open, high, low, prev, vol
- w52h, w52l, beta
"""

import json, time, datetime, os, requests, logging, sys
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("pip install yfinance")

# ── Setup logging ──────────────────────────────────────────────────────
log_dir = Path("data/logs")
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "fetch_ltp.log"

# Purge log file on startup
log_file.write_text("")

# Only log warnings and errors, not info messages
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
    ]
)
logger = logging.getLogger(__name__)

SYMBOLS_FILE   = "data/unified-symbols.json"
SYMBOL_MAP_FILE= "data/symbol_map.json"
LTP_FILE       = "data/ltp.json"
SECTOR_IDX_FILE= "data/sector_indices.json"

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
        # Return mapped value as-is (already has correct exchange suffix like .NS or .BO)
        return mapped, True
    
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

# ── Fetch Stock Price from NSE API (Fallback for Yahoo misses) ───────────────
def fetch_from_nse_api(symbol):
    """
    Fetch stock/SGB price directly from NSE API.
    Used as fallback when Yahoo Finance doesn't have data.
    
    Returns: dict with all price fields (mapped to yfinance structure) or None if failed.
    """
    try:
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if data and 'priceInfo' in data:
            price_info = data['priceInfo']
            info_header = data.get('info', {})
            
            # Map NSE fields to yfinance field names for build_quote()
            return {
                'currentPrice': float(price_info.get('lastPrice', 0)),
                'previousClose': float(price_info.get('previousClose', 0)),
                'open': float(price_info.get('open', None)) if price_info.get('open') else None,
                'dayHigh': float(price_info.get('intraDayHighLow', {}).get('max', None)) if price_info.get('intraDayHighLow', {}).get('max') else None,
                'dayLow': float(price_info.get('intraDayHighLow', {}).get('min', None)) if price_info.get('intraDayHighLow', {}).get('min') else None,
                'fiftyTwoWeekHigh': float(price_info.get('weekHighLow', {}).get('max', None)) if price_info.get('weekHighLow', {}).get('max') else None,
                'fiftyTwoWeekLow': float(price_info.get('weekHighLow', {}).get('min', None)) if price_info.get('weekHighLow', {}).get('min') else None,
                'volume': None,  # NSE equity API doesn't provide volume
                'beta': None,    # Not applicable for bonds/SGBs
                'longName': info_header.get('companyName', symbol),
                'sector': 'Government Securities' if symbol.startswith('SGB') else info_header.get('industry', 'NA'),
            }
    except Exception as e:
        pass
    
    return None


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

    # All symbols in unified-symbols.json are already confirmed
    # No need to resolve or update

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
        hist_1m = t.history(period="6d", interval="1d", auto_adjust=True)
        if hist_1m is None or hist_1m.empty:
            t_bo = yf.Ticker(sym + ".BO")
            hist_bo = t_bo.history(period="6d", interval="1d", auto_adjust=True)
            if hist_bo is not None and not hist_bo.empty:
                print(f"  ⚠ {sym}: falling back to BSE")
                try:    info_bo = t_bo.info or {}
                except: info_bo = {}
                return info_bo, hist_bo
            
            # Try NSE API as final fallback (for CNINFOTECH, HIGHENE, SGBFEB32IV, etc.)
            nse_data = fetch_from_nse_api(sym)
            if nse_data:
                print(f"  ⚠ {sym}: using NSE API")
                return nse_data, None
            
            print(f"  ✗ {sym}: not found")
            return {}, None
    except Exception as e:
        print(f"  ✗ {sym}: {e}")
        return {}, None
    try:    hist = t.history(period="6d", interval="1d", auto_adjust=True)
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



# ── Sector Index Symbols (Yahoo Finance) ──────────────────────────────────────
SECTOR_INDEX_MAP = {
    "Information Technology": ("^CNXIT",     "Nifty IT"),
    "Financials":             ("^NSEBANK",   "Nifty Bank"),
    "Healthcare":             ("^CNXPHARMA", "Nifty Pharma"),
    "Consumer Staples":       ("^CNXFMCG",  "Nifty FMCG"),
    "Consumer Discretionary": ("^CNXAUTO",  "Nifty Auto"),
    "Materials":              ("^CNXMETAL",  "Nifty Metal"),
    "Energy":                 ("^CNXENERGY", "Nifty Energy"),
    "Industrials":            ("^CNXINFRA",  "Nifty Infra"),
    "Utilities":              ("^CNXPSE",    "Nifty PSE"),
    "Defence":                ("MODEFENCE.NS", "Nifty India Defence"),
    "Telecom":                ("^CNXPSE",    "Nifty PSE"),
    "ETF":                    ("^NSEI",      "Nifty 50"),
}

def fetch_sector_indices():
    print(f"\n📊 Fetching sector indices…")
    results = {}
    seen = {}  # cache — avoid re-fetching same symbol

    for sector, (symbol, name) in SECTOR_INDEX_MAP.items():
        if symbol in seen:
            results[sector] = {**seen[symbol], "symbol": symbol, "name": name}
            print(f"  ↩ {sector:<30} {symbol} (cached)")
            continue
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="1y", interval="1wk", auto_adjust=True)
            if hist is None or hist.empty:
                raise ValueError("empty history")
            closes = hist["Close"].dropna()
            start_px = float(closes.iloc[0])
            end_px   = float(closes.iloc[-1])
            chg_pct  = round((end_px - start_px) / start_px * 100, 2)
            as_of    = closes.index[-1].strftime("%Y-%m-%d")
            entry = {
                "symbol":         symbol,
                "name":           name,
                "price":          round(end_px, 2),
                "change_52w_pct": chg_pct,
                "as_of":          as_of,
            }
            seen[symbol] = entry
            results[sector] = entry
            print(f"  ✓ {sector:<30} {symbol}  {chg_pct:+.1f}%")
        except Exception as e:
            print(f"  ✗ {sector:<30} {symbol}  {e}")
            results[sector] = {"symbol": symbol, "name": name}
        time.sleep(0.3)

    Path(SECTOR_IDX_FILE).write_text(
        json.dumps({"updated": now_utc().isoformat(), "sectors": results}, indent=2))
    ok = sum(1 for v in results.values() if "change_52w_pct" in v)
    print(f"  → {ok}/{len(results)} fetched → {SECTOR_IDX_FILE}")


def main():
    # Purge old data
    Path(LTP_FILE).write_text("")
    
    symbols, symbols_data = load_symbols()
    start_time = now_utc()
    
    print(f"📊 BharatMarkets LTP Fetch | {start_time.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"📋 {len(symbols)} symbols\n")

    # ── Build symbol-to-entry map for ISIN lookup ─────────────────────────
    sym_to_entry = {s["sym"]: s for s in symbols_data if s.get("sym")}
    
    # ── Categorize symbols by ISIN prefix ──────────────────────────────────
    equity_syms = []    # INE ISINs
    etf_syms = []       # INF ISINs
    sgb_syms = []       # SGB ISINs
    mf_syms = []        # Other ISINs (Mutual Funds)
    unknown_syms = []   # Missing ISIN
    errors = []         # Track failed fetches
    
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
            # Fetch last 6 days (market date + previous 5 days)
            batch_hist = yf.download(
                tickers=" ".join(yf_tickers), period="6d", interval="1d",
                auto_adjust=True, group_by="ticker", progress=False, threads=True)
        except Exception as e:
            logger.warning(f"Batch download failed: {e}")
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
        else:
            errors.append(sym)
            logger.warning(f"Failed to fetch {sym}")

    # ──────────────────────────────────────────────────────────────────────
    # FETCH: Mutual Funds (try Yahoo first, then NSE API)
    # ──────────────────────────────────────────────────────────────────────
    if mf_syms:
        print(f"💰 Fetching {len(mf_syms)} mutual funds…")
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
                else:
                    logger.warning(f"Failed to fetch {sym} (Yahoo & NSE API)")
                    errors.append(sym)

    # ──────────────────────────────────────────────────────────────────────
    # FETCH: SGBs (resolve ISIN to trading code, then fetch via Yahoo)
    # ──────────────────────────────────────────────────────────────────────
    if sgb_syms:
        print(f"🏆 Fetching {len(sgb_syms)} govt securities…")
        for sym in sgb_syms:
            entry = sym_to_entry.get(sym, {})
            isin = entry.get("isin", "").upper()
            trading_code, is_mapped = resolve_trading_code(sym, isin)
            
            # Use fetch_ticker() which includes NSE API fallback
            info, hist = fetch_ticker(trading_code)
            q = build_quote(sym, info, hist)
            if q:
                quotes[sym] = q
            else:
                logger.warning(f"Failed to fetch {sym}")
                errors.append(sym)

    # ──────────────────────────────────────────────────────────────────────
    # FETCH: Indices
    # ──────────────────────────────────────────────────────────────────────
    print(f"📊 Fetching {len(index_syms)} indices…")
    for sym in index_syms:
        info, hist = fetch_ticker(sym)
        q = build_quote(sym, info, hist)
        if q:
            quotes[sym] = q
        time.sleep(0.3)

    Path(LTP_FILE).write_text(
        json.dumps({
            "updated": now_utc().isoformat(),
            "lastLoadedAt": now_utc().isoformat(),
            "source": "yahoo_finance",
            "count": len(quotes),
            "quotes": quotes
        }, separators=(",",":")))
    
    fetch_sector_indices()

    elapsed = (now_utc() - start_time).total_seconds()
    print(f"\n{'='*50}")
    print(f"✅ SUMMARY")
    print(f"{'='*50}")
    print(f"Total quotes:  {len(quotes)}")
    print(f"Failed:        {len(errors)}")
    if errors:
        print(f"Failed syms:   {', '.join(errors)}")
        logger.warning(f"Failed symbols: {', '.join(errors)}")
    print(f"Elapsed:       {elapsed:.1f}s")
    print(f"File:          {LTP_FILE}")
    print(f"{'='*50}\n")

if __name__ == "__main__":
    main()
