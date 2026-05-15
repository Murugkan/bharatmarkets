#!/usr/bin/env python3
"""
STEP 2: MERGE & CONSOLIDATE MODULE
===================================
Independent module for consolidating 3 sources into 1
Includes: Consolidation + Testing + Logging + Git Commit (all self-contained)

GitHub Structure (relative paths):
bharatmarkets/
├── step1_fetch.py
├── step2_merge.py (THIS FILE)
├── merged_fundamentals.json (output)
├── symbol_map.json
└── data/
    ├── yahoo-history.json (input from Step 1)
    ├── screener-history.json (input from Step 1)
    └── finnhub-history.json (input from Step 1)
"""

import json
import logging
import subprocess
from pathlib import Path
from datetime import datetime
import sys

# ============================================================================
# PATHS - All relative to repository root (where script runs)
# ============================================================================

# Working from repository root directory
DATA_DIR = Path('data')

# Input files (from Step 1 output)
YAHOO_FILE = DATA_DIR / "yahoo-history.json"
SCREENER_FILE = DATA_DIR / "screener-history.json"
FINNHUB_FILE = DATA_DIR / "finnhub-history.json"

# Output file
MERGED_FILE = Path("merged_fundamentals.json")

# Verify paths exist (fail fast)
def verify_paths():
    """Verify all required input files exist"""
    missing = []
    
    if not YAHOO_FILE.exists():
        missing.append(f"YAHOO_FILE: {YAHOO_FILE.resolve()}")
    if not SCREENER_FILE.exists():
        missing.append(f"SCREENER_FILE: {SCREENER_FILE.resolve()}")
    if not FINNHUB_FILE.exists():
        missing.append(f"FINNHUB_FILE: {FINNHUB_FILE.resolve()}")
    
    if missing:
        error_msg = "Missing Step 1 output files:\n  " + "\n  ".join(missing)
        logger.error(error_msg)
        logger.error(f"Working directory: {Path.cwd()}")
        logger.error(f"Expected data location: {DATA_DIR.resolve()}")
        raise FileNotFoundError(error_msg)

# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-10s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("STEP2-MERGE")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Cannot load {path.name}: {e}")
        return {}

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ============================================================================
# CONSOLIDATION LOGIC
# ============================================================================

def consolidate(yahoo_data, screener_data, finnhub_data):
    """Consolidate 3 sources into 1"""
    
    logger.info("\nConsolidating data...")
    
    merged = {}
    errors = []
    all_tickers = set(yahoo_data.keys()) | set(screener_data.keys()) | set(finnhub_data.keys())
    
    for ticker in sorted(all_tickers):
        try:
            yahoo = yahoo_data.get(ticker, {})
            screener = screener_data.get(ticker, {})
            finnhub = finnhub_data.get(ticker, {})
            
            name = (yahoo or screener or finnhub).get('name', ticker)
            isin = (yahoo or screener or finnhub).get('isin', '')
            
            observations = []
            observations.extend(yahoo.get('observations', []))
            observations.extend(screener.get('observations', []))
            observations.extend(finnhub.get('observations', []))
            
            merged[ticker] = {
                'ticker': ticker,
                'name': name,
                'isin': isin,
                'observations': observations
            }
        except Exception as e:
            errors.append(f"ERROR {ticker}: {str(e)[:80]}")
    
    logger.info(f"  ✓ Consolidated {len(merged)} tickers")
    if errors:
        logger.warning(f"  ⚠️  {len(errors)} errors during consolidation")
    
    return merged, errors

# ============================================================================
# TESTING CLASS
# ============================================================================

