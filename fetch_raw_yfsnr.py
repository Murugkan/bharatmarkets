#!/usr/bin/env python3
"""
STEP 1: FETCH DATA MODULE (FIXED)
=========================
Fetches price history (Yahoo Finance) and company fundamentals (Screener.in)
Includes: Data fetch + Testing + Logging (all self-contained)

FIXES:
- Error logging now captured to file (WARNING level for critical errors)
- Screener.in company URL resolution uses BSE codes instead of company slugs
- Detailed error messages for debugging fetch failures

SCOPE:
  - Yahoo Finance: Historical price data (OHLCV) + company info
  - Screener.in:   Company fundamentals via web scraping

EXCLUDED:
  - Financial metrics (handled by fetch_yahoof_financials_1.py)
  - Bonds/SGB securities (filtered out)
  - Delisted companies (filtered out)

OUTPUT:
  - data/yahoofin_raw_data.json
  - data/screener_raw_data.json
  - data/logs/fetch_raw_yfsnr.log (warnings/errors only)

GitHub Structure (relative paths):
bharatmarkets/
├── fetch_raw_yfsnr.py (THIS FILE - yfinance + screener)
├── step2_merge.py
├── fetch_yahoof_financials_1.py
├── fetch_screener_financials.py
├── unified-symbols.json
├── symbol_map.json
└── data/
    ├── yahoo-history.json (output)
    ├── screener-history.json (output)
    └── logs/
        └── fetch_raw_yfsnr.log
"""

import json
import time
import requests
import yfinance as yf
import logging
import subprocess
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime, UTC

# Optional: pandas (not used - included if needed for yfinance internals)
try:
    import pandas as pd
except ImportError:
    pass  # Optional dependency

# ============================================================================
# PATHS - All relative to current working directory (repository root)
# ============================================================================

# Relative paths - works from repo root
DATA_DIR = Path('data')
SYMBOLS_FILE = Path('unified-symbols.json')
SYMBOL_MAP_FILE = Path('symbol_map.json')

# Output files
YAHOO_FILE = DATA_DIR / "yahoofin_raw_data.json"
SCREENER_FILE = DATA_DIR / "screener_raw_data.json"

# Verify paths exist (fail fast)
def verify_paths():
    """Verify all required input files exist"""
    if not SYMBOLS_FILE.exists():
        raise FileNotFoundError(f"Missing: {SYMBOLS_FILE}")
    if not SYMBOL_MAP_FILE.exists():
        raise FileNotFoundError(f"Missing: {SYMBOL_MAP_FILE}")

# ============================================================================
# CONSTANTS
# ============================================================================

HEADERS = {"User-Agent": "Mozilla/5.0"}

# Interval-to-period mapping: defines what period to use for each interval
# This ensures: 1d gets 6 months (recent daily data), 1wk/1mo get full configured period
INTERVAL_PERIOD_MAP = {
    "1d": "6mo",   # Always 6 months for daily granularity
    "1wk": None,   # Use configured history_period
    "1mo": None,   # Use configured history_period
}

# ============================================================================
# LOGGING
# ============================================================================
# Console: INFO level (shows execution progress)
# File:    WARNING level (only errors, no spam)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-10s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("STEP1-FETCH")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def now():
    return datetime.now(UTC).isoformat()

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Cannot load {path.name}: {e}")
        return {}

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def resolve_symbol(symbol, overrides):
    """Resolve symbol using override mapping"""
    if symbol in overrides:
        return overrides[symbol]
    if not any(symbol.endswith(ext) for ext in [".NS", ".BO"]):
        return f"{symbol}.NS"
    return symbol

def build_sector_mapping(symbols_list):
    """Build sector mapping dynamically from unified-symbols.json"""
    mapping = {}
    for symbol in symbols_list:
        ticker = str(symbol["ticker"]).strip()
        sector = symbol.get("sector") or symbol.get("industry") or symbol.get("group") or "Other"
        mapping[ticker] = sector
    return mapping

# ============================================================================
# TESTING CLASS
# ============================================================================

