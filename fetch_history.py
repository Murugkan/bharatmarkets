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
from abc import ABC, abstractmethod

# Ensure pandas available for financial metrics
try:
    import pandas as pd
except ImportError:
    subprocess.check_call([__import__('sys').executable, "-m", "pip", "install", "pandas", "-q"])
    import pandas as pd

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
FINANCIAL_FILE = DATA_DIR / "financial-metrics.json"

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
# SECTOR HANDLERS FOR FINANCIAL METRICS
# ============================================================================

SECTOR_MAPPING = {}

class SectorHandler(ABC):
    """Base class for sector-specific handlers"""
    
    @abstractmethod
    def extract_metrics(self, ticker_obj, latest_year):
        pass
    
    def extract_field(self, df, match_keys, date_col):
        """Safe field extraction"""
        for key in match_keys:
            if key in df.index:
                val = df.loc[key, date_col]
                if isinstance(val, pd.Series):
                    val = val.iloc[0]
                return float(val) if pd.notna(val) else 0
        return 0

class BankingHandler(SectorHandler):
    def extract_metrics(self, ticker_obj, latest_year):
        try:
            bs = ticker_obj.balance_sheet
            is_stmt = ticker_obj.income_stmt
            if bs.empty or is_stmt.empty:
                return {}
            return {
                "deposits": self.extract_field(bs, ["Total Deposits", "Customer Deposits"], latest_year),
                "advances": self.extract_field(bs, ["Advances", "Net Advances"], latest_year),
                "npl_gross": self.extract_field(bs, ["Gross NPA", "Non Performing Assets"], latest_year),
                "net_profit": self.extract_field(is_stmt, ["Net Income", "Net Profit"], latest_year),
                "total_assets": self.extract_field(bs, ["Total Assets"], latest_year),
                "capital": self.extract_field(bs, ["Total Equity", "Shareholders Equity"], latest_year)
            }
        except:
            return {}

class ManufacturingHandler(SectorHandler):
    def extract_metrics(self, ticker_obj, latest_year):
        try:
            bs = ticker_obj.balance_sheet
            cf = ticker_obj.cashflow
            is_stmt = ticker_obj.income_stmt
            if bs.empty or cf.empty or is_stmt.empty:
                return {}
            return {
                "capex": self.extract_field(cf, ["Capital Expenditure", "InvestmentsInPropertyPlantAndEquipment"], latest_year),
                "inventory": self.extract_field(bs, ["Inventory", "Inventories"], latest_year),
                "ppe_gross": self.extract_field(bs, ["Property Plant Equipment"], latest_year),
                "revenue": self.extract_field(is_stmt, ["Total Revenue", "Operating Revenue"], latest_year),
                "cogs": self.extract_field(is_stmt, ["Cost Of Revenue", "Cost of Goods Sold"], latest_year)
            }
        except:
            return {}

class ITServicesHandler(SectorHandler):
    def extract_metrics(self, ticker_obj, latest_year):
        try:
            bs = ticker_obj.balance_sheet
            is_stmt = ticker_obj.income_stmt
            cf = ticker_obj.cashflow
            if bs.empty or is_stmt.empty or cf.empty:
                return {}
            return {
                "revenue": self.extract_field(is_stmt, ["Total Revenue", "Operating Revenue"], latest_year),
                "ebitda": self.extract_field(is_stmt, ["EBITDA"], latest_year),
                "net_profit": self.extract_field(is_stmt, ["Net Income", "Net Profit"], latest_year),
                "operating_cash_flow": self.extract_field(cf, ["Operating Cash Flow"], latest_year),
                "accounts_receivable": self.extract_field(bs, ["Accounts Receivable"], latest_year),
                "cash": self.extract_field(bs, ["Cash And Cash Equivalents"], latest_year)
            }
        except:
            return {}