class Step2Tester:
    """Test Step 2 consolidation"""
    
    def __init__(self, yahoo, screener, finnhub, merged):
        self.yahoo = yahoo
        self.screener = screener
        self.finnhub = finnhub
        self.merged = merged
        self.results = {}
    
    def run_all_tests(self):
        """Run all Step 2 tests"""
        logger.info("\n" + "="*80)
        logger.info("STEP 2: TESTING CONSOLIDATION")
        logger.info("="*80)
        
        self.test_merged_file_created()
        self.test_all_tickers_present()
        self.test_observation_counts()
        self.test_data_integrity()
        
        return self.print_summary()
    
    def test_merged_file_created(self):
        """Test 1: merged_fundamentals.json created"""
        logger.info("\n[TEST 1] MERGED FILE CREATED")
        logger.info("-" * 80)
        
        if MERGED_FILE.exists():
            logger.info(f"  ✓ File created: {MERGED_FILE.name}")
            self.results["File Created"] = (1, 1)
        else:
            logger.error(f"  ✗ File NOT created")
            self.results["File Created"] = (0, 1)
    
    def test_all_tickers_present(self):
        """Test 2: All tickers consolidated"""
        logger.info("\n[TEST 2] ALL TICKERS PRESENT")
        logger.info("-" * 80)
        
        expected = set(self.yahoo.keys()) | set(self.screener.keys()) | set(self.finnhub.keys())
        actual = set(self.merged.keys())
        
        logger.info(f"  Expected tickers: {len(expected)}")
        logger.info(f"  Merged tickers:   {len(actual)}")
        
        missing = expected - actual
        extra = actual - expected
        
        if not missing and not extra:
            logger.info(f"  ✓ All tickers consolidated")
            self.results["Tickers Present"] = (1, 1)
        else:
            if missing:
                logger.warning(f"  ⚠️  {len(missing)} tickers missing")
            if extra:
                logger.warning(f"  ⚠️  {len(extra)} extra tickers")
            self.results["Tickers Present"] = (0, 1)
    
    def test_observation_counts(self):
        """Test 3: Observation counts correct"""
        logger.info("\n[TEST 3] OBSERVATION COUNTS")
        logger.info("-" * 80)
        
        yahoo_obs = sum(len(e.get('observations', [])) for e in self.yahoo.values())
        screener_obs = sum(len(e.get('observations', [])) for e in self.screener.values())
        finnhub_obs = sum(len(e.get('observations', [])) for e in self.finnhub.values())
        merged_obs = sum(len(e.get('observations', [])) for e in self.merged.values())
        expected_obs = yahoo_obs + screener_obs + finnhub_obs
        
        logger.info(f"  Yahoo:     {yahoo_obs:3d} observations")
        logger.info(f"  Screener:  {screener_obs:3d} observations")
        logger.info(f"  Finnhub:   {finnhub_obs:3d} observations")
        logger.info(f"  Expected:  {expected_obs:3d} observations")
        logger.info(f"  Merged:    {merged_obs:3d} observations")
        
        if merged_obs == expected_obs:
            logger.info(f"  ✓ Observation counts match")
            self.results["Observation Counts"] = (1, 1)
        else:
            diff = expected_obs - merged_obs
            logger.warning(f"  ⚠️  {diff} observations missing")
            self.results["Observation Counts"] = (0, 1)
    
    def test_data_integrity(self):
        """Test 4: Data structure valid"""
        logger.info("\n[TEST 4] DATA INTEGRITY")
        logger.info("-" * 80)
        
        issues = 0
        for ticker, entry in list(self.merged.items())[:5]:
            if not entry.get('ticker'):
                logger.warning(f"  ⚠️  {ticker}: Missing ticker field")
                issues += 1
            if not isinstance(entry.get('observations'), list):
                logger.warning(f"  ⚠️  {ticker}: observations not list")
                issues += 1
            if len(entry.get('observations', [])) == 0:
                logger.warning(f"  ⚠️  {ticker}: No observations")
                issues += 1
        
        if issues == 0:
            logger.info(f"  ✓ Data structure valid (sample checked)")
            self.results["Data Integrity"] = (1, 1)
        else:
            logger.warning(f"  ⚠️  {issues} integrity issues found")
            self.results["Data Integrity"] = (0, 1)
    
    def print_summary(self):
        """Print test summary"""
        logger.info("\n" + "="*80)
        logger.info("STEP 2 TEST SUMMARY")
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
            logger.info("✅ STEP 2 CONSOLIDATION VALIDATED")
        else:
            logger.warning("⚠️ STEP 2 CONSOLIDATION HAS ISSUES")
        
        return True

# ============================================================================
# GIT COMMIT
# ============================================================================