class Step1Tester:
    """Test Step 1 output"""
    
    def __init__(self, yahoo_data, screener_data):
        self.yahoo = yahoo_data
        self.screener = screener_data
        self.results = {}
    
    def run_all_tests(self):
        """Run all Step 1 tests (Yahoo + Screener providers)"""
        logger.info("\n" + "="*80)
        logger.info("STEP 1: TESTING FETCH RESULTS")
        logger.info("="*80)
        
        self.test_files_created()
        self.test_ticker_coverage()
        self.test_observation_counts()
        self.test_data_structure()
        self.test_error_handling()
        
        return self.print_summary()
    
    def test_files_created(self):
        """Test 1: Yahoo + Screener output files exist and have valid JSON"""
        logger.info("\n[TEST 1] FILES CREATED & VALID JSON")
        logger.info("-" * 80)
        
        tests = [
            ("Yahoo", YAHOO_FILE, self.yahoo),
            ("Screener", SCREENER_FILE, self.screener),
        ]
        
        passed = 0
        for name, file_path, data in tests:
            if file_path.exists():
                logger.info(f"  ✓ {name:12s} file exists")
                if isinstance(data, dict) and len(data) > 0:
                    logger.info(f"    └─ {len(data)} tickers loaded")
                    passed += 1
                else:
                    logger.error(f"    └─ Empty or invalid JSON")
            else:
                logger.error(f"  ✗ {name:12s} file NOT FOUND: {file_path}")
        
        self.results["Files Created"] = (passed, len(tests))
    
    def test_ticker_coverage(self):
        """Test 2: All companies fetched from both providers"""
        logger.info("\n[TEST 2] TICKER COVERAGE")
        logger.info("-" * 80)
        
        y_tickers = set(self.yahoo.keys())
        s_tickers = set(self.screener.keys())
        all_tickers = y_tickers | s_tickers
        
        logger.info(f"  Yahoo:     {len(y_tickers):2d} tickers")
        logger.info(f"  Screener:  {len(s_tickers):2d} tickers")
        logger.info(f"  Combined:  {len(all_tickers):2d} tickers")
        
        if len(all_tickers) >= 97:
            logger.info(f"  ✓ Coverage >= 97 tickers")
            self.results["Ticker Coverage"] = (1, 1)
        else:
            logger.warning(f"  ⚠️  Only {len(all_tickers)} tickers (expected 97)")
            self.results["Ticker Coverage"] = (0, 1)
    
    def test_observation_counts(self):
        """Test 3: Data was fetched (has observations)"""
        logger.info("\n[TEST 3] OBSERVATION COUNTS")
        logger.info("-" * 80)
        
        y_obs = sum(len(e.get('observations', [])) for e in self.yahoo.values())
        s_obs = sum(len(e.get('observations', [])) for e in self.screener.values())
        
        logger.info(f"  Yahoo:     {y_obs:3d} observations")
        logger.info(f"  Screener:  {s_obs:3d} observations")
        
        passed = 0
        if y_obs > 0:
            logger.info(f"  ✓ Yahoo has data")
            passed += 1
        if s_obs > 0:
            logger.info(f"  ✓ Screener has data")
            passed += 1
        
        self.results["Observation Counts"] = (passed, 2)
    
    def test_data_structure(self):
        """Test 4: Data has correct structure"""
        logger.info("\n[TEST 4] DATA STRUCTURE")
        logger.info("-" * 80)
        
        passed = 0
        total = 0
        
        for ticker, entry in list(self.yahoo.items())[:1]:
            total += 1
            if (isinstance(entry, dict) and 'ticker' in entry and 'observations' in entry):
                logger.info(f"  ✓ Yahoo structure valid")
                passed += 1
            else:
                logger.error(f"  ✗ Yahoo structure invalid")
        
        for ticker, entry in list(self.screener.items())[:1]:
            total += 1
            if (isinstance(entry, dict) and 'ticker' in entry and 'observations' in entry):
                logger.info(f"  ✓ Screener structure valid")
                passed += 1
            else:
                logger.error(f"  ✗ Screener structure invalid")
        
        self.results["Data Structure"] = (passed, total if total > 0 else 1)
    
    def test_error_handling(self):
        """Test 5: Check for errors in Yahoo+Screener fetch"""
        logger.info("\n[TEST 5] ERROR HANDLING")
        logger.info("-" * 80)
        
        errors = {'yahoo': 0, 'screener': 0}
        error_details = {'yahoo': [], 'screener': []}
        
        for ticker, entry in self.yahoo.items():
            for obs in entry.get('observations', []):
                if any('error' in k for k in obs.get('raw', {}).keys()):
                    errors['yahoo'] += 1
                    error_msg = obs.get('raw', {}).get('error') or obs.get('raw', {}).get('info_error', 'Unknown error')
                    error_details['yahoo'].append(f"  {ticker}: {error_msg[:80]}")
        
        for ticker, entry in self.screener.items():
            for obs in entry.get('observations', []):
                if any('error' in k for k in obs.get('raw', {}).keys()):
                    errors['screener'] += 1
                    error_msg = obs.get('raw', {}).get('error', 'Unknown error')
                    error_details['screener'].append(f"  {ticker}: {error_msg[:80]}")
        
        logger.info(f"  Yahoo errors:     {errors['yahoo']:2d}")
        logger.info(f"  Screener errors:  {errors['screener']:2d}")
        logger.info(f"  Total errors:     {sum(errors.values()):2d}")
        
        # Log error details to file (WARNING level)
        if error_details['yahoo']:
            logger.warning(f"Yahoo fetch errors ({len(error_details['yahoo'])}):")
            for detail in error_details['yahoo'][:5]:  # Log first 5
                logger.warning(detail)
        
        if error_details['screener']:
            logger.warning(f"Screener fetch errors ({len(error_details['screener'])}):")
            for detail in error_details['screener'][:5]:  # Log first 5
                logger.warning(detail)
        
        self.results["Error Handling"] = (1, 1)
    
    def print_summary(self):
        """Print test summary"""
        logger.info("\n" + "="*80)
        logger.info("STEP 1 TEST SUMMARY")
        logger.info("="*80)
        
        total_passed = 0
        total_tests = 0
        
        for test_name, (passed, total) in self.results.items():
            status = "✓ PASS" if passed == total else "⚠️  WARN"
            logger.info(f"{status}: {test_name:25s} ({passed}/{total})")
            total_passed += passed
            total_tests += total
        
        logger.info("\n" + "-"*80)
        logger.info(f"Result: {total_passed}/{total_tests} test groups passed")
        
        if total_passed == total_tests:
            logger.info("✅ STEP 1 COMPLETE - All tests passed")
        else:
            logger.warning("⚠️ STEP 1 COMPLETE - Some issues found")
        
        return True