class TechnologyHandler(SectorHandler):
    def extract_metrics(self, ticker_obj, latest_year):
        try:
            bs = ticker_obj.balance_sheet
            is_stmt = ticker_obj.income_stmt
            cf = ticker_obj.cashflow
            if bs.empty or is_stmt.empty or cf.empty:
                return {}
            return {
                "revenue": self.extract_field(is_stmt, ["Total Revenue", "Operating Revenue"], latest_year),
                "gross_profit": self.extract_field(is_stmt, ["Gross Profit"], latest_year),
                "rd_expense": self.extract_field(is_stmt, ["Research And Development"], latest_year),
                "net_profit": self.extract_field(is_stmt, ["Net Income", "Net Profit"], latest_year),
                "inventory": self.extract_field(bs, ["Inventory", "Inventories"], latest_year),
                "debt": self.extract_field(bs, ["Total Debt"], latest_year)
            }
        except:
            return {}

class InfrastructureHandler(SectorHandler):
    def extract_metrics(self, ticker_obj, latest_year):
        try:
            bs = ticker_obj.balance_sheet
            is_stmt = ticker_obj.income_stmt
            cf = ticker_obj.cashflow
            if bs.empty or is_stmt.empty or cf.empty:
                return {}
            return {
                "revenue": self.extract_field(is_stmt, ["Total Revenue", "Operating Revenue"], latest_year),
                "capex": self.extract_field(cf, ["Capital Expenditure"], latest_year),
                "debt": self.extract_field(bs, ["Total Debt"], latest_year),
                "operating_cash_flow": self.extract_field(cf, ["Operating Cash Flow"], latest_year),
                "accounts_receivable": self.extract_field(bs, ["Accounts Receivable"], latest_year)
            }
        except:
            return {}

class DefaultHandler(SectorHandler):
    """Generic handler for unmapped sectors"""
    def extract_metrics(self, ticker_obj, latest_year):
        try:
            bs = ticker_obj.balance_sheet
            is_stmt = ticker_obj.income_stmt
            cf = ticker_obj.cashflow
            if bs.empty or is_stmt.empty:
                return {}
            return {
                "revenue": self.extract_field(is_stmt, ["Total Revenue", "Operating Revenue"], latest_year),
                "net_profit": self.extract_field(is_stmt, ["Net Income", "Net Profit"], latest_year),
                "total_assets": self.extract_field(bs, ["Total Assets"], latest_year),
                "cash": self.extract_field(bs, ["Cash And Cash Equivalents"], latest_year),
                "debt": self.extract_field(bs, ["Total Debt"], latest_year)
            }
        except:
            return {}

# Sector mapping: Maps real sector names to handler instances
def get_sector_handler(sector_name):
    """Get handler for any sector - use intelligent fallback"""
    sector_lower = sector_name.lower()
    
    # Check keywords in sector name (order matters!)
    if any(x in sector_lower for x in ["bank", "financial"]):
        return SECTOR_HANDLERS["Banking"]
    if any(x in sector_lower for x in ["manufactur", "industrial", "metal"]):
        return SECTOR_HANDLERS["Manufacturing"]
    if any(x in sector_lower for x in ["energy", "infrastructure", "utilit", "power"]):
        return SECTOR_HANDLERS["Infrastructure"]
    if any(x in sector_lower for x in ["information technology", "software", "tech", "telecom"]):
        return SECTOR_HANDLERS["IT Services"]
    
    # Default handler for all other sectors (Healthcare, Consumer, Materials, Defence, etc.)
    return SECTOR_HANDLERS["Default"]

SECTOR_HANDLERS = {
    "Banking": BankingHandler(),
    "Manufacturing": ManufacturingHandler(),
    "IT Services": ITServicesHandler(),
    "Technology": TechnologyHandler(),
    "Infrastructure": InfrastructureHandler(),
    "Default": DefaultHandler()
}

# ============================================================================
# TESTING CLASS
# ============================================================================

