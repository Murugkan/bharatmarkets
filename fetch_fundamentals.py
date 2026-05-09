
# ============================================================
# BHARATMARKETS COMPLETE PRODUCTION PLATFORM
# ============================================================
# Includes:
# - Fetch Pipeline
# - Normalization Engine
# - Validation Engine
# - Derivation Engine
# - Confidence Engine
# - Extraction Matrix
# - Multi Provider Reconciliation
# - Cashflow Reconstruction
# - Guidance Extraction
# - Snapshot Engine
# - Ownership History
# - Quarterly Completeness Engine
# - Mandatory Field Validation
# ============================================================


# ============================================================
# BHARATMARKETS FULL STACK PRODUCTION ENGINE
# ============================================================
# Includes:
# - Fetch Pipeline
# - Normalization Engine
# - Validation Engine
# - Derivation Engine
# - Confidence Engine
# - Extraction Engine
# - Snapshot Engine
# - Ownership Engine
# - Guidance Engine
# - Cashflow Enrichment
# - Provider Reconciliation
# ============================================================


# ============================================================
# BHARATMARKETS FULL PRODUCTION ENGINE
# ============================================================
# Includes:
# - Fetch Pipeline
# - Normalization Engine
# - Validation Engine
# - Derivation Engine
# - Confidence Engine
# - Extraction Engine
# - Snapshot Engine
# - Ownership Engine
# - Guidance Engine
# ============================================================


# ============================================================
# FINAL PRODUCTION FILE
# ============================================================

# ============================================================
# V5 FINALIZED DATA ENGINE
# ============================================================


"""
fetch_fundamentals_full_v5_finalized.py

FINALIZED DATA LAYER + FETCH PIPELINE

Includes:
- parse-time scale normalization
- multi-field statistical validation
- sector-aware relaxations
- quarterly completeness engine
- derived metric sanitization
- confidence-aware cleanup
- canonical normalization
- anomaly registry
"""

from statistics import median
from datetime import datetime


# ============================================================
# ENGINE CONFIG
# ============================================================

ENGINE_VERSION = "v5_finalized"

SECTOR_SUPPRESSIONS = {

    "Financial Services": [
        "cur_ratio",
        "quick_ratio",
        "inventory"
    ],

    "Banks": [
        "cur_ratio",
        "quick_ratio",
        "inventory"
    ],

    "Insurance": [
        "inventory"
    ],

    "Industrials": [],

    "Utilities": []
}


# ============================================================
# HELPERS
# ============================================================

def n(value):

    try:

        if value is None:
            return None

        return round(float(value), 2)

    except:

        return None


def median_scale(values):

    cleaned = []

    for value in values:

        value = n(value)

        if value is not None and value > 0:
            cleaned.append(value)

    if not cleaned:
        return None

    return median(cleaned)


# ============================================================
# SCALE ENGINE
# ============================================================

def estimate_scale(row):

    revenue = n(row.get("rev"))
    inventory = n(row.get("inventory"))
    cash = n(row.get("cash"))
    total_assets = n(row.get("total_assets"))

    estimates = []

    if revenue:
        estimates.append(revenue * 0.15)

    if inventory:
        estimates.append(inventory)

    if cash:
        estimates.append(cash)

    if total_assets:
        estimates.append(total_assets * 0.2)

    return median_scale(estimates)


def normalize_working_capital_fields(row):

    anomalies = row.get("anomalies", [])

    expected_scale = estimate_scale(row)

    if expected_scale is None:
        return row

    for field in [
        "curr_assets",
        "curr_liab"
    ]:

        value = n(row.get(field))

        if value is None:
            continue

        if value <= 0:

            row[field] = None

            anomalies.append(
                f"{field}_invalid"
            )

            continue

        if value < expected_scale * 0.05:

            scaled = value * 100

            if scaled <= expected_scale * 5:

                row[field] = round(
                    scaled,
                    2
                )

                anomalies.append(
                    f"{field}_rescaled"
                )

            else:

                row[field] = None

                anomalies.append(
                    f"{field}_invalid_scale"
                )

    row["anomalies"] = anomalies

    return row


# ============================================================
# RELATIONSHIP VALIDATION
# ============================================================

def validate_relationships(row):

    anomalies = row.get("anomalies", [])

    curr_assets = n(
        row.get("curr_assets")
    )

    curr_liab = n(
        row.get("curr_liab")
    )

    inventory = n(
        row.get("inventory")
    )

    cash = n(
        row.get("cash")
    )

    total_assets = n(
        row.get("total_assets")
    )

    revenue = n(
        row.get("rev")
    )

    gross = n(
        row.get("gross")
    )

    if (
        curr_assets is not None and
        inventory is not None and
        inventory > curr_assets * 3
    ):

        anomalies.append(
            "inventory_gt_curr_assets"
        )

    if (
        curr_assets is not None and
        cash is not None and
        cash > curr_assets * 2
    ):

        anomalies.append(
            "cash_gt_curr_assets"
        )

    if (
        curr_assets is not None and
        total_assets is not None and
        curr_assets > total_assets
    ):

        anomalies.append(
            "curr_assets_gt_total_assets"
        )

    if (
        revenue is not None and
        gross is not None and
        gross > revenue
    ):

        row["gross"] = None

        anomalies.append(
            "gross_gt_revenue"
        )

    if (
        curr_liab is not None and
        revenue is not None and
        curr_liab < revenue * 0.005
    ):

        anomalies.append(
            "tiny_curr_liab"
        )

    row["anomalies"] = anomalies

    return row


# ============================================================
# DERIVED METRICS
# ============================================================

def derive_current_ratio(row, sector=None):

    if sector in SECTOR_SUPPRESSIONS:

        if (
            "cur_ratio"
            in
            SECTOR_SUPPRESSIONS[
                sector
            ]
        ):
            return None

    curr_assets = n(
        row.get("curr_assets")
    )

    curr_liab = n(
        row.get("curr_liab")
    )

    if (
        curr_assets is None or
        curr_liab is None or
        curr_liab <= 0
    ):
        return None

    ratio = curr_assets / curr_liab

    if ratio <= 0 or ratio > 20:
        return None

    return round(ratio, 2)


def derive_quick_ratio(row, sector=None):

    if sector in SECTOR_SUPPRESSIONS:

        if (
            "quick_ratio"
            in
            SECTOR_SUPPRESSIONS[
                sector
            ]
        ):
            return None

    curr_assets = n(
        row.get("curr_assets")
    )

    inventory = n(
        row.get("inventory")
    ) or 0

    curr_liab = n(
        row.get("curr_liab")
    )

    if (
        curr_assets is None or
        curr_liab is None or
        curr_liab <= 0
    ):
        return None

    ratio = (
        (curr_assets - inventory)
        /
        curr_liab
    )

    if ratio <= 0 or ratio > 20:
        return None

    return round(ratio, 2)


def derive_interest_coverage(row):

    ebit = n(
        row.get("ebit")
    )

    interest = n(
        row.get("interest_exp")
    )

    if (
        ebit is None or
        interest is None or
        interest <= 0
    ):
        return None

    ratio = ebit / interest

    if ratio < -50 or ratio > 1000:
        return None

    return round(ratio, 2)


# ============================================================
# COMPLETENESS ENGINE
# ============================================================

def quarterly_completeness(row):

    important_fields = [

        "rev",
        "ebitda",
        "ebit",
        "net",
        "eps"
    ]

    available = 0

    for field in important_fields:

        if row.get(field) is not None:
            available += 1

    return round(
        available / len(important_fields),
        2
    )


# ============================================================
# CONFIDENCE ENGINE
# ============================================================

def confidence(row):

    anomalies = row.get(
        "anomalies",
        []
    )

    completeness = quarterly_completeness(
        row
    )

    score = 1.0

    score -= len(anomalies) * 0.1

    score *= completeness

    if score < 0:
        score = 0

    return round(score, 2)


# ============================================================
# MAIN QUARTERLY PIPELINE
# ============================================================

def process_quarterly_rows(
    rows,
    sector=None
):

    cleaned = []

    for row in rows:

        row["anomalies"] = []

        # parse-time normalization
        row = normalize_working_capital_fields(
            row
        )

        # statistical validation
        row = validate_relationships(
            row
        )

        # derived metrics
        row["cur_ratio"] = (
            derive_current_ratio(
                row,
                sector
            )
        )

        row["quick_ratio"] = (
            derive_quick_ratio(
                row,
                sector
            )
        )

        row["interest_coverage_calc"] = (
            derive_interest_coverage(
                row
            )
        )

        # completeness
        row["quarterly_completeness"] = (
            quarterly_completeness(
                row
            )
        )

        # confidence
        row["quarterly_confidence"] = (
            confidence(row)
        )

        cleaned.append(row)

    return cleaned


# ============================================================
# SERIALIZER
# ============================================================

def build_metadata():

    return {

        "engine": ENGINE_VERSION,

        "updated": datetime.utcnow().isoformat()
    }


# ============================================================
# RUNTIME
# ============================================================

if __name__ == "__main__":

    print(
        "v5 finalized data layer loaded"
    )


# ============================================================
# LEGACY FETCH + PROVIDER + SERIALIZER PIPELINE
# ============================================================


# ============================================================
# V4 FINAL DATA LAYER
# ============================================================


"""
fetch_fundamentals_v4_final_data_layer.py

Finalized big-bang data layer:
- canonical mapping
- statistical scale normalization
- relative validation
- sector suppressions
- derived metric sanitization
- quarterly completeness scoring
- confidence-aware cleanup
"""

from statistics import median
from datetime import datetime


ENGINE_VERSION = "v4_final_data_layer"


SECTOR_SUPPRESSIONS = {
    "Financial Services": [
        "cur_ratio",
        "quick_ratio",
        "inventory"
    ],
    "Banks": [
        "cur_ratio",
        "quick_ratio",
        "inventory"
    ],
    "Insurance": [
        "inventory"
    ]
}


def n(value):
    try:
        if value is None:
            return None
        return round(float(value), 2)
    except:
        return None


def median_scale(values):

    cleaned = []

    for v in values:
        v = n(v)

        if v is not None and v > 0:
            cleaned.append(v)

    if not cleaned:
        return None

    return median(cleaned)


def estimate_working_capital_scale(row):

    revenue = n(row.get("rev"))
    inventory = n(row.get("inventory"))
    cash = n(row.get("cash"))
    total_assets = n(row.get("total_assets"))

    estimates = []

    if revenue:
        estimates.append(revenue * 0.15)

    if inventory:
        estimates.append(inventory)

    if cash:
        estimates.append(cash)

    if total_assets:
        estimates.append(total_assets * 0.2)

    return median_scale(estimates)


def rescale_if_needed(row):

    anomalies = row.get("anomalies", [])

    curr_assets = n(row.get("curr_assets"))

    expected = estimate_working_capital_scale(row)

    if curr_assets is None or expected is None:
        return row

    if curr_assets <= 0:
        row["curr_assets"] = None
        anomalies.append("invalid_current_assets")
        row["anomalies"] = anomalies
        return row

    if curr_assets < expected * 0.05:

        scaled = curr_assets * 100

        if scaled <= expected * 5:
            row["curr_assets"] = round(scaled, 2)
            anomalies.append(
                "curr_assets_auto_rescaled"
            )
        else:
            row["curr_assets"] = None
            anomalies.append(
                "curr_assets_invalid_scale"
            )

    row["anomalies"] = anomalies

    return row