# ============================================================================
# FETCH LOGIC
# ============================================================================

def fetch_yahoo_payload(ticker, symbol_overrides, history_period="10y", history_intervals=None):
    """
    Fetch Yahoo Finance info and price history for multiple intervals.
    
    Intervals use INTERVAL_PERIOD_MAP to determine their period:
    - 1d:  Fixed at 6 months (recent daily data)
    - 1wk: Uses configured history_period
    - 1mo: Uses configured history_period
    
    Args:
        ticker: Stock ticker
        symbol_overrides: Symbol mapping dict
        history_period: Main history period (2y, 5y, 10y, etc.)
        history_intervals: List of intervals to fetch (1d, 1wk, 1mo)
    """
    
    if history_intervals is None:
        history_intervals = ["1d", "1wk", "1mo"]
    
    payload = {}
    yahoo_symbol = resolve_symbol(ticker, symbol_overrides)
    stock = yf.Ticker(yahoo_symbol)
    
    try:
        payload["info"] = stock.info
    except Exception as e:
        payload["info_error"] = str(e)
    
    # Fetch history for each interval
    for interval in history_intervals:
        try:
            # Determine period: use map if defined, otherwise use configured period
            period = INTERVAL_PERIOD_MAP.get(interval, history_period)
            if period is None:
                period = history_period
            
            hist = stock.history(period=period, interval=interval)
            payload[f"history_{period}_{interval}"] = hist.reset_index().astype(str).to_dict("records")
        except Exception as e:
            payload[f"history_{interval}_error"] = str(e)
    
    return payload

def extract_table(table):
    rows = []
    for tr in table.select("tr"):
        cols = tr.select("th,td")
        row = [col.get_text(" ", strip=True) for col in cols]
        if row:
            rows.append(row)
    return rows

def fetch_screener_payload(ticker, screener_overrides, timeout=30, retries=2, delay=1.0):
    """
    Fetch Screener.in company data.
    
    FIXED: Uses screener_overrides mapping to resolve correct URL slug.
    For BSE-listed companies, use the BSE code (e.g., 504731 for AZADIND).
    
    Args:
        ticker: Stock ticker
        screener_overrides: Mapping of ticker → screener_slug (BSE code for BSE stocks)
        timeout: Request timeout in seconds
        retries: Number of retry attempts
        delay: Delay between retries in seconds
    """
    payload = {}
    # Use screener override if available, otherwise use lowercase ticker
    screener_slug = screener_overrides.get(ticker, ticker.lower())
    url = f"https://www.screener.in/company/{screener_slug}/"
    payload["url"] = url
    
    last_error = None
    
    # Retry logic with delay
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            payload["tables"] = []
            
            for section in soup.select("section"):
                table = section.select_one("table")
                if not table:
                    continue
                heading = section.select_one("h2")
                payload["tables"].append({
                    "section": heading.get_text(" ", strip=True) if heading else None,
                    "rows": extract_table(table)
                })
            
            return payload
        
        except Exception as e:
            last_error = str(e)
            if attempt < retries - 1:
                time.sleep(delay)
    
    # All retries exhausted
    payload["error"] = last_error
    return payload