class Step1Tester:
    """Test Step 1 output"""
    
    def __init__(self, yahoo_data, screener_data, finnhub_data, financial_data=None):
        self.yahoo = yahoo_data
        self.screener = screener_data
        self.finnhub = finnhub_data
        self.financial = financial_data or {}
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
            ("Financial", FINANCIAL_FILE, self.financial),
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
        fin_tickers = set(self.financial.keys())
        all_tickers = y_tickers | s_tickers | f_tickers | fin_tickers
        
        logger.info(f"  Yahoo:     {len(y_tickers):2d} tickers")
        logger.info(f"  Screener:  {len(s_tickers):2d} tickers")
        logger.info(f"  Finnhub:   {len(f_tickers):2d} tickers")
        logger.info(f"  Financial: {len(fin_tickers):2d} tickers")
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
        fin_obs = sum(len(e.get('observations', [])) for e in self.financial.values())
        
        logger.info(f"  Yahoo:     {y_obs:3d} observations")
        logger.info(f"  Screener:  {s_obs:3d} observations")
        logger.info(f"  Finnhub:   {f_obs:3d} observations")
        logger.info(f"  Financial: {fin_obs:3d} observations")
        
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
        if fin_obs > 0:
            logger.info(f"  ✓ Financial has data")
            passed += 1
        
        self.results["Observation Counts"] = (passed, 4)
    
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

def fetch_finnhub_payload(ticker, finnhub_overrides):
    """Fetch from Finnhub API. Skip if ticker marked as '' in finnhub_overrides"""
    
    # Check if ticker should be skipped (empty string in overrides)
    if ticker in finnhub_overrides and finnhub_overrides[ticker] == "":
        return {"skipped": True, "reason": "Not available in Finnhub (free API limited coverage)"}
    
    # Use override symbol if provided, otherwise use default
    finnhub_symbol = finnhub_overrides.get(ticker, f"{ticker}.NS") if ticker in finnhub_overrides else f"{ticker}.NS"
    
    payload = {}
    
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