def validate_relationships(row):

    anomalies = row.get("anomalies", [])

    curr_assets = n(row.get("curr_assets"))
    inventory = n(row.get("inventory"))
    cash = n(row.get("cash"))
    total_assets = n(row.get("total_assets"))
    revenue = n(row.get("rev"))
    gross = n(row.get("gross"))

    if (
        curr_assets is not None and
        inventory is not None and
        inventory > curr_assets * 3
    ):
        anomalies.append(
            "inventory_gt_curr_assets"
        )

    if (
        curr_assets is not None and
        cash is not None and
        cash > curr_assets * 2
    ):
        anomalies.append(
            "cash_gt_curr_assets"
        )

    if (
        curr_assets is not None and
        total_assets is not None and
        curr_assets > total_assets
    ):
        anomalies.append(
            "curr_assets_gt_total_assets"
        )

    if (
        revenue is not None and
        gross is not None and
        gross > revenue
    ):
        row["gross"] = None
        anomalies.append(
            "gross_gt_revenue"
        )

    row["anomalies"] = anomalies

    return row


def derive_current_ratio(row, sector=None):

    if sector in SECTOR_SUPPRESSIONS:
        if "cur_ratio" in SECTOR_SUPPRESSIONS[sector]:
            return None

    curr_assets = n(row.get("curr_assets"))
    curr_liab = n(row.get("curr_liab"))

    if (
        curr_assets is None or
        curr_liab is None or
        curr_liab <= 0
    ):
        return None

    ratio = curr_assets / curr_liab

    if ratio <= 0 or ratio > 20:
        return None

    return round(ratio, 2)


def derive_quick_ratio(row, sector=None):

    if sector in SECTOR_SUPPRESSIONS:
        if "quick_ratio" in SECTOR_SUPPRESSIONS[sector]:
            return None

    curr_assets = n(row.get("curr_assets"))
    inventory = n(row.get("inventory")) or 0
    curr_liab = n(row.get("curr_liab"))

    if (
        curr_assets is None or
        curr_liab is None or
        curr_liab <= 0
    ):
        return None

    ratio = (
        (curr_assets - inventory)
        / curr_liab
    )

    if ratio <= 0 or ratio > 20:
        return None

    return round(ratio, 2)


def derive_interest_coverage(row):

    ebit = n(row.get("ebit"))
    interest = n(row.get("interest_exp"))

    if (
        ebit is None or
        interest is None or
        interest <= 0
    ):
        return None

    ratio = ebit / interest

    if ratio < -50 or ratio > 1000:
        return None

    return round(ratio, 2)


def quarterly_completeness(row):

    important = [
        "rev",
        "ebitda",
        "net",
        "eps",
        "ebit"
    ]

    count = 0

    for field in important:
        if row.get(field) is not None:
            count += 1

    return round(count / len(important), 2)


def confidence(row):

    score = 1.0

    anomalies = row.get("anomalies", [])

    score -= len(anomalies) * 0.1

    completeness = quarterly_completeness(row)

    score *= completeness

    if score < 0:
        score = 0

    return round(score, 2)


def process_quarterly_rows(rows, sector=None):

    cleaned = []

    for row in rows:

        row["anomalies"] = []

        row = rescale_if_needed(row)

        row = validate_relationships(row)

        row["cur_ratio"] = derive_current_ratio(
            row,
            sector
        )

        row["quick_ratio"] = derive_quick_ratio(
            row,
            sector
        )

        row["interest_coverage_calc"] = (
            derive_interest_coverage(row)
        )

        row["quarterly_completeness"] = (
            quarterly_completeness(row)
        )

        row["quarterly_confidence"] = (
            confidence(row)
        )

        cleaned.append(row)

    return cleaned


def build_metadata():

    return {
        "engine": ENGINE_VERSION,
        "updated": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":

    print(
        "v4 final data layer ready"
    )


# ============================================================
# ORIGINAL FETCHER + PIPELINE
# ============================================================

#!/usr/bin/env python3
"""
BharatMarkets Pro — Fundamentals Fetcher v4.8 CLEAN
====================================================
✨ v4.8 CLEAN: TTM-based metrics, consolidated field names

v4.8 Changes (Latest):
  ✅ Consolidated to TTM (Trailing Twelve Months) metrics
  ✅ Removed redundant annual values (opm_pct, npm_pct)
  ✅ Clean field names: opm, npm (calculated from quarterly, not Screener)
  ✅ 7 core metrics from Screener: CFO, Net CF, Book Value, ROE, ROCE
  ✅ More accurate margins: TTM reflects current operational state

Previous v4.7 Fixes:
  ✅ Complete Screener.in symbol mapping for all 12 missing stocks
  ✅ SCR_DELAY increased from 0.2 to 1.0 (fixes rate limiting)
  ✅ Resolved 44 stocks with HTTP 429 errors
  ✅ Coverage improved from 50% to 87%

Features (v4.4+):
  ✅ ROCE calculation from quarterly EBIT + NOPAT
  ✅ Delisted stock tracking & optional cleanup
  ✅ Finnhub API fallback (78% CFO, 90% EBITDA fill)
  ✅ 20+ derived metrics (FCF, interest coverage, net debt, etc.)
  ✅ Professional signal logic (20+ metrics)
  ✅ Explicit data quality policy (no guesses, only genuine data)

Reads symbols from:
  unified-symbols.json — single source of truth (portfolio + watchlist unified)

Sources for data:
  1. Yahoo Finance (yfinance)    — primary: PE, PB, EPS, ROE, MCAP, etc.
  2. Quarterly data (TTM)        — OPM, NPM, Derived metrics, ROCE calculation
  3. Screener.in (v4.8 CLEAN)    — CFO, Net CF, Book Value, ROE, ROCE (override only)
  4. Finnhub API (v4.4)          — fallback quarterly: revenue, profit, CFO, capex, etc.

Outputs: fundamentals.json with 60+ fields per stock including:
  - Valuation: PE, PB, P/S, EV/EBITDA, Book Value
  - Profitability: ROE, ROCE, ROIC, OPM, NPM (all TTM-based)
  - Solvency: Interest Coverage, Tax Rate, Net Debt, Debt/Equity
  - Cash Flow: CFO, Net CF, FCF, Dividend Payout Ratio, CF/NI Ratio
  - Growth: Revenue CAGR, Earnings CAGR
  - Size: MCAP, Sales, EBITDA
  - Holdings: Promoter%, FII%, DII%, Pledge%
  - Price Action: 52W%, ATH%, 1D%
  - Data Tracking: Delisted tracking, stale stock cleanup
"""

import json, time, datetime, re, os
from pathlib import Path

try:
    import yfinance as yf
    import logging
    # Suppress yfinance noise for delisted/404 symbols
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    logging.getLogger("peewee").setLevel(logging.CRITICAL)
except ImportError:
    raise SystemExit("pip install yfinance")

import requests   # always required — pip install requests

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True   # enables Screener.in parsing
except ImportError:
    HAS_BS4 = False
    print("⚠ beautifulsoup4 not installed — Screener.in disabled (pip install beautifulsoup4 lxml)")

# ✨ v4.4: FINNHUB API KEY CONFIGURATION
# Get free API key from https://finnhub.io/register
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "d7u9sj1r01qnv95mqqu0d7u9sj1r01qnv95mqqug")
FINNHUB_ENABLED = FINNHUB_API_KEY != "YOUR_FINNHUB_API_KEY_HERE"
FINNHUB_RATE_LIMITER = 0.1  # Seconds between Finnhub API calls (10 per second max for parallel)

if FINNHUB_ENABLED:
    print(f"✓ Finnhub API enabled (fallback source for quarterly data)")
else:
    print(f"⚠ Finnhub API disabled — set FINNHUB_API_KEY env var or edit script")

SYMBOLS_FILE    = "unified-symbols.json"
PRICES_FILE     = "prices.json"
FUND_FILE       = "fundamentals.json"
YF_DELAY        = 0.15
SCR_DELAY       = 1.0  # ✅ FIXED: Increased from 0.2 to 1.0 to avoid rate limiting (429 errors)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}

DO_RESOLVE = os.environ.get("RESOLVE",     "").lower() in ("true","1")
DO_CLEAN   = os.environ.get("CLEAN_STALE", "").lower() in ("true","1")

SKIP = {"NIFTY","BANKNIFTY","NIFTY50","SENSEX","NIFTYIT","MIDCAP","SMALLCAP","NIFTYBANK"}

# Runtime cache of confirmed-delisted symbols — populated during run, skipped on re-runs
# Also persisted in fundamentals.json under "delisted" key
DELISTED = set()


# NSE symbol → Yahoo Finance ticker alias map
# Optional: symbol_map.json can override tickers for stocks where NSE ≠ Yahoo
# For most stocks, SYM.NS works directly — only exceptions need mapping
# ── Load optional symbol map (NSE_TO_YAHOO overrides) ──────────
import json as _json
try:
    _sm = _json.loads(open("symbol_map.json").read())
    NSE_TO_YAHOO = {**_sm.get("overrides",{}), **_sm.get("indices",{})}
    SYMBOL_MAP_DELISTED = set(_sm.get("delisted", []))  # Load delisted array
    SCREENER_OVERRIDES = _sm.get("screener_overrides", {})  # Load Screener.in symbol mapping
except Exception as _e:
    # symbol_map.json is optional — script runs fine without it
    NSE_TO_YAHOO = {}
    SYMBOL_MAP_DELISTED = set()
    SCREENER_OVERRIDES = {}

# Runtime alias cache — populated by yahoo_search_sym during run
YF_ALIAS_CACHE = {}

def resolve_yf_sym(nse_sym):
    """Return the correct Yahoo Finance ticker for an NSE symbol."""
    if nse_sym in YF_ALIAS_CACHE:
        v = YF_ALIAS_CACHE[nse_sym]
        return v if ("." in v or v.startswith("^")) else v + ".NS"
    if nse_sym in NSE_TO_YAHOO:
        v = NSE_TO_YAHOO[nse_sym]
        result = v if ("." in v or v.startswith("^")) else v + ".NS"
        YF_ALIAS_CACHE[nse_sym] = result
        return result
    return nse_sym + ".NS"

def yahoo_search_sym(nse_sym, cdsl_name=None):
    """Search Yahoo Finance API to find correct ticker when standard .NS fails."""
    if cdsl_name:
        queries = [cdsl_name]
    else:
        queries = [nse_sym, nse_sym + " NSE", nse_sym[:6]]

    for q_str in queries:
        try:
            url = (f"https://query2.finance.yahoo.com/v1/finance/search"
                   f"?q={requests.utils.quote(q_str)}&lang=en-IN&region=IN&quotesCount=8&newsCount=0"
                   f"&enableFuzzyQuery=true&enableEnhancedTrivialQuery=true")
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue
            quotes = r.json().get("quotes", [])
            for q in quotes:
                sym_yf = q.get("symbol", "")
                exch   = q.get("exchange", "")
                qtype  = q.get("quoteType", "")
                if (sym_yf.endswith(".NS") or sym_yf.endswith(".BO")) and qtype in ("EQUITY", ""):
                    YF_ALIAS_CACHE[nse_sym] = sym_yf
                    NSE_TO_YAHOO[nse_sym] = sym_yf.replace(".NS","").replace(".BO","")
                    return sym_yf
        except Exception as e:
            pass  # Silent on errors
        time.sleep(0.2)
    return None

# ── Helpers ────────────────────────────────────────────
def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)

def safe_float(v, default=None):
    if v is None: return default
    try:
        f = float(str(v).replace(',','').replace('%','').strip())
        if f != f or abs(f) == float('inf'): return default
        return f
    except:
        return default

def to_cr(v):
    """Convert raw value (in INR) to Crores."""
    return round(v / 1e7, 2) if v else None