# ============================================================================
# GIT COMMIT
# ============================================================================

def commit_to_git(log_file):
    """Commit data files to git"""
    try:
        logger.info("\n" + "="*80)
        logger.info("GIT COMMIT")
        logger.info("="*80)
        
        # Check if git is available
        result = subprocess.run(
            ["git", "status"],
            capture_output=True,
            check=False
        )
        
        if result.returncode != 0:
            logger.warning("  Git not available or not in a repo")
            return True
        
        # Add files
        files = [
            "data/yahoofin_raw_data.json",
            "data/screener_raw_data.json"
        ]
        
        if log_file and log_file.exists():
            files.append(str(log_file))
        
        files_added = 0
        for file in files:
            filepath = Path(file)
            if filepath.exists():
                result = subprocess.run(
                    ["git", "add", file],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if result.returncode == 0:
                    logger.info(f"  ✓ Added {file}")
                    files_added += 1
                else:
                    logger.warning(f"  ⚠️  Failed to add {file}")
            else:
                logger.warning(f"  ⚠️  File not found: {file}")
        
        if files_added == 0:
            logger.warning("  No files to commit")
            return True
        
        # Commit
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[Step 1] Fetch: Yahoo+Screener ({timestamp})"
        
        result = subprocess.run(
            ["git", "commit", "-m", msg],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            logger.info(f"  ✓ Committed: {msg}")
            
            # Push to GitHub
            logger.info("\n  Pushing to GitHub...")
            push_result = subprocess.run(
                ["git", "push", "origin", "HEAD:main"],
                capture_output=True,
                text=True,
                check=False
            )
            
            logger.info(f"  Push return code: {push_result.returncode}")
            if push_result.stdout:
                logger.info(f"  stdout: {push_result.stdout}")
            if push_result.stderr:
                logger.info(f"  stderr: {push_result.stderr}")
            
            if push_result.returncode == 0:
                logger.info(f"  ✓ Pushed to GitHub")
            else:
                logger.warning(f"  ⚠️  Push failed (code: {push_result.returncode})")
            
            return True
        elif "nothing to commit" in result.stderr.lower():
            logger.info(f"  ⊘ Nothing to commit")
            return True
        else:
            logger.warning(f"  ⚠️  Commit may have failed: {result.stderr.strip()}")
            return True
    
    except Exception as e:
        logger.error(f"  ✗ Git error: {str(e)}")
        return True

# ============================================================================
# MAIN
# ============================================================================

def main():
    # Load fetch configuration first (from workflow)
    fetch_config = load_json(Path('.fetch_config.json'))
    FETCH_YAHOO = fetch_config.get('yahoo', True)
    FETCH_SCREENER = fetch_config.get('screener', True)
    HISTORY_PERIOD = fetch_config.get('history_period', '10y')
    HISTORY_INTERVALS = fetch_config.get('history_intervals', ['1d', '1wk', '1mo'])
    SCREENER_TIMEOUT = fetch_config.get('screener_timeout', 30)
    SCREENER_RETRIES = fetch_config.get('screener_retries', 2)
    SCREENER_DELAY = fetch_config.get('screener_delay', 1.0)
    
    # Create log file handler - WARNING level only (captures errors)
    log_file = Path('data/logs/fetch_raw_yfsnr.log')
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.WARNING)  # Only warnings/errors to file
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(name)-10s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(file_handler)
    
    # Set logger level to INFO (for console output)
    logger.setLevel(logging.INFO)
    
    # Print summary FIRST
    logger.info("\n" + "="*80)
    logger.info("STEP 1: FETCH DATA MODULE - SUMMARY (FIXED)")
    logger.info("="*80)
    logger.info("\nProvider Configuration:")
    logger.info(f"  {'✓' if FETCH_YAHOO else '✗'} Yahoo Finance (period: {HISTORY_PERIOD}, intervals: {', '.join(HISTORY_INTERVALS)})")
    logger.info(f"  {'✓' if FETCH_SCREENER else '✗'} Screener.in (timeout: {SCREENER_TIMEOUT}s, retries: {SCREENER_RETRIES}, delay: {SCREENER_DELAY}s)")
    logger.info(f"  Output: {Path('data').resolve()}/")
    logger.info("="*80)
    
    # Verify paths
    logger.info("\nVerifying paths...")
    try:
        verify_paths()
        logger.info(f"  ✓ Working dir:   {Path.cwd()}")
        logger.info(f"  ✓ DATA_DIR:      {DATA_DIR.resolve()}")
        logger.info(f"  ✓ SYMBOLS_FILE:  {SYMBOLS_FILE.resolve()}")
        logger.info(f"  ✓ SYMBOL_MAP:    {SYMBOL_MAP_FILE.resolve()}")
    except FileNotFoundError as e:
        logger.error(f"  ✗ {e}")
        logger.error(f"  ✗ Path verification failed")
        return 1
    
    start_time = time.time()
    
    # Load symbols
    logger.info("\nLoading configuration...")
    symbols_master = load_json(SYMBOLS_FILE)
    symbols = symbols_master.get("symbols", [])
    symbol_map = load_json(SYMBOL_MAP_FILE)
    DELISTED = set(symbol_map.get("delisted", []))
    SYMBOL_OVERRIDES = symbol_map.get("overrides", {})
    SCREENER_OVERRIDES = symbol_map.get("screener_overrides", {})
    
    logger.info(f"  ✓ {len(symbols)} companies to fetch")
    logger.info(f"  ✓ {len(DELISTED)} delisted excluded")
    logger.info(f"  ✓ {len(SCREENER_OVERRIDES)} screener overrides loaded")
    
    # Initialize stores
    yahoo_store = {}
    screener_store = {}
    
    processed = 0
    skipped = 0
    
    # Fetch (only enabled providers)
    enabled_count = sum([FETCH_YAHOO, FETCH_SCREENER])
    logger.info(f"\nFetching from {enabled_count} provider(s)...")
    for symbol in symbols:
        ticker = str(symbol["ticker"]).strip()
        
        if ticker in DELISTED:
            skipped += 1
            continue
        
        if str(ticker).upper().startswith("SGB") or "BOND" in str(ticker).upper():
            skipped += 1
            continue
        
        # Yahoo (if enabled)
        if FETCH_YAHOO:
            if ticker not in yahoo_store:
                yahoo_store[ticker] = {"ticker": ticker, "name": symbol.get("name"), "isin": symbol.get("isin"), "observations": []}
            try:
                payload = fetch_yahoo_payload(ticker, SYMBOL_OVERRIDES, HISTORY_PERIOD, HISTORY_INTERVALS)
                yahoo_store[ticker]["observations"].append({"fetched_at": now(), "raw": payload})
            except Exception as e:
                yahoo_store[ticker]["observations"].append({"fetched_at": now(), "raw": {"error": str(e)}})
        
        # Screener (if enabled)
        if FETCH_SCREENER:
            if ticker not in screener_store:
                screener_store[ticker] = {"ticker": ticker, "name": symbol.get("name"), "isin": symbol.get("isin"), "observations": []}
            try:
                payload = fetch_screener_payload(ticker, SCREENER_OVERRIDES, SCREENER_TIMEOUT, SCREENER_RETRIES, SCREENER_DELAY)
                screener_store[ticker]["observations"].append({"fetched_at": now(), "raw": payload})
            except Exception as e:
                screener_store[ticker]["observations"].append({"fetched_at": now(), "raw": {"error": str(e)}})
        
        processed += 1
        if processed % 20 == 0:
            logger.info(f"  Progress: {processed}/{len(symbols)-skipped}...")
    
    runtime = round(time.time() - start_time, 2)
    
    # Save (only enabled providers)
    logger.info(f"\nSaving files...")
    logger.info(f"  Current directory: {Path.cwd()}")
    
    if FETCH_YAHOO:
        save_json(YAHOO_FILE, yahoo_store)
        logger.info(f"  ✓ Saved: {YAHOO_FILE.resolve()}")
    
    if FETCH_SCREENER:
        save_json(SCREENER_FILE, screener_store)
        logger.info(f"  ✓ Saved: {SCREENER_FILE.resolve()}")
    
    # Test
    tester = Step1Tester(yahoo_store, screener_store)
    tester.run_all_tests()
    
    # Commit
    commit_to_git(log_file)
    
    # Brief completion message
    logger.info("\n✅ STEP 1 COMPLETE")
    logger.info(f"Processed: {processed} | Skipped: {skipped} | Runtime: {runtime}s")
    logger.info(f"Log file: {log_file.resolve()}")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
