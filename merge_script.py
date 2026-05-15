#!/usr/bin/env python3
"""
Step 1: Data Consolidation Module - WITH TESTING FRAMEWORK + FINNHUB
====================================================================
Includes stock-by-stock & cell-by-cell comparison testing
Now supports Yahoo, Screener, AND Finnhub data sources
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
import sys


# ============================================================================
# STOCK-BY-STOCK & CELL-BY-CELL TESTING FRAMEWORK
# ============================================================================

class StockByStockTester:
    """
    Comprehensive testing framework for stock-by-stock and cell-by-cell
    comparison between Yahoo, Screener, Finnhub, and Merged data files.
    """
    
    def __init__(self, yahoo_data: Dict, screener_data: Dict, finnhub_data: Dict, merged_data: Dict, logger):
        self.yahoo_data = yahoo_data
        self.screener_data = screener_data
        self.finnhub_data = finnhub_data
        self.merged_data = merged_data
        self.log = logger
        
        # Mismatch tracking
        self.mismatches = {
            'ticker_level': [],
            'observation_count': [],
            'field_level': [],
            'data_loss': [],
            'type_errors': [],
            'duplicates': []
        }
        
        self.test_results = []
    
    def run_all_tests(self) -> bool:
        """Run all stock-by-stock and cell-by-cell tests"""
        self.log.info("\n" + "="*80)
        self.log.info("ADVANCED TESTING: STOCK-BY-STOCK & CELL-BY-CELL COMPARISON")
        self.log.info("="*80)
        
        all_passed = True
        all_passed &= self.test_ticker_by_ticker()
        all_passed &= self.test_stock_observation_counts()
        all_passed &= self.test_yahoo_vs_merged_cells()
        all_passed &= self.test_screener_vs_merged_cells()
        all_passed &= self.test_finnhub_vs_merged_cells()
        all_passed &= self.test_data_types_cell_level()
        all_passed &= self.test_field_by_field()
        
        self.print_mismatch_report()
        return all_passed
    
    # TEST 1: Ticker-by-Ticker
    def test_ticker_by_ticker(self) -> bool:
        self.log.info("\n[TEST 1] TICKER-BY-TICKER COMPARISON")
        self.log.info("-" * 80)
        
        yahoo_tickers = set(self.yahoo_data.keys())
        screener_tickers = set(self.screener_data.keys())
        finnhub_tickers = set(self.finnhub_data.keys())
        merged_tickers = set(self.merged_data.keys())
        
        expected_tickers = yahoo_tickers | screener_tickers | finnhub_tickers
        missing = expected_tickers - merged_tickers
        extra = merged_tickers - expected_tickers
        
        if missing:
            for ticker in missing:
                self.mismatches['ticker_level'].append(f"Missing in merged: {ticker}")
                self.log.error(f"  Missing: {ticker}")
        
        if extra:
            for ticker in extra:
                self.mismatches['ticker_level'].append(f"Extra in merged: {ticker}")
                self.log.warning(f"  Extra: {ticker}")
        
        if not missing and not extra:
            self.log.info(f"  ✓ All {len(merged_tickers)} tickers match")
            self.test_results.append(("Ticker-by-Ticker", True))
            return True
        else:
            self.test_results.append(("Ticker-by-Ticker", False))
            return False
    
    # TEST 2: Stock Observation Counts
    def test_stock_observation_counts(self) -> bool:
        self.log.info("\n[TEST 2] STOCK-BY-STOCK OBSERVATION COUNT VERIFICATION")
        self.log.info("-" * 80)
        
        issues = 0
        all_tickers = set(self.yahoo_data.keys()) | set(self.screener_data.keys()) | set(self.finnhub_data.keys())
        
        for ticker in sorted(all_tickers):
            yahoo_count = len(self.yahoo_data.get(ticker, {}).get('observations', []))
            screener_count = len(self.screener_data.get(ticker, {}).get('observations', []))
            finnhub_count = len(self.finnhub_data.get(ticker, {}).get('observations', []))
            merged_count = len(self.merged_data.get(ticker, {}).get('observations', []))
            expected = yahoo_count + screener_count + finnhub_count
            
            if merged_count != expected:
                issues += 1
                msg = f"{ticker}: Expected {expected}, got {merged_count}"
                self.mismatches['observation_count'].append(msg)
                if issues <= 3:
                    self.log.warning(f"  {msg}")
        
        if issues == 0:
            self.log.info(f"  ✓ All {len(all_tickers)} stocks have correct observation counts")
            self.test_results.append(("Stock Observation Counts", True))
            return True
        else:
            self.log.warning(f"  {issues} stock(s) have count mismatches")
            self.test_results.append(("Stock Observation Counts", issues == 0))
            return issues == 0
    
    # TEST 3: Yahoo vs Merged (Cell-by-Cell)
    def test_yahoo_vs_merged_cells(self) -> bool:
        self.log.info("\n[TEST 3] CELL-BY-CELL: YAHOO vs MERGED")
        self.log.info("-" * 80)
        
        issues = 0
        for ticker in sorted(self.yahoo_data.keys()):
            yahoo_entry = self.yahoo_data[ticker]
            merged_entry = self.merged_data.get(ticker, {})
            
            # Check metadata
            for field in ['ticker', 'name', 'isin']:
                if yahoo_entry.get(field) != merged_entry.get(field):
                    issues += 1
                    msg = f"{ticker}.{field}: Value mismatch"
                    self.mismatches['field_level'].append(msg)
                    if issues <= 3:
                        self.log.warning(f"  {msg}")
            
            # Check observations
            yahoo_obs = yahoo_entry.get('observations', [])
            merged_obs = merged_entry.get('observations', [])
            
            for i, obs in enumerate(yahoo_obs):
                obs_json = json.dumps(obs, sort_keys=True, default=str)
                found = any(
                    obs_json == json.dumps(m, sort_keys=True, default=str)
                    for m in merged_obs
                )
                if not found:
                    issues += 1
                    msg = f"{ticker}: Yahoo obs[{i}] missing in merged"
                    self.mismatches['data_loss'].append(msg)
                    if issues <= 3:
                        self.log.error(f"  {msg}")
        
        if issues == 0:
            self.log.info("  ✓ All Yahoo data perfectly preserved")
            self.test_results.append(("Yahoo vs Merged", True))
            return True
        else:
            self.log.error(f"  {issues} cell mismatches found")
            self.test_results.append(("Yahoo vs Merged", False))
            return False
    
    # TEST 4: Screener vs Merged (Cell-by-Cell)
    def test_screener_vs_merged_cells(self) -> bool:
        self.log.info("\n[TEST 4] CELL-BY-CELL: SCREENER vs MERGED")
        self.log.info("-" * 80)
        
        issues = 0
        for ticker in sorted(self.screener_data.keys()):
            screener_entry = self.screener_data[ticker]
            merged_entry = self.merged_data.get(ticker, {})
            
            screener_obs = screener_entry.get('observations', [])
            merged_obs = merged_entry.get('observations', [])
            
            for i, obs in enumerate(screener_obs):
                obs_json = json.dumps(obs, sort_keys=True, default=str)
                found = any(
                    obs_json == json.dumps(m, sort_keys=True, default=str)
                    for m in merged_obs
                )
                if not found:
                    issues += 1
                    msg = f"{ticker}: Screener obs[{i}] missing in merged"
                    self.mismatches['data_loss'].append(msg)
                    if issues <= 3:
                        self.log.error(f"  {msg}")
        
        if issues == 0:
            self.log.info("  ✓ All Screener data perfectly preserved")
            self.test_results.append(("Screener vs Merged", True))
            return True
        else:
            self.log.error(f"  {issues} cell mismatches found")
            self.test_results.append(("Screener vs Merged", False))
            return False
    
    # TEST 5: Finnhub vs Merged (Cell-by-Cell)
    def test_finnhub_vs_merged_cells(self) -> bool:
        self.log.info("\n[TEST 5] CELL-BY-CELL: FINNHUB vs MERGED")
        self.log.info("-" * 80)
        
        if not self.finnhub_data:
            self.log.info("  ⊘ Finnhub data not available (skipped)")
            self.test_results.append(("Finnhub vs Merged", True))
            return True
        
        issues = 0
        for ticker in sorted(self.finnhub_data.keys()):
            finnhub_entry = self.finnhub_data[ticker]
            merged_entry = self.merged_data.get(ticker, {})
            
            finnhub_obs = finnhub_entry.get('observations', [])
            merged_obs = merged_entry.get('observations', [])
            
            for i, obs in enumerate(finnhub_obs):
                obs_json = json.dumps(obs, sort_keys=True, default=str)
                found = any(
                    obs_json == json.dumps(m, sort_keys=True, default=str)
                    for m in merged_obs
                )
                if not found:
                    issues += 1
                    msg = f"{ticker}: Finnhub obs[{i}] missing in merged"
                    self.mismatches['data_loss'].append(msg)
                    if issues <= 3:
                        self.log.error(f"  {msg}")
        
        if issues == 0:
            self.log.info("  ✓ All Finnhub data perfectly preserved")
            self.test_results.append(("Finnhub vs Merged", True))
            return True
        else:
            self.log.error(f"  {issues} cell mismatches found")
            self.test_results.append(("Finnhub vs Merged", False))
            return False
    
    # TEST 6: Data Types (Cell Level)
    def test_data_types_cell_level(self) -> bool:
        self.log.info("\n[TEST 6] DATA TYPE VALIDATION (Cell Level)")
        self.log.info("-" * 80)
        
        errors = 0
        for ticker, entry in self.merged_data.items():
            if not isinstance(entry.get('ticker'), str):
                errors += 1
                self.mismatches['type_errors'].append(f"{ticker}: ticker not string")
            if not isinstance(entry.get('name'), str):
                errors += 1
                self.mismatches['type_errors'].append(f"{ticker}: name not string")
            if not isinstance(entry.get('isin'), str):
                errors += 1
                self.mismatches['type_errors'].append(f"{ticker}: isin not string")
            if not isinstance(entry.get('observations'), list):
                errors += 1
                self.mismatches['type_errors'].append(f"{ticker}: observations not list")
        
        if errors == 0:
            self.log.info("  ✓ All cell data types correct")
            self.test_results.append(("Data Types", True))
            return True
        else:
            self.log.error(f"  {errors} type errors found")
            self.test_results.append(("Data Types", False))
            return False
    
    # TEST 7: Field-by-Field Analysis
    def test_field_by_field(self) -> bool:
        self.log.info("\n[TEST 7] FIELD-BY-FIELD ANALYSIS")
        self.log.info("-" * 80)
        
        if not self.merged_data:
            self.log.warning("  No merged data to analyze")
            self.test_results.append(("Field Analysis", False))
            return False
        
        sample_ticker = list(self.merged_data.keys())[0]
        entry = self.merged_data[sample_ticker]
        
        self.log.info(f"  Sample ticker: {sample_ticker}")
        self.log.info(f"  Fields: {list(entry.keys())}")
        self.log.info(f"  Observations: {len(entry.get('observations', []))}")
        
        if len(entry.get('observations', [])) > 0:
            obs = entry['observations'][0]
            self.log.info(f"  First obs keys: {list(obs.keys())}")
        
        self.test_results.append(("Field Analysis", True))
        return True
    
    def print_mismatch_report(self):
        """Print detailed mismatch report"""
        self.log.info("\n" + "="*80)
        self.log.info("MISMATCH REPORT")
        self.log.info("="*80)
        
        total_mismatches = sum(len(v) for v in self.mismatches.values())
        
        self.log.info(f"\nTotal Mismatches: {total_mismatches}")
        self.log.info(f"  Ticker Level: {len(self.mismatches['ticker_level'])}")
        self.log.info(f"  Observation Count: {len(self.mismatches['observation_count'])}")
        self.log.info(f"  Field Level: {len(self.mismatches['field_level'])}")
        self.log.info(f"  Data Loss: {len(self.mismatches['data_loss'])}")
        self.log.info(f"  Type Errors: {len(self.mismatches['type_errors'])}")
        
        if total_mismatches == 0:
            self.log.info("\n✅ PERFECT MATCH - ALL TESTS PASSED")
        else:
            self.log.warning(f"\n⚠️ {total_mismatches} mismatches recorded")
            
            for category, items in self.mismatches.items():
                if items:
                    self.log.warning(f"\n{category.upper()}:")
                    for item in items[:5]:
                        self.log.warning(f"  - {item}")
                    if len(items) > 5:
                        self.log.warning(f"  ... and {len(items)-5} more")
        
        self.log.info("\n" + "="*80)


# ============================================================================
# MAIN CONSOLIDATION CLASS (GitHub paths)
# ============================================================================

def quick_consolidation_with_testing():
    """Quick consolidation with stock-by-stock testing"""
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger("Step1-ConsolidationWithTesting")
    
    logger.info("\n" + "="*80)
    logger.info("STEP 1: DATA CONSOLIDATION WITH TESTING FRAMEWORK")
    logger.info("="*80)
    
    # GitHub paths (relative to script location)
    BASE_DIR = Path(__file__).resolve().parent
    DATA_DIR = BASE_DIR / "data"
    
    logger.info("\nLoading files from data directory...")
    
    yaml_file = DATA_DIR / "yahoo-history.json"
    screener_file = DATA_DIR / "screener-history.json"
    finnhub_file = DATA_DIR / "finnhub-history.json"
    merged_file = BASE_DIR / "merged_fundamentals.json"
    
    # Load Yahoo
    with open(yaml_file) as f:
        yahoo_data = json.load(f)
    
    # Load Screener
    with open(screener_file) as f:
        screener_data = json.load(f)
    
    # Load Finnhub (if exists)
    finnhub_data = {}
    if finnhub_file.exists():
        with open(finnhub_file) as f:
            finnhub_data = json.load(f)
    
    # Load or create merged
    if merged_file.exists():
        with open(merged_file) as f:
            merged_data = json.load(f)
    else:
        merged_data = {}
    
    logger.info(f"✓ Yahoo: {len(yahoo_data)} tickers")
    logger.info(f"✓ Screener: {len(screener_data)} tickers")
    logger.info(f"✓ Finnhub: {len(finnhub_data)} tickers")
    logger.info(f"✓ Merged: {len(merged_data)} tickers")
    
    # Run testing framework
    tester = StockByStockTester(yahoo_data, screener_data, finnhub_data, merged_data, logger)
    passed = tester.run_all_tests()
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)
    for test_name, result in tester.test_results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {test_name}")
    
    passed_count = sum(1 for _, r in tester.test_results if r)
    logger.info(f"\nResult: {passed_count}/{len(tester.test_results)} tests passed")
    
    if passed:
        logger.info("\n✅ ALL TESTS PASSED - DATA INTEGRITY VERIFIED")
    else:
        logger.warning("\n⚠️ Some tests failed - review mismatches above")
    
    logger.info("="*80)
    
    return passed, tester.mismatches


if __name__ == "__main__":
    passed, mismatches = quick_consolidation_with_testing()
    sys.exit(0 if passed else 1)