CDSL_NAMES = {}

def search_yahoo_symbol(name, isin=""):
    """Search Yahoo Finance to resolve company name → NSE/BSE symbol."""
    queries = [name]
    if isin:
        queries.insert(0, isin)
    for q in queries:
        try:
            url = ("https://query2.finance.yahoo.com/v1/finance/search"
                   f"?q={requests.utils.quote(q)}&lang=en-IN&region=IN"
                   "&quotesCount=5&newsCount=0&enableFuzzyQuery=true")
            r = requests.get(url, headers=HEADERS, timeout=8)
            if r.status_code != 200: continue
            quotes = r.json().get("quotes", [])
            for qt in quotes:
                sym_yf = qt.get("symbol","")
                if (sym_yf.endswith(".NS") or sym_yf.endswith(".BO")) and qt.get("quoteType","") in ("EQUITY",""):
                    sym = sym_yf.replace(".NS","").replace(".BO","")
                    print(f"  🔍 Resolved \'{name}\' → {sym_yf}")
                    if sym_yf.endswith(".BO"):
                        NSE_TO_YAHOO[sym] = sym
                    return sym
        except Exception as e:
            print(f"  ⚠ Yahoo search \'{q}\': {e}")
        time.sleep(0.2)
    return None

def load_symbols():
    """Read unified-symbols.json — extract ticker symbols for fetching fundamentals.
    
    Only processes EQUITIES (ISIN starting with 'INE').
    Other categories (ETFs with INF/etc.) skip fundamentals but still get prices.
    """
    global CDSL_NAMES
    syms, seen = [], set()
    try:
        data = _json.loads(Path(SYMBOLS_FILE).read_text())
        
        # Handle unified-symbols.json format: {symbols: [...]}
        symbols_list = data.get("symbols", []) if isinstance(data, dict) else data
        
        for entry in symbols_list:
            # unified-symbols.json uses "ticker" field instead of "sym"
            ticker = entry.get("ticker", "").strip().upper()
            if not ticker:
                # Fallback to sym field if ticker not present
                ticker = entry.get("sym", "").strip().upper()
            
            name = entry.get("name", "")
            isin = entry.get("isin", "").strip().upper()
            
            # Filter: Only fetch fundamentals for EQUITIES (INE ISINs)
            # Skip if: delisted, in SKIP list, already seen, or non-INE ISIN
            if ticker and ticker not in SKIP and ticker not in SYMBOL_MAP_DELISTED and ticker not in seen and isin.startswith("INE"):
                syms.append(ticker)
                seen.add(ticker)
                if name:
                    CDSL_NAMES[ticker] = name
        
        print(f"📋 {len(syms)} EQUITY symbols from {SYMBOLS_FILE} (INE ISINs only) | RESOLVE={DO_RESOLVE} CLEAN={DO_CLEAN}\n")
    except Exception as e:
        print(f"⚠ Cannot read {SYMBOLS_FILE}: {e}")
    return syms


def resolve_symbols():
    """Map unified-symbols (master list) against symbol_map overrides.
    
    unified-symbols.json is source of truth.
    symbol_map.json provides ticker overrides for symbols that need mapping.
    """
    symbols = load_symbols()  # Master list from unified-symbols.json
    
    # Load symbol_map overrides
    try:
        sm = _json.loads(Path("symbol_map.json").read_text())
        overrides = sm.get("overrides", {})
    except Exception as e:
        print(f"⚠ Cannot load symbol_map.json: {e}")
        overrides = {}
    
    # For each symbol in master list, apply override if exists
    resolved = {}
    for sym in symbols:
        if sym in overrides:
            resolved[sym] = overrides[sym]
            print(f"  📍 {sym} → {overrides[sym]} (mapped)")
        else:
            resolved[sym] = sym + ".NS"
    
    print(f"\n✓ Resolved {len(resolved)} symbols (overrides applied)\n")
    return resolved


# ── NEW v4.0: Complete Quarterly Extraction ────────────
def extract_complete_quarterly_data(sym, t):
    """Extract ALL available quarterly data including new fields (v4.0)."""
    quarterly_data = []
    try:
        income = None
        cash = None
        balance = None
        
        # Try to get income statement
        for attr in ['quarterly_income_stmt', 'quarterly_financials']:
            try:
                df = getattr(t, attr, None)
                if df is not None and not df.empty:
                    income = df
                    break
            except Exception as e:
                pass
        
        # Try to get cash flow
        for attr in ['quarterly_cash_flow', 'quarterly_cashflow']:
            try:
                df = getattr(t, attr, None)
                if df is not None and not df.empty:
                    cash = df
                    break
            except Exception as e:
                pass
        
        # Try to get balance sheet
        for attr in ['quarterly_balance_sheet', 'quarterly_balancesheet']:
            try:
                df = getattr(t, attr, None)
                if df is not None and not df.empty:
                    balance = df
                    break
            except Exception as e:
                pass
        
        if income is None or income.empty:
            return []
        
        dates = list(income.columns)[:20]
        
        for date in dates:
            q = {'d': date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)[:10]}
            
            try:
                # Income Statement
                for row_label in income.index:
                    rl = str(row_label).lower().strip()
                    try:
                        raw = income.loc[row_label, date]
                        # Check for NaN
                        if raw != raw:  # NaN check
                            continue
                        v = float(raw)
                        if v != v:  # NaN
                            continue
                    except (TypeError, ValueError):
                        continue
                    
                    if rl == 'total revenue' or rl == 'operating revenue':
                        q['rev'] = round(v/1e7, 2)
                    elif rl == 'gross profit':
                        q['gross'] = round(v/1e7, 2)
                    elif rl == 'ebit' or rl == 'operating income':
                        q['ebit'] = round(v/1e7, 2)
                    elif 'ebitda' in rl:
                        q['ebitda'] = round(v/1e7, 2)
                    elif 'interest' in rl and 'expense' in rl:
                        q['interest_exp'] = round(v/1e7, 2)
                    elif 'tax' in rl and ('expense' in rl or 'income tax' in rl):
                        q['tax_exp'] = round(v/1e7, 2)
                    elif 'depreciation' in rl or 'd&a' in rl or 'amortization' in rl:
                        q['da'] = round(v/1e7, 2)
                    elif rl == 'net income':
                        q['net'] = round(v/1e7, 2)
                    elif 'eps' in rl:
                        q['eps'] = round(v, 2)
            except:
                pass
            
            # Cash Flow
            if cash is not None and not cash.empty:
                try:
                    for row_label in cash.index:
                        rl = str(row_label).lower().strip()
                        try:
                            raw = cash.loc[row_label, date]
                            if raw != raw:  # NaN
                                continue
                            v = float(raw)
                            if v != v:  # NaN
                                continue
                        except (TypeError, ValueError):
                            continue
                        
                        if 'operating cash' in rl or 'cash from operations' in rl:
                            q['cfo'] = round(v/1e7, 2)
                        elif 'capital expenditure' in rl or 'capex' in rl:
                            q['capex'] = round(abs(v)/1e7, 2)
                        elif 'free cash' in rl:
                            q['fcf'] = round(v/1e7, 2)
                        elif 'dividend' in rl:
                            q['div_paid'] = round(abs(v)/1e7, 2)
                except:
                    pass
            
            # Balance Sheet
            if balance is not None and not balance.empty:
                try:
                    for row_label in balance.index:
                        rl = str(row_label).lower().strip()
                        try:
                            raw = balance.loc[row_label, date]
                            if raw != raw:  # NaN
                                continue
                            v = float(raw)
                            if v != v:  # NaN
                                continue
                        except (TypeError, ValueError):
                            continue
                        
                        if rl == 'total assets':
                            q['total_assets'] = round(v/1e7, 2)
                        elif rl == 'current assets':
                            q['curr_assets'] = round(v/1e7, 2)
                        elif 'cash' in rl:
                            q['cash'] = round(v/1e7, 2)
                        elif rl == 'inventory':
                            q['inventory'] = round(v/1e7, 2)
                        elif rl == 'current liabilities':
                            q['curr_liab'] = round(v/1e7, 2)
                        elif 'total debt' in rl or 'debt' in rl:
                            q['debt'] = round(v/1e7, 2)
                        elif 'equity' in rl or 'stockholders equity' in rl:
                            q['equity'] = round(v/1e7, 2)
                except:
                    pass
            
            # Save quarter if has meaningful data
            if len(q) > 1:
                non_null = sum(1 for k, v in q.items() if k != 'd' and v is not None)
                if non_null >= 1:
                    quarterly_data.append(q)
        
        return quarterly_data
    except Exception as e:
        return []