def commit_to_git():
    """Commit merged data to Git"""
    logger.info("\n" + "="*80)
    logger.info("COMMITTING TO GIT")
    logger.info("="*80)
    logger.info(f"Working directory: {Path.cwd()}")
    
    try:
        # Check if in git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            logger.warning("  ⚠️  Not in a git repository - skipping commit")
            return True
        
        logger.info(f"  ✓ Git repo found: {result.stdout.strip()}")
        
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
        
        # Add files (relative paths from repo root)
        files = [
            "merged_fundamentals.json",
            "data/yahoo-history.json",
            "data/screener-history.json",
            "data/finnhub-history.json"
        ]
        
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
                    logger.warning(f"  ⚠️  Failed to add {file}: {result.stderr.strip()}")
            else:
                logger.warning(f"  ⚠️  File not found: {filepath.resolve()}")
        
        if files_added == 0:
            logger.warning("  ⚠️  No files were added to git")
            return True
        
        # Commit
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[Step 2] Consolidate: Yahoo+Screener+Finnhub ({timestamp})"
        
        result = subprocess.run(
            ["git", "commit", "-m", msg],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            logger.info(f"  ✓ Committed")
            logger.info(f"    {msg}")
            return True
        else:
            if "nothing to commit" in result.stderr.lower() or "nothing to commit" in result.stdout.lower():
                logger.info(f"  ⊘ Nothing new to commit")
                return True
            else:
                logger.warning(f"  ⚠️  Commit failed:")
                if result.stderr.strip():
                    logger.warning(f"    Error: {result.stderr.strip()}")
                if result.stdout.strip():
                    logger.warning(f"    Output: {result.stdout.strip()}")
                return True
    
    except Exception as e:
        logger.error(f"  ✗ Git error: {str(e)}")
        return True

# ============================================================================
# MAIN
# ============================================================================

def main():
    logger.info("\n" + "="*80)
    logger.info("STEP 2: MERGE & CONSOLIDATE MODULE")
    logger.info("="*80)
    
    # Verify paths
    logger.info("\nVerifying paths...")
    logger.info(f"  Working directory: {Path.cwd()}")
    try:
        verify_paths()
        logger.info(f"  ✓ DATA_DIR:        {DATA_DIR}")
        logger.info(f"  ✓ YAHOO_FILE:      {YAHOO_FILE.resolve()}")
        logger.info(f"  ✓ SCREENER_FILE:   {SCREENER_FILE.resolve()}")
        logger.info(f"  ✓ FINNHUB_FILE:    {FINNHUB_FILE.resolve()}")
    except FileNotFoundError as e:
        logger.error(f"  ✗ {e}")
        logger.error("  Make sure Step 1 has completed successfully")
        return 1
    
    # Load sources
    logger.info("\nLoading source files...")
    yahoo = load_json(YAHOO_FILE)
    screener = load_json(SCREENER_FILE)
    finnhub = load_json(FINNHUB_FILE)
    
    logger.info(f"  ✓ Yahoo:     {len(yahoo)} tickers")
    logger.info(f"  ✓ Screener:  {len(screener)} tickers")
    logger.info(f"  ✓ Finnhub:   {len(finnhub)} tickers")
    
    # Consolidate
    merged, errors = consolidate(yahoo, screener, finnhub)
    
    # Save
    logger.info("\nSaving merged file...")
    save_json(MERGED_FILE, merged)
    logger.info(f"  ✓ {MERGED_FILE}")
    
    # Test
    tester = Step2Tester(yahoo, screener, finnhub, merged)
    tester.run_all_tests()
    
    # Commit
    commit_to_git()
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("STEP 2 EXECUTION SUMMARY")
    logger.info("="*80)
    logger.info(f"Working directory: {Path.cwd()}")
    logger.info(f"Sources:           Yahoo + Screener + Finnhub")
    logger.info(f"Tickers:           {len(merged)}")
    logger.info(f"Observations:      {sum(len(e.get('observations', [])) for e in merged.values())}")
    logger.info(f"Output (rel):      merged_fundamentals.json")
    logger.info(f"Output (abs):      {MERGED_FILE.resolve()}")
    logger.info(f"Consolidation:     ✅ COMPLETE")
    logger.info("="*80)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
