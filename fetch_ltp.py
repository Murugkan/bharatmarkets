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

    # Identify MUTUAL FUND entries — these have no Yahoo/NSE equity quote
    # (NAV comes from fetch_amfi_nav.py instead). Detect via explicit
    # instrument_type or sector == 'MUTUAL FUND' (real wizard-imported MF
    # entries always set sector="Mutual Fund", even without instrument_type).
    # NOTE: do NOT use an ISIN "INF" prefix check — ETFs like JUNIORBEES
    # (INF200KA1FS3, sector="ETF") also have INF-prefixed ISINs but ARE
    # exchange-traded with real Yahoo LTP data; an INF-prefix check would
    # incorrectly exclude them. Sovereign Gold Bonds (SGB) are also
    # exchange-traded and fetchable via Yahoo, so they're not skipped here.
    def is_mf_like(entry):
        itype = (entry.get('instrument_type') or '').upper()
        sector = (entry.get('sector') or '').upper()
        return itype == 'MUTUAL FUND' or sector == 'MUTUAL FUND'

    mf_skipped = len([s for s in data if s.get("sym") and is_mf_like(s)])
    if mf_skipped:
        print(f"🪙 Skipped {mf_skipped} mutual fund symbols (NAV handled via fetch_nav_ltp.py)")

    # Filter out delisted symbols and MF/SGB entries
    syms = [s["sym"] for s in data if s.get("sym") and s.get("resolved") and s["sym"] not in DELISTED and not is_mf_like(s)]
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

            # 52W change — weekly history
            hist_w = t.history(period="1y", interval="1wk", auto_adjust=True)
            if hist_w is None or hist_w.empty:
                raise ValueError("empty weekly history")
            closes_w = hist_w["Close"].dropna()
            start_px  = float(closes_w.iloc[0])
            end_px    = float(closes_w.iloc[-1])
            chg_52w   = round((end_px - start_px) / start_px * 100, 2)
            as_of     = closes_w.index[-1].strftime("%Y-%m-%d")

            # 1D change — daily history (last 5 days for safety)
            hist_d = t.history(period="5d", interval="1d", auto_adjust=True)
            chg_1d = None
            if hist_d is not None and len(hist_d) >= 2:
                closes_d = hist_d["Close"].dropna()
                prev_px  = float(closes_d.iloc[-2])
                last_px  = float(closes_d.iloc[-1])
                if prev_px > 0:
                    chg_1d = round((last_px - prev_px) / prev_px * 100, 2)

            entry = {
                "symbol":         symbol,
                "name":           name,
                "price":          round(end_px, 2),
                "change_52w_pct": chg_52w,
                "change_1d_pct":  chg_1d,
                "as_of":          as_of,
            }
            seen[symbol] = entry
            results[sector] = entry
            print(f"  ✓ {sector:<30} {symbol}  52W:{chg_52w:+.1f}%  1D:{chg_1d:+.2f}%" if chg_1d is not None else f"  ✓ {sector:<30} {symbol}  52W:{chg_52w:+.1f}%")
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
    # FETCH: Mutual Funds + SGBs + QSIF — from nav_ltp.json
    # (NSE/BSE APIs block GitHub Actions IPs; nav_ltp.json is pre-fetched
    #  by fetch_nav_ltp.py which runs before this step)
    # ──────────────────────────────────────────────────────────────────────
    nav_ltp_syms = mf_syms + sgb_syms
    if nav_ltp_syms:
        print(f"💰 Injecting {len(nav_ltp_syms)} MF/SGB/QSIF from nav_ltp.json…")
        nav_ltp_data = {}
        nav_ltp_path = Path("data/nav_ltp.json")
        if nav_ltp_path.exists():
            try:
                nav_ltp_data = json.loads(nav_ltp_path.read_text())
            except Exception as e:
                logger.warning(f"nav_ltp.json load failed: {e}")

        # Build ISIN → nav_ltp key lookup (nav_ltp is keyed by ISIN or ticker)
        isin_to_nav = {}
        for key, entry in nav_ltp_data.items():
            if key == '_metadata':
                continue
            isin_to_nav[key.upper()] = entry

        for sym in nav_ltp_syms:
            entry = sym_to_entry.get(sym, {})
            isin = entry.get("isin", "").upper()
            nav_entry = isin_to_nav.get(isin) or isin_to_nav.get(sym.upper())
            if nav_entry and nav_entry.get('ltp') is not None:
                q = {
                    "ticker": sym,
                    "name": nav_entry.get('scheme_name') or entry.get("name", sym),
                    "sector": entry.get("sector", ""),
                    "ltp": nav_entry.get('ltp'),
                    "change": nav_entry.get('change'), "changePct": nav_entry.get('changePct'),
                    "open": None, "high": None, "low": None, "prev": None,
                    "vol": 0, "w52h": None, "w52l": None, "beta": None,
                    "nav_date": nav_entry.get('date'),
                    "nav_source": nav_entry.get('source'),
                }
                quotes[sym] = q
                print(f"  ✓ {sym}: LTP {nav_entry['ltp']} ({nav_entry.get('source')})")
            else:
                logger.warning(f"nav_ltp.json: no entry for {sym} (ISIN: {isin})")
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