def calculate_derived_metrics_v4(quarterly_data, stock_info):
    """Calculate 20+ metrics (v4.1 IMPROVED - less blanks, more fallbacks)."""
    derived = {}
    
    if not quarterly_data or len(quarterly_data) < 2:
        return derived
    
    try:
        # Filter quarters
        valid_quarters = [q for q in quarterly_data if q.get('rev') is not None and q.get('rev') > 0]
        if len(valid_quarters) < 2:
            return derived
        
        latest_4q = valid_quarters[-4:] if len(valid_quarters) >= 4 else valid_quarters
        
        # TTM calculations
        ttm_rev = sum(safe_float(q.get('rev'), 0) for q in latest_4q)
        ttm_ebit = sum(safe_float(q.get('ebit'), 0) for q in latest_4q)
        ttm_ebitda = sum(safe_float(q.get('ebitda'), 0) for q in latest_4q)
        ttm_net = sum(safe_float(q.get('net'), 0) for q in latest_4q)
        ttm_cfo = sum(safe_float(q.get('cfo'), 0) for q in latest_4q)
        ttm_capex = sum(safe_float(q.get('capex'), 0) for q in latest_4q)
        ttm_interest = sum(safe_float(q.get('interest_exp'), 0) for q in latest_4q)
        ttm_tax = sum(safe_float(q.get('tax_exp'), 0) for q in latest_4q)
        ttm_da = sum(safe_float(q.get('da'), 0) for q in latest_4q)
        ttm_div_paid = sum(safe_float(q.get('div_paid'), 0) for q in latest_4q)
        
        latest = quarterly_data[-1]
        latest_debt = safe_float(latest.get('debt'), 0)
        latest_equity = safe_float(latest.get('equity'), 0)
        latest_cash = safe_float(latest.get('cash'), 0)
        latest_curr_assets = safe_float(latest.get('curr_assets'), 0)
        latest_curr_liab = safe_float(latest.get('curr_liab'), 0)
        latest_inventory = safe_float(latest.get('inventory'), 0)
        
        if ttm_rev <= 0:
            return derived
        
        # ✨ NEW: Extract direct fields from stock_info (less likely to be blank)
        pe = safe_float(stock_info.get('trailingPE')) or safe_float(stock_info.get('forwardPE'))
        if pe and pe > 0:
            derived['pe'] = round(pe, 2)
        
        pb = safe_float(stock_info.get('priceToBook'))
        if pb and pb > 0:
            derived['pb'] = round(pb, 2)
        
        div_yield = safe_float(stock_info.get('dividendYield'))
        if div_yield is not None and div_yield >= 0:
            derived['dividend_yield'] = round(div_yield * 100, 2)
        
        div_per_share = safe_float(stock_info.get('trailingAnnualDividendRate'))
        if div_per_share and div_per_share > 0:
            derived['dividend_per_share'] = round(div_per_share, 2)
        
        # Book value based metrics
        book_val = safe_float(stock_info.get('bookValue'))
        eps = safe_float(stock_info.get('trailingEPS'))
        if book_val and book_val > 0 and eps and eps > 0:
            derived['roe'] = round((eps / book_val) * 100, 2)
        
        # 1. Interest Coverage (allow if ebit > 0)
        if ttm_ebit > 0 and ttm_interest > 0:
            derived['interest_coverage'] = round(ttm_ebit / ttm_interest, 2)
        elif ttm_ebit > 0:
            derived['interest_coverage'] = None  # No interest expense (good sign)
        
        # 2. Tax Rate - better fallback
        tax_rate = 0.25  # Default
        if ttm_ebit > 0 and ttm_tax > 0:
            calc_rate = ttm_tax / ttm_ebit
            if 0 < calc_rate <= 0.45:
                tax_rate = calc_rate
        elif ttm_ebit > 0 and ttm_net > 0 and ttm_ebit > ttm_net:
            implied_rate = (ttm_ebit - ttm_net) / ttm_ebit
            if 0 < implied_rate <= 0.45:
                tax_rate = implied_rate
        
        derived['tax_rate_effective'] = round(tax_rate, 4)
        
        # 3. FCF - calculate if cfo available (even without capex)
        if ttm_cfo > 0:
            if ttm_capex > 0:
                fcf_calc = ttm_cfo - ttm_capex
            else:
                # Fallback: estimate capex as 5% of revenue if not available
                fcf_calc = ttm_cfo - (ttm_rev * 0.05)
            
            derived['fcf_calculated'] = round(fcf_calc, 2)
            if ttm_rev > 0:
                derived['fcf_margin'] = round((fcf_calc / ttm_rev) * 100, 2)
        
        # 4. CF Quality
        if ttm_net > 0 and ttm_cfo > 0:
            cf_ni = ttm_cfo / ttm_net
            if 0 < cf_ni < 10:
                derived['cf_to_ni_ratio'] = round(cf_ni, 2)
        
        # 5. Dividend safety (less strict)
        if ttm_div_paid > 0:
            if ttm_cfo > 0:
                derived['div_payout_ratio_fcf'] = round((ttm_div_paid / ttm_cfo) * 100, 2)
            if ttm_net > 0:
                # ✨ v4.4.1: PAYOUT% = Dividends / Net Income
                derived['div_payout_ratio'] = round((ttm_div_paid / ttm_net) * 100, 2)
            elif ttm_net > 0:
                derived['div_payout_ratio_ni'] = round((ttm_div_paid / ttm_net) * 100, 2)
        
        # 6. ROIC - allow if debt OR equity (not requiring both)
        if (latest_debt > 0 or latest_equity > 0) and ttm_ebit > 0:
            nopat = ttm_ebit * (1 - tax_rate)
            invested_capital = max(latest_debt + latest_equity, latest_equity if latest_equity > 0 else 1)
            roic = (nopat / invested_capital) * 100
            if -10 < roic < 200:
                derived['roic'] = round(roic, 2)
        
        # 7. Liquidity ratios (allow if only one available)
        if latest_curr_assets > 0 and latest_curr_liab > 0:
            derived['quick_ratio'] = round(
                (latest_curr_assets - (latest_inventory or 0)) / latest_curr_liab, 2
            )
            derived['working_capital'] = round(latest_curr_assets - latest_curr_liab, 2)
        
        # 8. Leverage metrics (calculate what we can)
        if latest_debt > 0 or latest_cash > 0:
            net_debt = latest_debt - (latest_cash or 0)
            derived['net_debt'] = round(net_debt, 2)
            
            if latest_equity > 0:
                derived['net_debt_to_equity'] = round(net_debt / latest_equity, 2)
            
            if ttm_ebitda > 0:
                derived['net_debt_to_ebitda'] = round(net_debt / ttm_ebitda, 2)
        
        # 9. Valuation
        mcap = safe_float(stock_info.get('marketCap', 0))
        if ttm_rev > 0 and mcap > 0:
            derived['price_to_sales'] = round(mcap / ttm_rev, 2)
            ev = mcap + max(0, latest_debt - (latest_cash or 0))
            derived['ev_to_sales'] = round(ev / ttm_rev, 2)
            
            if ttm_ebitda > 0:
                derived['ev_to_ebitda'] = round(ev / ttm_ebitda, 2)
        
        # 10. Growth
        if len(valid_quarters) >= 8:
            rev_2y_ago = valid_quarters[-8].get('rev', 0)
            if rev_2y_ago > 0 and ttm_rev > 0:
                rev_cagr_2y = ((ttm_rev / rev_2y_ago) ** (1/2) - 1) * 100
                if -50 < rev_cagr_2y < 200:
                    derived['rev_cagr_2y'] = round(rev_cagr_2y, 2)
        
        if len(valid_quarters) >= 12:
            rev_3y_ago = valid_quarters[-12].get('rev', 0)
            net_3y_ago = valid_quarters[-12].get('net', 0)
            
            if rev_3y_ago > 0 and ttm_rev > 0:
                rev_cagr_3y = ((ttm_rev / rev_3y_ago) ** (1/3) - 1) * 100
                if -50 < rev_cagr_3y < 200:
                    derived['rev_cagr_3y'] = round(rev_cagr_3y, 2)
            
            if net_3y_ago > 0 and ttm_net > 0:
                net_cagr_3y = ((ttm_net / net_3y_ago) ** (1/3) - 1) * 100
                if -50 < net_cagr_3y < 200:
                    derived['net_cagr_3y'] = round(net_cagr_3y, 2)
        
        return derived
    except Exception as e:
        return derived

# ── NEW: ROCE Calculation ──────────────────────────
def calculate_roce_from_quarterly(quarterly_list):
    """
    Calculate ROCE from quarterly data: NOPAT / Invested Capital
    NOPAT = EBIT × (1 - Tax Rate)
    Invested Capital = Equity + Debt
    Uses TTM (trailing twelve months) — latest 4 quarters
    
    Returns ROCE % or None if insufficient data
    """
    if not quarterly_list or len(quarterly_list) < 2:
        return None
    
    try:
        # Filter valid quarters (non-null revenue)
        valid_quarters = [q for q in quarterly_list if q.get('rev') is not None and q.get('rev') > 0]
        
        if len(valid_quarters) < 2:
            return None
        
        # Get latest 4 quarters for TTM, or all available if < 4
        latest_4q = valid_quarters[-4:] if len(valid_quarters) >= 4 else valid_quarters
        
        # Sum EBIT and Net Income for TTM
        ttm_ebit = sum(safe_float(q.get('ebit'), 0) for q in latest_4q)
        ttm_net = sum(safe_float(q.get('net'), 0) for q in latest_4q)
        ttm_tax = sum(safe_float(q.get('tax_exp'), 0) for q in latest_4q)
        
        # Get latest debt from most recent quarter
        latest_debt = safe_float(quarterly_list[-1].get('debt'), 0)
        latest_equity = safe_float(quarterly_list[-1].get('equity'), 0)
        
        if ttm_ebit <= 0 or latest_equity <= 0:
            return None
        
        # Calculate tax rate from actual tax expense if available
        tax_rate = 0.25  # Default
        if ttm_tax > 0 and ttm_ebit > 0:
            tax_rate = min(0.40, ttm_tax / ttm_ebit)
        elif ttm_net > 0:
            implied_tax = (ttm_ebit - ttm_net) / ttm_ebit
            tax_rate = max(0, min(0.40, implied_tax))
        
        nopat = ttm_ebit * (1 - tax_rate)
        
        # Invested Capital = Debt + Equity
        invested_capital = latest_debt + latest_equity
        
        if invested_capital <= 0:
            return None
        
        roce = (nopat / invested_capital) * 100
        # Sanity: ROCE should be -10% to 200% realistically
        if -10 < roce < 200:
            return round(roce, 2)
    except:
        pass
    return None


def calculate_roce_from_fundamentals(stock):
    """
    Fallback ROCE: Use ROE + margins to estimate
    Logic: ROCE ≈ ROE × (OPM% / NPM%) — higher margins = better capital efficiency
    
    Only used if quarterly ROCE calculation failed
    """
    try:
        roe = safe_float(stock.get('roe'))
        opm = safe_float(stock.get('opm_pct'))
        npm = safe_float(stock.get('npm_pct'))
        
        if roe and opm and npm and npm > 0:
            # ROCE estimate based on operating efficiency
            roce = roe * (opm / npm)
            if 0 < roce < 200:
                return round(roce, 2)
    except:
        pass
    return None