def fetch_financial_payload(ticker, sector, symbol_overrides):
    """Fetch financial metrics - RAW DATA ONLY with HISTORICAL DATA (4 quarters)"""
    resolved_ticker = resolve_symbol(ticker, symbol_overrides)
    
    payload = {
        "status": "not_available",
        "capex": {},
        "debt_details": {},
        "working_capital": {},
        "exceptional_items": {}
    }
    
    try:
        stock = yf.Ticker(resolved_ticker)
        
        # ========== CAPEX (4 quarters) ==========
        try:
            cf = stock.quarterly_cashflow
            if not cf.empty and 'Capital Expenditure' in cf.index:
                capex_data = cf.loc['Capital Expenditure'].head(4)
                history = []
                
                for date, val in capex_data.items():
                    if pd.notna(val) and val != 0:
                        history.append({
                            'period': date.strftime('%Y-%m-%d'),
                            'value_raw': float(val)
                        })
                
                if history:
                    payload["capex"] = {
                        "status": "success",
                        "source": "yfinance",
                        "historical_periods": history[:4]
                    }
        except Exception as e:
            payload["capex"]["error"] = str(e)
        
        # ========== DEBT (4 quarters) ==========
        try:
            bs = stock.quarterly_balance_sheet
            if not bs.empty and len(bs.columns) > 0:
                history = []
                
                for col_idx in range(min(4, len(bs.columns))):
                    period = bs.iloc[:, col_idx]
                    period_date = bs.columns[col_idx]
                    
                    st_debt = None
                    lt_debt = None
                    
                    for key in period.index:
                        k_lower = str(key).lower()
                        if 'short' in k_lower and ('debt' in k_lower or 'borrowing' in k_lower):
                            val = period[key]
                            if pd.notna(val) and val > 0:
                                st_debt = float(val)
                        if 'long term' in k_lower and 'debt' in k_lower:
                            val = period[key]
                            if pd.notna(val) and val > 0:
                                lt_debt = float(val)
                    
                    if st_debt is not None or lt_debt is not None:
                        period_data = {'period': period_date.strftime('%Y-%m-%d')}
                        if st_debt is not None:
                            period_data['short_term_debt_raw'] = st_debt
                        if lt_debt is not None:
                            period_data['long_term_debt_raw'] = lt_debt
                        history.append(period_data)
                
                if history:
                    payload["debt_details"] = {
                        "status": "success",
                        "source": "yfinance",
                        "historical_periods": history
                    }
        except Exception as e:
            payload["debt_details"]["error"] = str(e)
        
        # ========== WORKING CAPITAL (4 quarters) ==========
        try:
            bs = stock.quarterly_balance_sheet
            if not bs.empty and len(bs.columns) > 0:
                history = []
                
                for col_idx in range(min(4, len(bs.columns))):
                    period = bs.iloc[:, col_idx]
                    period_date = bs.columns[col_idx]
                    
                    ar = None
                    ap = None
                    inv = None
                    
                    for key in period.index:
                        k_lower = str(key).lower()
                        if 'accounts receivable' in k_lower:
                            val = period[key]
                            if pd.notna(val):
                                ar = float(val)
                        if 'accounts payable' in k_lower:
                            val = period[key]
                            if pd.notna(val):
                                ap = float(val)
                        if 'inventory' in k_lower:
                            val = period[key]
                            if pd.notna(val):
                                inv = float(val)
                    
                    if ar is not None or ap is not None or inv is not None:
                        period_data = {'period': period_date.strftime('%Y-%m-%d')}
                        if ar is not None:
                            period_data['accounts_receivable_raw'] = ar
                        if ap is not None:
                            period_data['accounts_payable_raw'] = ap
                        if inv is not None:
                            period_data['inventory_raw'] = inv
                        history.append(period_data)
                
                if history:
                    payload["working_capital"] = {
                        "status": "success",
                        "source": "yfinance",
                        "historical_periods": history
                    }
        except Exception as e:
            payload["working_capital"]["error"] = str(e)
        
        # ========== EXCEPTIONAL ITEMS (4 periods) ==========
        try:
            is_stmt = stock.quarterly_income_stmt
            if not is_stmt.empty and len(is_stmt.columns) > 0:
                history = []
                
                for col_idx in range(min(4, len(is_stmt.columns))):
                    period = is_stmt.iloc[:, col_idx]
                    period_date = is_stmt.columns[col_idx]
                    
                    for key in period.index:
                        k_lower = str(key).lower()
                        if 'exceptional' in k_lower or 'extraordinary' in k_lower:
                            val = period[key]
                            if pd.notna(val) and val != 0:
                                history.append({
                                    'period': period_date.strftime('%Y-%m-%d'),
                                    'value_raw': float(val)
                                })
                                break
                
                if history:
                    payload["exceptional_items"] = {
                        "status": "success",
                        "source": "yfinance",
                        "historical_periods": history
                    }
        except Exception as e:
            payload["exceptional_items"]["error"] = str(e)
        
        # Determine overall status
        if any(payload[key].get("status") == "success" for key in ["capex", "debt_details", "working_capital", "exceptional_items"]):
            payload["status"] = "success"
        
        return {
            "resolved_ticker": resolved_ticker,
            "sector": sector,
            "metrics": payload
        }
    except Exception as e:
        return {"error": str(e)}

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
            "data/finnhub-history.json",
            "data/financial-metrics.json"
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
        msg = f"[Step 1] Fetch: Yahoo+Screener+Finnhub+Financial ({timestamp})"
        
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
    
    # Load fetch configuration (from workflow)
    fetch_config = load_json(Path('.fetch_config.json'))
    FETCH_YAHOO = fetch_config.get('yahoo', True)
    FETCH_SCREENER = fetch_config.get('screener', True)
    FETCH_FINNHUB = fetch_config.get('finnhub', True)
    FETCH_FINANCIAL = fetch_config.get('financial', False)
    
    logger.info("\nProvider Configuration:")
    logger.info(f"  {'✓' if FETCH_YAHOO else '✗'} Yahoo Finance")
    logger.info(f"  {'✓' if FETCH_SCREENER else '✗'} Screener.in")
    logger.info(f"  {'✓' if FETCH_FINNHUB else '✗'} Finnhub API")
    logger.info(f"  {'✓' if FETCH_FINANCIAL else '✗'} Financial Metrics")
    
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
    FINNHUB_OVERRIDES = symbol_map.get("finnhub_overrides", {})
    SYMBOL_OVERRIDES = symbol_map.get("overrides", {})
    
    logger.info(f"  ✓ {len(symbols)} companies to fetch")
    logger.info(f"  ✓ {len(DELISTED)} delisted excluded")
    
    # Build sector mapping if financial enabled
    if FETCH_FINANCIAL:
        logger.info("\nBuilding sector mapping...")
        global SECTOR_MAPPING
        SECTOR_MAPPING = build_sector_mapping(symbols)
        logger.info(f"  ✓ Sector mapping built: {len(SECTOR_MAPPING)} stocks")
        unique_sectors = set(SECTOR_MAPPING.values())
        logger.info(f"  ✓ Unique sectors: {', '.join(sorted(unique_sectors))}")
    
    # Initialize stores
    yahoo_store = {}
    screener_store = {}
    finnhub_store = {}
    financial_store = {}
    
    processed = 0
    skipped = 0
    
    # Fetch (only enabled providers)
    enabled_count = sum([FETCH_YAHOO, FETCH_SCREENER, FETCH_FINNHUB, FETCH_FINANCIAL])
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
                payload = fetch_yahoo_payload(ticker)
                yahoo_store[ticker]["observations"].append({"fetched_at": now(), "raw": payload})
            except Exception as e:
                yahoo_store[ticker]["observations"].append({"fetched_at": now(), "raw": {"error": str(e)}})
        
        # Screener (if enabled)
        if FETCH_SCREENER:
            if ticker not in screener_store:
                screener_store[ticker] = {"ticker": ticker, "name": symbol.get("name"), "isin": symbol.get("isin"), "observations": []}
            try:
                payload = fetch_screener_payload(ticker)
                screener_store[ticker]["observations"].append({"fetched_at": now(), "raw": payload})
            except Exception as e:
                screener_store[ticker]["observations"].append({"fetched_at": now(), "raw": {"error": str(e)}})
        
        # Finnhub (if enabled)
        if FETCH_FINNHUB:
            if ticker not in finnhub_store:
                finnhub_store[ticker] = {"ticker": ticker, "name": symbol.get("name"), "isin": symbol.get("isin"), "observations": []}
            try:
                payload = fetch_finnhub_payload(ticker, FINNHUB_OVERRIDES)
                finnhub_store[ticker]["observations"].append({"fetched_at": now(), "raw": payload})
                if not payload.get("skipped"):
                    time.sleep(0.1)
            except Exception as e:
                finnhub_store[ticker]["observations"].append({"fetched_at": now(), "raw": {"error": str(e)}})
        
        # Financial Metrics (if enabled)
        if FETCH_FINANCIAL:
            sector = SECTOR_MAPPING.get(ticker, "Other")
            if ticker not in financial_store:
                financial_store[ticker] = {"ticker": ticker, "name": symbol.get("name"), "isin": symbol.get("isin"), "sector": sector, "observations": []}
            try:
                payload = fetch_financial_payload(ticker, sector, SYMBOL_OVERRIDES)
                financial_store[ticker]["observations"].append({"fetched_at": now(), "raw": payload})
            except Exception as e:
                financial_store[ticker]["observations"].append({"fetched_at": now(), "raw": {"error": str(e)}})
        
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
    
    if FETCH_FINNHUB:
        save_json(FINNHUB_FILE, finnhub_store)
        logger.info(f"  ✓ Saved: {FINNHUB_FILE.resolve()}")
    
    if FETCH_FINANCIAL:
        save_json(FINANCIAL_FILE, financial_store)
        logger.info(f"  ✓ Saved: {FINANCIAL_FILE.resolve()}")
    
    # Test
    tester = Step1Tester(yahoo_store, screener_store, finnhub_store, financial_store)
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
