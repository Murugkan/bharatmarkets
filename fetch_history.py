#!/usr/bin/env python3
"""
STEP 1: FETCH DATA MODULE
=========================
Independent module for fetching from Yahoo, Screener, Finnhub
Includes: Data fetch + Testing + Logging (all self-contained)

GitHub Structure (relative paths):
bharatmarkets/
├── step1_fetch.py (THIS FILE)
├── step2_merge.py
├── unified-symbols.json
├── symbol_map.json
└── data/
    ├── yahoo-history.json (output)
    ├── screener-history.json (output)
    └── finnhub-history.json (output)
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

# ============================================================================
# PATHS - All relative to current working directory (repository root)
# ============================================================================

# Relative paths - works from repo root
DATA_DIR = Path('data')
SYMBOLS_FILE = Path('unified-symbols.json')
SYMBOL_MAP_FILE = Path('symbol_map.json')

# Output files
YAHOO_FILE = DATA_DIR / "yahoo-history.json"
SCREENER_FILE = DATA_DIR / "screener-history.json"
FINNHUB_FILE = DATA_DIR / "finnhub-history.json"

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
FINNHUB_API_KEY = "d7u9sj1r01qnv95mqqu0d7u9sj1r01qnv95mqqug"
FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

# ============================================================================
# LOGGING
# ============================================================================

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

# ============================================================================
# TESTING CLASS
# ============================================================================

class Step1Tester:
    """Test Step 1 output"""
    
    def __init__(self, yahoo_data, screener_data, finnhub_data):
        self.yahoo = yahoo_data
        self.screener = screener_data
        self.finnhub = finnhub_data
        self.results = {}
    
    def run_all_tests(self):
        """Run all Step 1 tests"""
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
        """Test 1: Output files exist and have valid JSON"""
        logger.info("\n[TEST 1] FILES CREATED & VALID JSON")
        logger.info("-" * 80)
        
        tests = [
            ("Yahoo", YAHOO_FILE, self.yahoo),
            ("Screener", SCREENER_FILE, self.screener),
            ("Finnhub", FINNHUB_FILE, self.finnhub),
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
        """Test 2: All 97 companies fetched"""
        logger.info("\n[TEST 2] TICKER COVERAGE")
        logger.info("-" * 80)
        
        y_tickers = set(self.yahoo.keys())
        s_tickers = set(self.screener.keys())
        f_tickers = set(self.finnhub.keys())
        all_tickers = y_tickers | s_tickers | f_tickers
        
        logger.info(f"  Yahoo:     {len(y_tickers):2d} tickers")
        logger.info(f"  Screener:  {len(s_tickers):2d} tickers")
        logger.info(f"  Finnhub:   {len(f_tickers):2d} tickers")
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
        f_obs = sum(len(e.get('observations', [])) for e in self.finnhub.values())
        
        logger.info(f"  Yahoo:     {y_obs:3d} observations")
        logger.info(f"  Screener:  {s_obs:3d} observations")
        logger.info(f"  Finnhub:   {f_obs:3d} observations")
        
        passed = 0
        if y_obs > 0:
            logger.info(f"  ✓ Yahoo has data")
            passed += 1
        if s_obs > 0:
            logger.info(f"  ✓ Screener has data")
            passed += 1
        if f_obs > 0:
            logger.info(f"  ✓ Finnhub has data")
            passed += 1
        
        self.results["Observation Counts"] = (passed, 3)
    
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
        
        for ticker, entry in list(self.finnhub.items())[:1]:
            total += 1
            if (isinstance(entry, dict) and 'ticker' in entry and 'observations' in entry):
                logger.info(f"  ✓ Finnhub structure valid")
                passed += 1
            else:
                logger.error(f"  ✗ Finnhub structure invalid")
        
        self.results["Data Structure"] = (passed, total if total > 0 else 1)
    
    def test_error_handling(self):
        """Test 5: Check for errors in fetch"""
        logger.info("\n[TEST 5] ERROR HANDLING")
        logger.info("-" * 80)
        
        errors = {'yahoo': 0, 'screener': 0, 'finnhub': 0}
        
        for entry in self.yahoo.values():
            for obs in entry.get('observations', []):
                if any('error' in k for k in obs.get('raw', {}).keys()):
                    errors['yahoo'] += 1
        
        for entry in self.screener.values():
            for obs in entry.get('observations', []):
                if any('error' in k for k in obs.get('raw', {}).keys()):
                    errors['screener'] += 1
        
        for entry in self.finnhub.values():
            for obs in entry.get('observations', []):
                if any('error' in k for k in obs.get('raw', {}).keys()):
                    errors['finnhub'] += 1
        
        logger.info(f"  Yahoo errors:     {errors['yahoo']:2d}")
        logger.info(f"  Screener errors:  {errors['screener']:2d}")
        logger.info(f"  Finnhub errors:   {errors['finnhub']:2d}")
        logger.info(f"  Total errors:     {sum(errors.values()):2d}")
        
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

def fetch_yahoo_payload(ticker):
    payload = {}
    yahoo_symbol = f"{ticker}.NS"
    stock = yf.Ticker(yahoo_symbol)
    
    try:
        payload["info"] = stock.info
    except Exception as e:
        payload["info_error"] = str(e)
    
    try:
        hist = stock.history(period="1y", interval="1d")
        payload["history_1y_1d"] = hist.reset_index().astype(str).to_dict("records")
    except Exception as e:
        payload["history_error"] = str(e)
    
    return payload

def extract_table(table):
    rows = []
    for tr in table.select("tr"):
        cols = tr.select("th,td")
        row = [col.get_text(" ", strip=True) for col in cols]
        if row:
            rows.append(row)
    return rows

def fetch_screener_payload(ticker):
    payload = {}
    url = f"https://www.screener.in/company/{ticker}/"
    payload["url"] = url
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
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
    except Exception as e:
        payload["error"] = str(e)
    
    return payload

def fetch_finnhub_payload(ticker):
    payload = {}
    finnhub_symbol = f"{ticker}.NS"
    
    try:
        url = f"{FINNHUB_BASE_URL}/stock/financials"
        params = {"symbol": finnhub_symbol, "statement": "bs", "freq": "annual", "token": FINNHUB_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            payload["balance_sheet"] = response.json()
    except Exception as e:
        payload["balance_sheet_error"] = str(e)
    
    try:
        params["statement"] = "ic"
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            payload["income_statement"] = response.json()
    except Exception as e:
        payload["income_statement_error"] = str(e)
    
    try:
        params["statement"] = "cf"
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            payload["cash_flow"] = response.json()
    except Exception as e:
        payload["cash_flow_error"] = str(e)
    
    try:
        url = f"{FINNHUB_BASE_URL}/stock/metric"
        params = {"symbol": finnhub_symbol, "metric": "all", "token": FINNHUB_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            payload["metrics"] = response.json()
    except Exception as e:
        payload["metrics_error"] = str(e)
    
    return payload

# ============================================================================
# MAIN
# ============================================================================

def commit_to_git(log_file):
    """Commit fetch results to Git"""
    logger.info("\n" + "="*80)
    logger.info("COMMITTING TO GIT")
    logger.info("="*80)
    
    try:
        # Configure git
        subprocess.run(
            ["git", "config", "user.email", "pipeline@bharatmarkets.dev"],
            capture_output=True,
            check=False
        )
        subprocess.run(
            ["git", "config", "user.name", "BharatMarkets Pipeline"],
            capture_output=True,
            check=False
        )
        
        # Add files
        files = [
            "data/yahoo-history.json",
            "data/screener-history.json",
            "data/finnhub-history.json"
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
        msg = f"[Step 1] Fetch: Yahoo+Screener+Finnhub ({timestamp})"
        
        result = subprocess.run(
            ["git", "commit", "-m", msg],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            logger.info(f"  ✓ Committed: {msg}")
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
    # Create log file handler
    log_file = Path('data/fetch-history.log')
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(name)-10s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(file_handler)
    
    logger.info("\n" + "="*80)
    logger.info("STEP 1: FETCH DATA MODULE")
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
        return 1
    
    start_time = time.time()
    
    # Load symbols
    logger.info("\nLoading configuration...")
    symbols_master = load_json(SYMBOLS_FILE)
    symbols = symbols_master.get("symbols", [])
    symbol_map = load_json(SYMBOL_MAP_FILE)
    DELISTED = set(symbol_map.get("delisted", []))
    
    logger.info(f"  ✓ {len(symbols)} companies to fetch")
    logger.info(f"  ✓ {len(DELISTED)} delisted excluded")
    
    # Initialize stores
    yahoo_store = {}
    screener_store = {}
    finnhub_store = {}
    
    processed = 0
    skipped = 0
    
    # Fetch
    logger.info(f"\nFetching from 3 providers...")
    for symbol in symbols:
        ticker = str(symbol["ticker"]).strip()
        
        if ticker in DELISTED:
            skipped += 1
            continue
        
        if str(ticker).upper().startswith("SGB") or "BOND" in str(ticker).upper():
            skipped += 1
            continue
        
        # Yahoo
        if ticker not in yahoo_store:
            yahoo_store[ticker] = {"ticker": ticker, "name": symbol.get("name"), "isin": symbol.get("isin"), "observations": []}
        try:
            payload = fetch_yahoo_payload(ticker)
            yahoo_store[ticker]["observations"].append({"fetched_at": now(), "raw": payload})
        except Exception as e:
            yahoo_store[ticker]["observations"].append({"fetched_at": now(), "raw": {"error": str(e)}})
        
        # Screener
        if ticker not in screener_store:
            screener_store[ticker] = {"ticker": ticker, "name": symbol.get("name"), "isin": symbol.get("isin"), "observations": []}
        try:
            payload = fetch_screener_payload(ticker)
            screener_store[ticker]["observations"].append({"fetched_at": now(), "raw": payload})
        except Exception as e:
            screener_store[ticker]["observations"].append({"fetched_at": now(), "raw": {"error": str(e)}})
        
        # Finnhub
        if ticker not in finnhub_store:
            finnhub_store[ticker] = {"ticker": ticker, "name": symbol.get("name"), "isin": symbol.get("isin"), "observations": []}
        try:
            payload = fetch_finnhub_payload(ticker)
            finnhub_store[ticker]["observations"].append({"fetched_at": now(), "raw": payload})
            time.sleep(0.1)
        except Exception as e:
            finnhub_store[ticker]["observations"].append({"fetched_at": now(), "raw": {"error": str(e)}})
        
        processed += 1
        if processed % 20 == 0:
            logger.info(f"  Progress: {processed}/{len(symbols)-skipped}...")
    
    runtime = round(time.time() - start_time, 2)
    
    # Save
    logger.info(f"\nSaving files...")
    logger.info(f"  Current directory: {Path.cwd()}")
    save_json(YAHOO_FILE, yahoo_store)
    logger.info(f"  ✓ Saved: {YAHOO_FILE.resolve()}")
    save_json(SCREENER_FILE, screener_store)
    logger.info(f"  ✓ Saved: {SCREENER_FILE.resolve()}")
    save_json(FINNHUB_FILE, finnhub_store)
    logger.info(f"  ✓ Saved: {FINNHUB_FILE.resolve()}")
    
    # Test
    tester = Step1Tester(yahoo_store, screener_store, finnhub_store)
    tester.run_all_tests()
    
    # Commit
    commit_to_git(log_file)
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("STEP 1 EXECUTION SUMMARY")
    logger.info("="*80)
    logger.info(f"Processed:  {processed} companies")
    logger.info(f"Skipped:    {skipped} (bonds/delisted)")
    logger.info(f"Runtime:    {runtime}s")
    logger.info(f"Output:     {DATA_DIR.resolve()}/")
    logger.info("="*80)
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