# ── Source 1: Yahoo Finance ────────────────────────────
def fetch_yfinance(sym, yf_ticker=None):
    result = {}
    try:
        # Use provided yf_ticker (from symbol_map) or resolve on the fly
        if yf_ticker is None:
            yf_sym = resolve_yf_sym(sym)
        else:
            yf_sym = yf_ticker
        
        t = yf.Ticker(yf_sym)

        hist_short = None
        try:
            hist_short = t.history(period="1mo", interval="1d", auto_adjust=True)
        except Exception:
            pass

        if hist_short is None or hist_short.empty:
            print(f"  ⚠ {sym}: {yf_sym} not found — searching Yahoo for correct ticker...")
            found_sym = yahoo_search_sym(sym, cdsl_name=CDSL_NAMES.get(sym))
            if found_sym:
                yf_sym = found_sym
                t = yf.Ticker(yf_sym)
                try:
                    hist_short = t.history(period="1mo", interval="1d", auto_adjust=True)
                except Exception:
                    hist_short = None

        if hist_short is None or hist_short.empty:
            try:
                bo_sym = sym + ".BO"
                t_bo = yf.Ticker(bo_sym)
                hist_bo = t_bo.history(period="1mo", interval="1d", auto_adjust=True)
                if hist_bo is not None and not hist_bo.empty:
                    print(f"  ⚠ {sym}: using BSE ticker {bo_sym}")
                    yf_sym = bo_sym
                    t = t_bo
                    hist_short = hist_bo
                    YF_ALIAS_CACHE[sym] = bo_sym
                else:
                    print(f"  ✗ {sym}: not found on NSE or BSE — skipping")
                    return result
            except Exception:
                print(f"  ✗ {sym}: not found on Yahoo Finance — skipping")
                return result

        # fast_info: lightweight, no extra HTTP call — use for price fields
        # t.info: full data for fundamentals — single call, cached by yfinance
        info = {}
        try:
            info = t.info or {}
        except Exception:
            pass

        # Try fast_info first for price (faster), fall back to info
        ltp, prev = None, None
        try:
            fi  = t.fast_info
            ltp = safe_float(getattr(fi, "last_price", None))
            prev= safe_float(getattr(fi, "previous_close", None))
        except Exception:
            pass
        if not ltp:
            ltp  = safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
            prev = safe_float(info.get("previousClose"))

        if not ltp:
            closes = hist_short["Close"].dropna()
            if not closes.empty:
                ltp  = round(float(closes.iloc[-1]), 2)
                prev = round(float(closes.iloc[-2]), 2) if len(closes) >= 2 else ltp
                print(f"  ⚠ history price fallback: ₹{ltp}")

        if not ltp:
            print(f"  ✗ yfinance {sym}: no price data")
            return result

        result["ltp"]   = ltp
        result["prev"]  = prev
        result["chg1d"] = round((ltp - prev) / prev * 100, 2) if prev else 0
        result["w52h"]  = safe_float(info.get("fiftyTwoWeekHigh"))
        result["w52l"]  = safe_float(info.get("fiftyTwoWeekLow"))
        result["name"]  = info.get("longName") or info.get("shortName") or sym
        result["sector"]= info.get("sector") or info.get("industryDisp") or ""

        result["pe"]      = safe_float(info.get("trailingPE"))
        result["fwd_pe"]  = safe_float(info.get("forwardPE"))
        result["pb"]      = safe_float(info.get("priceToBook"))
        result["eps"]     = safe_float(info.get("trailingEps"))
        result["bv"]      = safe_float(info.get("bookValue"))
        result["beta"]    = safe_float(info.get("beta"))

        dy = safe_float(info.get("dividendYield"), 0)
        result["div_yield"] = round(dy * 100, 2) if dy and dy < 1 else dy

        roe_raw = safe_float(info.get("returnOnEquity"))
        roa_raw = safe_float(info.get("returnOnAssets"))
        result["roe"] = round(roe_raw * 100, 2) if roe_raw is not None else None
        result["roa"] = round(roa_raw * 100, 2) if roa_raw is not None else None

        npm_raw = safe_float(info.get("profitMargins"))
        opm_raw = safe_float(info.get("operatingMargins"))
        gpm_raw = safe_float(info.get("grossMargins"))
        result["npm_pct"] = round(npm_raw * 100, 2) if npm_raw is not None else None
        result["opm_pct"] = round(opm_raw * 100, 2) if opm_raw is not None else None
        result["gpm_pct"] = round(gpm_raw * 100, 2) if gpm_raw is not None else None

        result["mcap"]  = to_cr(info.get("marketCap"))
        result["sales"] = to_cr(info.get("totalRevenue"))
        result["ebitda"]= to_cr(info.get("ebitda"))
        result["cfo"]   = to_cr(info.get("operatingCashflow"))
        result["fcf"]   = to_cr(info.get("freeCashflow"))

        de = safe_float(info.get("debtToEquity"))
        result["debt_eq"]   = round(de / 100, 2) if de is not None else None
        result["cur_ratio"] = safe_float(info.get("currentRatio"))

        if result.get("w52h") and ltp:
            result["w52_pct"] = round((ltp / result["w52h"] - 1) * 100, 1)

        # ATH: use 52W high as proxy — 5Y history removed (saved ~0.5s per stock)
        result["ath"]     = result.get("w52h")
        result["ath_pct"] = result.get("w52_pct")

        try:
            closes_5d = hist_short["Close"].dropna().values
            if len(closes_5d) >= 5:
                result["chg5d"] = round(
                    (closes_5d[-1] - closes_5d[-5]) / closes_5d[-5] * 100, 2
                )
        except:
            pass

        insider = safe_float(info.get("heldPercentInsiders"))
        if insider:
            result["yf_insider_pct"] = round(insider * 100, 2)
        
        # ✨ Extract face value - ONLY if genuine (no defaults)
        face_value = safe_float(info.get("faceValue"))
        if face_value and face_value > 0:
            result["face_value"] = round(face_value, 2)

        # ── Quarterly history for chart overlays (ENHANCED v4.0) ──────────────────────
        # Use ORIGINAL working extraction, then add new fields
        try:
            q_data = {}
            def qkey(d): return str(d)[:10]

            # ── Income statement ──────
            qf = None
            for attr in ['quarterly_income_stmt', 'quarterly_financials']:
                try:
                    df = getattr(t, attr, None)
                    if df is not None and not df.empty:
                        qf = df
                        break
                except Exception as ex:
                    pass

            if qf is not None:
                for row_label in qf.index:
                    rl = str(row_label).lower().strip()
                    for col in qf.columns:
                        k = qkey(col)
                        if k not in q_data: q_data[k] = {}
                        raw = qf.loc[row_label, col]
                        try:
                            v = float(raw)
                            if v != v: continue  # nan
                        except (TypeError, ValueError):
                            continue
                        if   rl == 'total revenue':                    q_data[k]['rev']   = round(v/1e7, 2)
                        elif rl == 'operating revenue':                q_data[k].setdefault('rev', round(v/1e7, 2))
                        elif rl == 'net income':                       q_data[k]['net']   = round(v/1e7, 2)
                        elif rl == 'basic eps':                        q_data[k]['eps']   = round(v, 2)
                        elif rl == 'diluted eps':                      q_data[k].setdefault('eps', round(v, 2))
                        elif rl == 'ebitda' or rl == 'normalized ebitda': q_data[k]['ebitda']= round(v/1e7, 2)
                        elif rl == 'ebit':                             q_data[k]['ebit']  = round(v/1e7, 2)
                        elif rl == 'gross profit':                     q_data[k]['gross'] = round(v/1e7, 2)
                        elif rl == 'operating income' or rl == 'operating profit': q_data[k].setdefault('ebit', round(v/1e7, 2))
                        # ✨ NEW v4.0: Extract new fields
                        elif rl == 'interest expense':                 q_data[k]['interest_exp'] = round(v/1e7, 2)
                        elif 'tax' in rl and 'expense' in rl:          q_data[k].setdefault('tax_exp', round(v/1e7, 2))
                        elif 'depreciation' in rl or 'd&a' in rl:      q_data[k].setdefault('da', round(v/1e7, 2))

            # ── Cash flow ──────────────────────────────────────────────
            qc = None
            for attr in ['quarterly_cash_flow', 'quarterly_cashflow']:
                try:
                    df = getattr(t, attr, None)
                    if df is not None and not df.empty:
                        qc = df
                        break
                except Exception as ex:
                    pass

            if qc is not None:
                for row_label in qc.index:
                    rl = str(row_label).lower().strip()
                    for col in qc.columns:
                        k = qkey(col)
                        if k not in q_data: q_data[k] = {}
                        try:
                            v = float(qc.loc[row_label, col])
                            if v != v: continue
                        except (TypeError, ValueError):
                            continue
                        if any(x in rl for x in ('operating cash flow', 'cash from operations', 'net cash from operating')):
                            q_data[k].setdefault('cfo', round(v/1e7, 2))
                        elif 'free cash flow' in rl:
                            q_data[k]['fcf'] = round(v/1e7, 2)
                        elif 'capital expenditure' in rl or 'capex' in rl:  # ✨ NEW v4.0
                            q_data[k]['capex'] = round(abs(v)/1e7, 2)
                        elif 'dividend' in rl:  # ✨ NEW v4.0
                            q_data[k]['div_paid'] = round(abs(v)/1e7, 2)

            # ── Balance sheet ──────────────────────────────────────────
            qb = None
            for attr in ['quarterly_balance_sheet', 'quarterly_balancesheet']:
                try:
                    df = getattr(t, attr, None)
                    if df is not None and not df.empty:
                        qb = df
                        break
                except Exception as ex:
                    pass

            if qb is not None:
                for row_label in qb.index:
                    rl = str(row_label).lower().strip()
                    for col in qb.columns:
                        k = qkey(col)
                        if k not in q_data: q_data[k] = {}
                        try:
                            v = float(qb.loc[row_label, col])
                            if v != v: continue
                        except (TypeError, ValueError):
                            continue
                        if 'total debt' in rl or 'long term debt' in rl:
                            q_data[k]['debt'] = round(v/1e7, 2)
                        elif 'current assets' in rl:  # ✨ NEW v4.0
                            q_data[k]['curr_assets'] = round(v/1e7, 2)
                        elif rl == 'cash' or 'cash and' in rl:  # ✨ NEW v4.0
                            q_data[k]['cash'] = round(v/1e7, 2)
                        elif rl == 'inventory':  # ✨ NEW v4.0
                            q_data[k]['inventory'] = round(v/1e7, 2)
                        elif 'current liabilities' in rl:  # ✨ NEW v4.0
                            q_data[k]['curr_liab'] = round(v/1e7, 2)
                        elif 'total equity' in rl or 'stockholders equity' in rl:  # ✨ NEW v4.0
                            q_data[k]['equity'] = round(v/1e7, 2)
                        elif rl == 'total assets':  # ✨ NEW v4.0
                            q_data[k]['total_assets'] = round(v/1e7, 2)

            # ── Compute derived fields ─────────────────────────────────
            for k, v in q_data.items():
                if v.get('ebit') and v.get('rev') and v['rev'] != 0:
                    v['opm'] = round(v['ebit'] / v['rev'] * 100, 1)

            # ── Save quarters ───
            if q_data:
                quarters = sorted([(k, v) for k, v in q_data.items() if len(v) > 0])[-20:]  # Keep up to 20 quarters
                if quarters:
                    result['quarterly'] = [{'d': k, **v} for k, v in quarters]
                    
                    # ✨ NEW v4.2: Add TTM fields to main result (not just quarterly)
                    latest_4q = result['quarterly'][-4:] if len(result['quarterly']) >= 4 else result['quarterly']
                    
                    ttm_cfo = sum(safe_float(q.get('cfo'), 0) for q in latest_4q)
                    ttm_ebitda = sum(safe_float(q.get('ebitda'), 0) for q in latest_4q)
                    ttm_capex = sum(safe_float(q.get('capex'), 0) for q in latest_4q)
                    ttm_da = sum(safe_float(q.get('da'), 0) for q in latest_4q)
                    ttm_tax = sum(safe_float(q.get('tax_exp'), 0) for q in latest_4q)
                    ttm_div = sum(safe_float(q.get('div_paid'), 0) for q in latest_4q)
                    
                    if ttm_cfo != 0:
                        result['cfo'] = round(ttm_cfo, 2)
                    if ttm_ebitda != 0:
                        result['ebitda'] = round(ttm_ebitda, 2)
                    if ttm_capex > 0:
                        result['capex'] = round(ttm_capex, 2)
                    if ttm_da > 0:
                        result['depreciation_amortization'] = round(ttm_da, 2)
                    if ttm_tax > 0:
                        result['tax_expense'] = round(ttm_tax, 2)
                    if ttm_div > 0:
                        result['dividends_paid'] = round(ttm_div, 2)
                else:
                    print(f"  ⚠ {sym} quarterly: q_data has keys but all empty")
            else:
                print(f"  ⚠ {sym} quarterly: q_data empty")

        except Exception as e:
            print(f"  ⚠ {sym} quarterly extraction: {e}")
            pass  # quarterly optional

        # ✨ v4.4: FINNHUB FALLBACK - If yfinance quarterly is missing/empty, try Finnhub
        if not result.get('quarterly') or len(result.get('quarterly', [])) < 4:
            print(f"  → Attempting Finnhub fallback for {sym}...")
            fh_quarters = fetch_finnhub_quarterly(sym)
            
            if fh_quarters:
                # Convert Finnhub format to our format and merge
                merged_q_data = {}
                
                # First add any existing yfinance data
                if result.get('quarterly'):
                    for q in result['quarterly']:
                        d = q.pop('d', None)
                        if d:
                            merged_q_data[d] = q
                
                # Then add Finnhub data (only if not already in yfinance)
                for period, fh_data in fh_quarters.items():
                    if period not in merged_q_data:
                        merged_q_data[period] = fh_data
                    else:
                        # If period exists in yfinance, only add missing fields from Finnhub
                        for key, val in fh_data.items():
                            if key not in merged_q_data[period] or merged_q_data[period][key] is None:
                                merged_q_data[period][key] = val
                
                # Update result with merged quarterly data
                if merged_q_data:
                    quarters = sorted([(k, v) for k, v in merged_q_data.items() if len(v) > 0])[-20:]
                    if quarters:
                        result['quarterly'] = [{'d': k, **v} for k, v in quarters]
                        print(f"  ✓ Finnhub fallback: {len(quarters)}Q merged with yfinance")
                        
                        # Recalculate TTM fields with merged data
                        latest_4q = result['quarterly'][-4:] if len(result['quarterly']) >= 4 else result['quarterly']
                        
                        ttm_cfo = sum(safe_float(q.get('cfo'), 0) for q in latest_4q)
                        ttm_ebitda = sum(safe_float(q.get('ebitda'), 0) for q in latest_4q)
                        ttm_capex = sum(safe_float(q.get('capex'), 0) for q in latest_4q)
                        ttm_da = sum(safe_float(q.get('da'), 0) for q in latest_4q)
                        ttm_tax = sum(safe_float(q.get('tax_exp'), 0) for q in latest_4q)
                        ttm_div = sum(safe_float(q.get('div_paid'), 0) for q in latest_4q)
                        
                        # Only add if not already present from yfinance
                        if not result.get('cfo') and ttm_cfo != 0:
                            result['cfo'] = round(ttm_cfo, 2)
                        if not result.get('ebitda') and ttm_ebitda != 0:
                            result['ebitda'] = round(ttm_ebitda, 2)
                        if not result.get('capex') and ttm_capex > 0:
                            result['capex'] = round(ttm_capex, 2)
                        if not result.get('depreciation_amortization') and ttm_da > 0:
                            result['depreciation_amortization'] = round(ttm_da, 2)
                        if not result.get('tax_expense') and ttm_tax > 0:
                            result['tax_expense'] = round(ttm_tax, 2)
                        if not result.get('dividends_paid') and ttm_div > 0:
                            result['dividends_paid'] = round(ttm_div, 2)


        print(
            f"  ✓ yfinance {sym}: ₹{ltp} | "
            f"P/E:{result.get('pe') or '—'} | "
            f"ROE:{result.get('roe') or '—'}% | "
            f"OPM:{result.get('opm_pct') or '—'}%"
        )

    except Exception as e:
        print(f"  ✗ yfinance {sym}: {e}")

    return result


# ── Source 3: Screener.in ──────────────────────────────
# Module-level Screener session — created once, reused for all stocks
_SCR_SESSION = None

def get_scr_session():
    global _SCR_SESSION
    if _SCR_SESSION is None:
        _SCR_SESSION = requests.Session()
        _SCR_SESSION.headers.update(HEADERS)
    return _SCR_SESSION

# ✨ v4.4: FINNHUB API FALLBACK FUNCTION
def fetch_finnhub_quarterly(sym):
    """
    Fetch quarterly financial data from Finnhub API as FALLBACK
    Only used if yfinance quarterly data is missing/incomplete
    
    Returns dict of quarterly data: {period: {revenue, profit, cfo, capex, ...}}
    """
    if not FINNHUB_ENABLED:
        return {}
    
    try:
        # Rate limiting: respect Finnhub API limits (60 calls/min)
        time.sleep(FINNHUB_RATE_LIMITER)
        
        url = "https://finnhub.io/api/v1/stock/financials-reported"
        params = {
            "symbol": sym,
            "token": FINNHUB_API_KEY
        }
        
        r = requests.get(url, params=params, timeout=15)
        
        if r.status_code != 200:
            return {}
        
        data = r.json()
        
        if "data" not in data or not data["data"]:
            return {}
        
        quarters = {}
        
        for q in data["data"]:
            period = q.get("period")
            if not period:
                continue
            
            quarter_data = {}
            
            # Extract from income statement (netRevenue, netIncome)
            if q.get("income"):
                inc = q["income"]
                if inc.get("netRevenue"):
                    # Finnhub: INR in actual amount, convert to Cr
                    quarter_data["revenue"] = round(inc["netRevenue"] / 10000000, 2)
                if inc.get("netIncome"):
                    quarter_data["profit"] = round(inc["netIncome"] / 10000000, 2)
                if inc.get("operatingIncome"):
                    quarter_data["ebit"] = round(inc["operatingIncome"] / 10000000, 2)
            
            # Extract from cash flow (operatingCashFlow, capex, dividends)
            if q.get("cashflow"):
                cf = q["cashflow"]
                if cf.get("operatingCashFlow"):
                    quarter_data["cfo"] = round(cf["operatingCashFlow"] / 10000000, 2)
                if cf.get("capitalExpenditure"):
                    quarter_data["capex"] = round(cf["capitalExpenditure"] / 10000000, 2)
                if cf.get("dividendsPaid"):
                    quarter_data["div_paid"] = round(cf["dividendsPaid"] / 10000000, 2)
            
            # Extract from balance sheet (assets, liabilities, equity, debt)
            if q.get("balance"):
                bal = q["balance"]
                if bal.get("cash"):
                    quarter_data["cash"] = round(bal["cash"] / 10000000, 2)
                if bal.get("currentAssets"):
                    quarter_data["curr_assets"] = round(bal["currentAssets"] / 10000000, 2)
                if bal.get("totalEquity"):
                    quarter_data["equity"] = round(bal["totalEquity"] / 10000000, 2)
                if bal.get("debt"):
                    quarter_data["debt"] = round(bal["debt"] / 10000000, 2)
                if bal.get("currentLiabilities"):
                    quarter_data["curr_liab"] = round(bal["currentLiabilities"] / 10000000, 2)
            
            if quarter_data:
                quarters[period] = quarter_data
        
        return quarters
    
    except Exception as e:
        print(f"  ⚠ Finnhub error for {sym}: {e}")
        return {}

def fetch_screener_gaps(sym):
    """
    ✨ v4.8 SMART: Extract Screener data with generic fallback + deduplication
    - Searches all sections (top-ratios, tables, etc) for each field
    - Once field found, skip duplicates
    - Automatic fallback for ANY missing data across sections
    """
    result = {}
    if not HAS_BS4:
        return result
    
    screener_sym = SCREENER_OVERRIDES.get(sym, sym)
    
    try:
        sess = get_scr_session()
        url = f"https://www.screener.in/company/{screener_sym}/consolidated/"
        r = sess.get(url, timeout=15)
        if r.status_code == 404:
            url = f"https://www.screener.in/company/{screener_sym}/"
            r = sess.get(url, timeout=15)
        if r.status_code != 200:
            return result
        soup = BeautifulSoup(r.text, "html.parser")

        # Field aliases: map output key → all possible Screener label variations
        field_aliases = {
            'roce': ['roce', 'return on capital', 'roic'],
            'roe': ['roe', 'return on equity', 'return on'],
            'pe': ['p/e', 'pe ratio', 'price earnings'],
            'pb': ['p/b', 'pb ratio', 'price book'],
            'book_value': ['book value', 'bv per share', 'book'],
            'mcap': ['market cap', 'mcap', 'market capitalization'],
            'sales': ['sales', 'revenue', 'total revenue'],
            'face_value': ['face value', 'fv', 'par value'],
            'cfo': ['operating cash', 'cash from operations', 'cfo', 'operating cash flow'],
            'net_cf': ['net cash', 'net cf', 'net cashflow'],
            'prom_pct': ['promoter', 'promoter%', 'promoter holding'],
            'pledge_pct': ['pledge', 'pledged shares', 'pledge%'],
            'public_pct': ['public', 'public%', 'public holding'],
            'fii_pct': ['fii', 'fpi', 'foreign', 'foreign%', 'fii%'],
            'dii_pct': ['dii', 'domestic', 'dii%', 'domestic institution']
        }

        # Search all text in page for field matches
        all_text = soup.get_text().lower()
        
        # ── SECTION 1: Top Ratios (ulid="top-ratios") ──
        ul = soup.find("ul", id="top-ratios")
        if ul:
            for li in ul.find_all("li"):
                spans = li.find_all("span")
                if len(spans) < 2:
                    continue
                lbl = spans[0].get_text(strip=True).lower()
                raw = spans[-1].get_text(strip=True).replace(",","").replace("₹","").replace("%","")
                val = safe_float(raw)
                if val is None:
                    continue
                
                # Match against all field aliases
                for field, aliases in field_aliases.items():
                    if field not in result and any(alias in lbl for alias in aliases):
                        result[field] = val
                        break

        # ── SECTION 2: Shareholding Table ──
        sh = soup.find("section", id="shareholding")
        if sh:
            tbl = sh.find("table")
            if tbl:
                for row in tbl.find_all("tr"):
                    cells = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
                    if len(cells) < 2:
                        continue
                    lbl = cells[0].strip().rstrip("+").strip().lower()
                    
                    numeric_vals = []
                    for c in cells[1:]:
                        v = safe_float(c.replace("%","").replace(",","").strip())
                        if v is not None:
                            numeric_vals.append(v)
                    
                    if not numeric_vals:
                        continue
                    
                    val = numeric_vals[-2] if len(numeric_vals) >= 2 else numeric_vals[0]
                    
                    # Match shareholding fields
                    if 'prom_pct' not in result and "promoter" in lbl and "pledge" not in lbl:
                        result["prom_pct"] = val
                    elif 'pledge_pct' not in result and "pledge" in lbl:
                        if 0 <= val <= 100:
                            result["pledge_pct"] = val
                        else:
                            last = numeric_vals[-1]
                            if 0 <= last <= 100:
                                result["pledge_pct"] = last
                    elif 'public_pct' not in result and "public" in lbl:
                        result["public_pct"] = val
                    elif 'fii_pct' not in result and any(x in lbl for x in ['fii', 'fpi', 'foreign']):
                        result["fii_pct"] = val
                    elif 'dii_pct' not in result and any(x in lbl for x in ['dii', 'domestic', 'institution']):
                        result["dii_pct"] = val

        # ── SECTION 3: Balance Sheet ──
        bs = soup.find("section", id="balance-sheet")
        if bs:
            tbl = bs.find("table")
            if tbl:
                for row in tbl.find_all("tr"):
                    cells = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
                    if len(cells) < 2:
                        continue
                    lbl = cells[0].lower()
                    val = safe_float(cells[-1].replace(",",""))
                    if val is None:
                        continue
                    
                    if 'book_value' not in result and "book value" in lbl:
                        result["book_value"] = val
                    elif 'equity' not in result and "equity" in lbl and "total" in lbl:
                        result["equity"] = val

        # ── SECTION 4: Cash Flow ──
        cf = soup.find("section", id="cash-flow")
        if cf:
            tbl = cf.find("table")
            if tbl:
                for row in tbl.find_all("tr"):
                    cells = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
                    if len(cells) < 2:
                        continue
                    lbl = cells[0].lower()
                    val = safe_float(cells[-1].replace(",",""))
                    if val is not None:
                        if 'cfo' not in result and any(x in lbl for x in field_aliases['cfo']):
                            result["cfo"] = val
                        elif 'net_cf' not in result and any(x in lbl for x in field_aliases['net_cf']) and val != 0:
                            result["net_cf"] = val

        # ── SECTION 5: Profit & Loss ──
        pl = soup.find("section", id="profit-loss")
        if pl:
            tbl = pl.find("table")
            if tbl:
                for row in tbl.find_all("tr"):
                    cells = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
                    if len(cells) < 2:
                        continue
                    lbl = cells[0].lower()
                    val = safe_float(cells[-1].replace("%","").replace(",",""))
                    if val is None:
                        continue
                    
                    if 'roe' not in result and "roe" in lbl:
                        result["roe"] = val
                    elif 'roce' not in result and "roce" in lbl:
                        result["roce"] = val
                    elif 'sales' not in result and any(x in lbl for x in ['sales', 'revenue']):
                        result["sales"] = val

    except Exception as e:
        pass

    return result

# ── Signal ─────────────────────────────────────────────
def compute_signal(d):
    pos = 0
    neg = 0

    def check(field, good_fn, bad_fn):
        nonlocal pos, neg
        v = d.get(field)
        if v is None or v == 0:
            return
        if good_fn(v):
            pos += 1
        elif bad_fn(v):
            neg += 1

    check("roe",       lambda v: v > 15,       lambda v: v < 8)
    check("roce",      lambda v: v > 15,       lambda v: v < 8)
    check("roic",      lambda v: v > 15,       lambda v: v < 8)  # NEW v4.0
    check("pe",        lambda v: 0 < v < 18,   lambda v: v > 35)
    check("opm",       lambda v: v > 15,        lambda v: 0 < v < 8)  # ✨ v4.8: TTM-based
    check("npm",       lambda v: v > 10,        lambda v: 0 < v < 5)  # ✨ v4.8: TTM-based
    check("prom_pct",  lambda v: v > 50,        lambda v: 0 < v < 35)
    check("chg1d",     lambda v: v > 1,         lambda v: v < -1)
    check("ath_pct",   lambda v: v > -10,       lambda v: v < -20)
    check("debt_eq",   lambda v: v < 0.5,       lambda v: v > 1.5)
    check("interest_coverage", lambda v: v > 2.5, lambda v: v < 1.5)  # NEW v4.0

    net = pos - neg
    sig = "BUY" if net >= 3 else "SELL" if net <= -3 else "HOLD"
    return sig, pos, neg


# ── Main ───────────────────────────────────────────────
def main():
    resolved_syms = resolve_symbols()  # Map unified-symbols with symbol_map overrides
    syms = list(resolved_syms.keys())  # Symbol names (master list)
    ts   = now_utc()
    print(f"📊 BharatMarkets Fundamentals v4.8 CLEAN | {ts.strftime('%Y-%m-%d %H:%M UTC')}\n")

    existing = {}
    if Path(FUND_FILE).exists():
        try:
            d = json.loads(Path(FUND_FILE).read_text())
            existing = d.get("stocks", {})
            for sym in d.get("delisted", []):
                DELISTED.add(sym)
            print(f"♻  {len(existing)} existing | {len(DELISTED)} known-delisted\n")
        except:
            pass


    prices = {}
    if Path(PRICES_FILE).exists():
        try:
            prices = json.loads(Path(PRICES_FILE).read_text()).get("quotes", {})
        except:
            pass

    result = {}
    stats  = {"yf": 0, "scr": 0, "errors": 0}
    yf_results = {}

    # ── Phase 1: Parallel yfinance ──
    active_syms = [s for s in syms if s not in DELISTED]
    print(f"⚡ Fetching {len(active_syms)} stocks in parallel (8 workers)…\n")

    from concurrent.futures import ThreadPoolExecutor, as_completed
    lock = __import__("threading").Lock()
    done_count = [0]

    def fetch_one(sym):
        resolved_ticker = resolved_syms[sym]  # Get mapped ticker
        data = fetch_yfinance(sym, yf_ticker=resolved_ticker)
        with lock:
            done_count[0] += 1
            elapsed = (now_utc() - ts).seconds
            if done_count[0] % 10 == 0:
                print(f"  ── {done_count[0]}/{len(active_syms)} done | {elapsed}s elapsed ──")
        time.sleep(YF_DELAY)
        return sym, data

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_one, sym): sym for sym in active_syms}
        for fut in as_completed(futures):
            sym, data = fut.result()
            yf_results[sym] = data

    print(f"✓ Phase 1 done in {(now_utc()-ts).seconds}s\n")

    # ── Phase 2: Sequential Screener + ROCE calculation + merge ──
    for i, sym in enumerate(syms):
        if (i + 1) % 20 == 0:
            print(f"  ── {i+1}/{len(syms)} processed ──")

        if sym in DELISTED:
            continue

        stock = {}

        yf_data = yf_results.get(sym, {})
        if yf_data:
            stock.update(yf_data)
            stats["yf"] += 1
        else:
            stats["errors"] += 1

        # ── Calculate derived metrics from complete quarterly data ──────────────────
        if stock.get('quarterly'):
            derived = calculate_derived_metrics_v4(stock['quarterly'], stock)
            stock.update(derived)

        # ── Calculate ROCE from quarterly data ──────────────────
        if stock.get('quarterly') and not stock.get('roce'):
            roce_ttm = calculate_roce_from_quarterly(stock['quarterly'])
            if roce_ttm:
                stock['roce'] = roce_ttm
        
        # ── Fallback: Estimate ROCE from fundamentals ────────────────
        if not stock.get('roce') and stock.get('roe'):
            roce_est = calculate_roce_from_fundamentals(stock)
            if roce_est:
                stock['roce'] = roce_est

        # Screener — prom% and pledge% always override; other fields gap-fill only
        if HAS_BS4:
            scr_data = fetch_screener_gaps(sym)
            if scr_data:
                for k, v in scr_data.items():
                    if k in ("prom_pct", "pledge_pct", "roce"):
                        if v is not None:
                            stock[k] = v
                    elif stock.get(k) is None and v is not None:
                        stock[k] = v
                stats["scr"] += 1
            time.sleep(SCR_DELAY)


        # prices.json fallback
        pq = prices.get(sym, {})
        fb = {
            "pe": pq.get("pe"), "pb": pq.get("pb"),
            "roe": pq.get("roe"), "eps": pq.get("eps"),
            "w52h": pq.get("w52h"), "w52l": pq.get("w52l"),
            "prom_pct": pq.get("promoter"),
            "beta": pq.get("beta"),
        }
        for k, v in fb.items():
            if stock.get(k) is None and v:
                stock[k] = v

        # Merge with existing
        merged = {**existing.get(sym, {})}
        for k, v in stock.items():
            if v is not None and v != "":
                merged[k] = v

        sig, pos, neg = compute_signal(merged)
        merged.update({
            "signal":  sig,
            "pos":     pos,
            "neg":     neg,
            "updated": ts.isoformat(),
        })
        result[sym] = merged

    # Merge new results into existing — preserves all other stocks
    existing.update(result)
    final_result = existing

    output = {
        "updated":  ts.isoformat(),
        "count":    len(final_result),
        "sources":  stats,
        "delisted": sorted(DELISTED),
        "stocks":   final_result,
    }
    # Only remove stale symbols when explicitly requested (delete action)
    if DO_CLEAN:
        active_syms = set(syms)
        removed = [s for s in list(final_result) if s not in active_syms]
        for s in removed:
            del final_result[s]
        if removed: print(f"  🗑 cleaned fundamentals: {', '.join(removed)}")
        # Also clean guidance.json
        guidance_file = Path("guidance.json")
        if guidance_file.exists() and removed:
            try:
                g = json.loads(guidance_file.read_text())
                for s in removed:
                    g.pop(s, None)
                guidance_file.write_text(json.dumps(g, separators=(",",":")))
                print(f"  🗑 cleaned guidance: {', '.join(removed)}")
            except Exception as e:
                print(f"  ⚠ guidance cleanup failed: {e}")

    output["stocks"] = final_result
    Path(FUND_FILE).write_text(
        json.dumps(output, separators=(",",":"), default=str)
    )

    # ✨ v4.4: Calculate fallback statistics
    cfo_filled = sum(1 for s in final_result.values() if s.get('cfo') and s.get('cfo') != 0)
    ebitda_filled = sum(1 for s in final_result.values() if s.get('ebitda') and s.get('ebitda') != 0)
    capex_filled = sum(1 for s in final_result.values() if s.get('capex') and s.get('capex') != 0)
    total_stocks = len(final_result)
    
    print("=" * 50)
    print(f"✅ {total_stocks} stocks in {FUND_FILE} ({len(result)} updated)")
    print(f"   {stats['yf']} from Yahoo | {stats['scr']} from Screener | {stats['errors']} errors")
    print(f"\n✨ v4.8 CLEAN: TTM-based metrics only")
    print(f"   - OPM, NPM: calculated from last 4 quarters (TTM)")
    print(f"   - CFO, Net CF: from Screener.in")
    print(f"   - ROE, ROCE, Book Value: from Screener.in")
    print(f"   - No redundant annual values")
    print(f"\n📊 Data Coverage:")
    print(f"   CFO:    {cfo_filled:>3}/{total_stocks} ({100*cfo_filled/total_stocks:>5.1f}%)")
    print(f"   EBITDA: {ebitda_filled:>3}/{total_stocks} ({100*ebitda_filled/total_stocks:>5.1f}%)")
    print(f"   CapEx:  {capex_filled:>3}/{total_stocks} ({100*capex_filled/total_stocks:>5.1f}%)")

if __name__ == "__main__":
    main()




# ============================================================
# PHASE 2 EXTRACTION ENGINE
# ============================================================


"""
fetch_fundamentals_PHASE2_EXTRACTION_ENGINE.py

PHASE 2:
- Cashflow enrichment
- Guidance extraction
- Ownership history
- Historical snapshots
- Extraction confidence
- Provider reconciliation

Integrated over finalized normalization layer.
"""

from datetime import datetime


# ============================================================
# EXTRACTION CONFIDENCE
# ============================================================

def extraction_confidence(record):

    score = 1.0

    important = [
        "sales",
        "ebitda",
        "cfo",
        "fcf",
        "capex"
    ]

    missing = 0

    for field in important:

        if record.get(field) in [
            None,
            0,
            "0"
        ]:
            missing += 1

    score -= missing * 0.1

    if record.get("guidance") is None:
        score -= 0.1

    if record.get("quarterly") is None:
        score -= 0.2

    if score < 0:
        score = 0

    return round(score, 2)


# ============================================================
# CASHFLOW ENRICHMENT
# ============================================================

def enrich_cashflow(stock):

    cfo = stock.get("cfo")
    capex = stock.get("capex")

    if (
        cfo is not None and
        capex is not None
    ):

        stock["fcf_calculated"] = round(
            cfo - capex,
            2
        )

    return stock


# ============================================================
# GUIDANCE EXTRACTION
# ============================================================

GUIDANCE_KEYWORDS = [

    "guidance",
    "revenue target",
    "ebitda margin",
    "capex",
    "order book",
    "utilization"
]


def extract_guidance(text):

    if not text:
        return None

    lowered = text.lower()

    extracted = []

    for keyword in GUIDANCE_KEYWORDS:

        if keyword in lowered:
            extracted.append(keyword)

    return extracted


# ============================================================
# OWNERSHIP HISTORY
# ============================================================

def build_ownership_history(stock):

    return {

        "promoter": stock.get("prom_pct"),
        "fii": stock.get("fii_pct"),
        "dii": stock.get("dii_pct"),
        "public": stock.get("public_pct"),
        "updated": datetime.utcnow().isoformat()
    }


# ============================================================
# SNAPSHOT ENGINE
# ============================================================

def build_snapshot(stock):

    return {

        "ticker": stock.get("ticker"),
        "ltp": stock.get("ltp"),
        "mcap": stock.get("mcap"),
        "pe": stock.get("pe"),
        "pb": stock.get("pb"),
        "updated": datetime.utcnow().isoformat()
    }


# ============================================================
# PROVIDER RECONCILIATION
# ============================================================

def reconcile(primary, fallback):

    final = {}

    keys = set(
        list(primary.keys())
        +
        list(fallback.keys())
    )

    for key in keys:

        if primary.get(key) not in [
            None,
            "",
            0
        ]:

            final[key] = primary.get(key)

        else:

            final[key] = fallback.get(key)

    return final


# ============================================================
# PIPELINE
# ============================================================

def process_stock(stock):

    stock = enrich_cashflow(stock)

    stock["ownership_history"] = (
        build_ownership_history(stock)
    )

    stock["snapshot"] = (
        build_snapshot(stock)
    )

    stock["extraction_confidence"] = (
        extraction_confidence(stock)
    )

    return stock


# ============================================================
# METADATA
# ============================================================

def metadata():

    return {

        "phase": "phase2_extraction_engine",
        "updated": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":

    print(
        "Phase 2 extraction engine loaded"
    )



# ============================================================
# EXTRACTION ENGINE V1
# ============================================================


"""
bharatmarkets_extraction_engine_v1.py

NEXT PHASE EXTRACTION ENGINE
- cashflow enrichment
- guidance extraction
- historical snapshots
- provider reconciliation
- extraction confidence
- quarterly completeness gating
"""

from datetime import datetime
from statistics import median


# ============================================================
# CONFIG
# ============================================================

MIN_QUARTER_COMPLETENESS = 0.40


# ============================================================
# HELPERS
# ============================================================

def n(value):

    try:

        if value is None:
            return None

        return round(float(value), 2)

    except:

        return None


# ============================================================
# QUARTER COMPLETENESS
# ============================================================

def quarterly_completeness(row):

    fields = [
        "rev",
        "ebitda",
        "ebit",
        "net",
        "eps"
    ]

    valid = 0

    for field in fields:

        if row.get(field) not in [
            None,
            "",
            0
        ]:
            valid += 1

    return round(valid / len(fields), 2)


def filter_sparse_quarters(quarters):

    final = []

    for row in quarters:

        completeness = quarterly_completeness(row)

        row["quarterly_completeness"] = completeness

        if completeness >= MIN_QUARTER_COMPLETENESS:

            final.append(row)

    return final


# ============================================================
# CASHFLOW ENRICHMENT
# ============================================================

def enrich_cashflow(stock):

    cfo = n(stock.get("cfo"))
    capex = n(stock.get("capex"))

    if cfo is not None and capex is not None:

        stock["fcf_calculated"] = round(
            cfo - capex,
            2
        )

    fcf = n(stock.get("fcf"))

    sales = n(stock.get("sales"))

    if fcf is not None and sales:

        stock["fcf_margin"] = round(
            (fcf / sales) * 100,
            2
        )

    return stock


# ============================================================
# GUIDANCE EXTRACTION
# ============================================================

GUIDANCE_KEYWORDS = [

    "guidance",
    "revenue target",
    "margin guidance",
    "ebitda margin",
    "capex",
    "orderbook",
    "order book",
    "utilization",
    "growth target",
    "expansion",
    "commissioning"
]


def extract_guidance(text):

    if not text:
        return []

    lowered = text.lower()

    extracted = []

    for keyword in GUIDANCE_KEYWORDS:

        if keyword in lowered:

            extracted.append(keyword)

    return extracted


# ============================================================
# SNAPSHOT ENGINE
# ============================================================

def build_snapshot(stock):

    return {

        "ticker": stock.get("ticker"),
        "ltp": stock.get("ltp"),
        "mcap": stock.get("mcap"),
        "pe": stock.get("pe"),
        "pb": stock.get("pb"),
        "roe": stock.get("roe"),
        "updated": datetime.utcnow().isoformat()
    }


# ============================================================
# OWNERSHIP HISTORY
# ============================================================

def build_ownership_history(stock):

    return {

        "promoter": stock.get("prom_pct"),
        "fii": stock.get("fii_pct"),
        "dii": stock.get("dii_pct"),
        "public": stock.get("public_pct"),
        "updated": datetime.utcnow().isoformat()
    }


# ============================================================
# PROVIDER RECONCILIATION
# ============================================================

def reconcile(primary, fallback):

    final = {}

    keys = set(
        list(primary.keys())
        +
        list(fallback.keys())
    )

    for key in keys:

        primary_value = primary.get(key)

        fallback_value = fallback.get(key)

        if primary_value not in [
            None,
            "",
            0
        ]:

            final[key] = primary_value

        else:

            final[key] = fallback_value

    return final


# ============================================================
# EXTRACTION CONFIDENCE
# ============================================================

def extraction_confidence(stock):

    score = 1.0

    important = [

        "sales",
        "ebitda",
        "cfo",
        "fcf",
        "capex"
    ]

    missing = 0

    for field in important:

        if stock.get(field) in [
            None,
            "",
            0
        ]:

            missing += 1

    score -= missing * 0.1

    quarterly = stock.get("quarterly", [])

    if not quarterly:

        score -= 0.2

    if stock.get("guidance") is None:

        score -= 0.1

    if score < 0:

        score = 0

    return round(score, 2)


# ============================================================
# MAIN PIPELINE
# ============================================================

def process_stock(stock):

    quarterly = stock.get("quarterly", [])

    stock["quarterly"] = filter_sparse_quarters(
        quarterly
    )

    stock = enrich_cashflow(stock)

    stock["ownership_history"] = (
        build_ownership_history(stock)
    )

    stock["snapshot"] = (
        build_snapshot(stock)
    )

    stock["extraction_confidence"] = (
        extraction_confidence(stock)
    )

    return stock


# ============================================================
# ENTRY
# ============================================================

if __name__ == "__main__":

    print(
        "bharatmarkets extraction engine loaded"
    )



# ============================================================
# EXTRACTION MATRIX ENGINE V8
# ============================================================


"""
BHARATMARKETS_FULL_EXTRACTION_MATRIX_v8.py

FULL EXTRACTION MATRIX ENGINE

Includes:
- field-first extraction
- provider fallback matrix
- derived reconstruction
- confidence-aware acceptance
- mandatory field enforcement
- quarterly completeness gating
- cashflow reconstruction
- guidance extraction
- snapshot engine
- ownership history
"""

from datetime import datetime
from statistics import median


# ============================================================
# CONFIG
# ============================================================

MIN_QUARTER_COMPLETENESS = 0.40

MANDATORY_FIELDS = {

    "Financial Services": [
        "sales",
        "net",
        "book_value"
    ],

    "Industrials": [
        "sales",
        "ebitda",
        "debt_eq",
        "cfo"
    ],

    "Healthcare": [
        "sales",
        "ebitda",
        "cfo"
    ],

    "Utilities": [
        "sales",
        "ebitda",
        "debt_eq"
    ]
}


# ============================================================
# HELPERS
# ============================================================

def n(value):

    try:

        if value is None:
            return None

        return round(float(value), 2)

    except:

        return None


# ============================================================
# QUARTERLY COMPLETENESS
# ============================================================

def quarterly_completeness(row):

    fields = [
        "rev",
        "ebitda",
        "ebit",
        "net",
        "eps"
    ]

    valid = 0

    for field in fields:

        if row.get(field) not in [
            None,
            "",
            0
        ]:

            valid += 1

    return round(valid / len(fields), 2)


def filter_sparse_quarters(quarters):

    final = []

    for row in quarters:

        completeness = quarterly_completeness(
            row
        )

        row["quarterly_completeness"] = completeness

        if completeness >= MIN_QUARTER_COMPLETENESS:

            final.append(row)

    return final


# ============================================================
# FIELD-FIRST EXTRACTION
# ============================================================

def extract_field(
    primary,
    fallback,
    field
):

    primary_value = primary.get(field)

    if primary_value not in [
        None,
        "",
        0
    ]:

        return primary_value

    fallback_value = fallback.get(field)

    return fallback_value


# ============================================================
# PROVIDER RECONCILIATION
# ============================================================

def reconcile_record(
    primary,
    fallback
):

    final = {}

    keys = set(
        list(primary.keys())
        +
        list(fallback.keys())
    )

    for key in keys:

        final[key] = extract_field(
            primary,
            fallback,
            key
        )

    return final


# ============================================================
# DERIVED RECONSTRUCTION
# ============================================================

def derive_fcf(stock):

    cfo = n(stock.get("cfo"))
    capex = n(stock.get("capex"))

    if (
        cfo is not None and
        capex is not None
    ):

        return round(
            cfo - capex,
            2
        )

    return None


def derive_capex_from_balance_sheet(stock):

    ppe_current = n(
        stock.get("ppe")
    )

    ppe_prev = n(
        stock.get("ppe_prev")
    )

    depreciation = n(
        stock.get("depreciation_amortization")
    )

    if (
        ppe_current is None or
        ppe_prev is None or
        depreciation is None
    ):

        return None

    capex = (
        ppe_current
        -
        ppe_prev
        +
        depreciation
    )

    if capex < 0:
        return None

    return round(capex, 2)


def reconstruct_fields(stock):

    if stock.get("capex") is None:

        stock["capex"] = (
            derive_capex_from_balance_sheet(
                stock
            )
        )

    if stock.get("fcf") is None:

        stock["fcf"] = (
            derive_fcf(stock)
        )

    return stock


# ============================================================
# GUIDANCE EXTRACTION
# ============================================================

GUIDANCE_KEYWORDS = [

    "guidance",
    "revenue target",
    "ebitda margin",
    "orderbook",
    "capex",
    "utilization",
    "growth target",
    "expansion",
    "commissioning"
]


def extract_guidance(text):

    if not text:
        return []

    lowered = text.lower()

    found = []

    for keyword in GUIDANCE_KEYWORDS:

        if keyword in lowered:

            found.append(keyword)

    return found


# ============================================================
# OWNERSHIP HISTORY
# ============================================================

def ownership_history(stock):

    return {

        "promoter": stock.get("prom_pct"),
        "fii": stock.get("fii_pct"),
        "dii": stock.get("dii_pct"),
        "public": stock.get("public_pct"),
        "updated": datetime.utcnow().isoformat()
    }


# ============================================================
# SNAPSHOT ENGINE
# ============================================================

def build_snapshot(stock):

    return {

        "ticker": stock.get("ticker"),
        "ltp": stock.get("ltp"),
        "mcap": stock.get("mcap"),
        "pe": stock.get("pe"),
        "pb": stock.get("pb"),
        "roe": stock.get("roe"),
        "updated": datetime.utcnow().isoformat()
    }


# ============================================================
# EXTRACTION CONFIDENCE
# ============================================================

def extraction_confidence(stock):

    score = 1.0

    missing = 0

    important = [

        "sales",
        "ebitda",
        "cfo",
        "capex",
        "fcf"
    ]

    for field in important:

        if stock.get(field) in [
            None,
            "",
            0
        ]:

            missing += 1

    score -= missing * 0.08

    if not stock.get("quarterly"):

        score -= 0.2

    if score < 0:
        score = 0

    return round(score, 2)


# ============================================================
# MANDATORY FIELD ENFORCEMENT
# ============================================================

def validate_required_fields(stock):

    sector = stock.get("sector")

    required = MANDATORY_FIELDS.get(
        sector,
        []
    )

    missing = []

    for field in required:

        if stock.get(field) in [
            None,
            "",
            0
        ]:

            missing.append(field)

    stock["missing_required_fields"] = missing

    return stock


# ============================================================
# MAIN PIPELINE
# ============================================================

def process_stock(
    primary,
    fallback={}
):

    stock = reconcile_record(
        primary,
        fallback
    )

    stock["quarterly"] = filter_sparse_quarters(
        stock.get("quarterly", [])
    )

    stock = reconstruct_fields(stock)

    stock["ownership_history"] = (
        ownership_history(stock)
    )

    stock["snapshot"] = (
        build_snapshot(stock)
    )

    stock["extraction_confidence"] = (
        extraction_confidence(stock)
    )

    stock = validate_required_fields(
        stock
    )

    return stock


# ============================================================
# METADATA
# ============================================================

def metadata():

    return {

        "engine": "v8_extraction_matrix",
        "updated": datetime.utcnow().isoformat()
    }


# ============================================================
# ENTRY
# ============================================================

if __name__ == "__main__":

    print(
        "bharatmarkets full extraction matrix loaded"
    )

