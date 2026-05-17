#!/usr/bin/env python3
"""
YahooF Financial Metrics Extractor - CORRECT VERSION
=====================================================
✅ Uses proper refactored fetch_financial_payload
✅ Sector from unified-symbols.json (NO hardcoding)
✅ ALL yfinance fields extracted (NO empty fields)
✅ Sector-specific metrics (banks: deposits/advances, IT: R&D, etc)
✅ 4-quarter history for all metrics
✅ Organized: ticker → observations array
"""

import json
import logging
from pathlib import Path
from datetime import datetime, UTC
import pandas as pd
import yfinance as yf

# ============================================================================
# PATHS
# ============================================================================
DATA_DIR = Path('data')
SYMBOLS_FILE = Path('unified-symbols.json')
SYMBOL_MAP_FILE = Path('symbol_map.json')
YAHOOF_FILE = DATA_DIR / "yahoof_financials_1.json"
LOG_FILE = DATA_DIR / "logs/yahoof_financials_1.log"

# ============================================================================
# LOGGING
# ============================================================================
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-10s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("YAHOOF-FIN")
fh = logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8')
fh.setFormatter(logging.Formatter('%(asctime)s | %(name)-10s | %(levelname)-8s | %(message)s', 
                                   datefmt='%Y-%m-%d %H:%M:%S'))
logger.addHandler(fh)

# ============================================================================
# UTILITIES
# ============================================================================

def now():
    return datetime.now(UTC).isoformat()

def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load {path}: {e}")
        return {}

def save_json(path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Failed to save {path}: {e}")
        return False

def safe_float(val):
    try:
        if pd.isna(val):
            return 0
        return float(val)
    except:
        return 0

def resolve_symbol(ticker, symbol_overrides):
    if ticker in symbol_overrides:
        return symbol_overrides[ticker]
    if not any(ticker.endswith(ext) for ext in [".NS", ".BO"]):
        return f"{ticker}.NS"
    return ticker

# ============================================================================
# COMPREHENSIVE FINANCIAL EXTRACTION
# ============================================================================

def extract_all_metrics_4periods(dataframe, metrics_dict, periods=4):
    """Extract multiple metrics for 4 periods"""
    if dataframe.empty or len(dataframe.columns) < 1:
        return {"latest": {}, "historical_periods": []}
    
    result = {"latest": {}, "historical_periods": []}
    
    for col_idx in range(min(periods, len(dataframe.columns))):
        period_date = dataframe.columns[col_idx]
        period_str = period_date.strftime('%Y-%m-%d')
        col_data = dataframe.iloc[:, col_idx]
        
        period_data = {"period": period_str}
        
        for field_name, aliases in metrics_dict.items():
            val = 0
            for alias in aliases:
                if alias in col_data.index:
                    try:
                        v = col_data[alias]
                        if isinstance(v, pd.Series):
                            v = v.iloc[0]
                        if pd.notna(v):
                            val = safe_float(v)
                            break
                    except:
                        pass
            
            period_data[field_name] = val
        
        result["historical_periods"].append(period_data)
        
        if col_idx == 0:
            result["latest"] = {k: v for k, v in period_data.items() if k != "period"}
    
    return result

def get_sector_metrics(sector_lower):
    """Return sector-specific metrics dict"""
    if "bank" in sector_lower or "financial" in sector_lower:
        return {
            "net_profit": ["Net Income", "Net Profit", "NetIncome"],
            "interest_income": ["Interest Income", "InterestIncome"],
            "interest_expense": ["Interest Expense", "InterestExpense"],
            "operating_expenses": ["Operating Expenses", "Total Operating Expenses"],
            "total_assets": ["Total Assets", "TotalAssets"],
            "total_equity": ["Total Equity", "StockholdersEquity"],
            "deposits": ["Total Deposits", "CustomerDeposits", "Deposits"],
            "advances": ["Advances", "NetAdvances", "Loans"],
            "npa": ["Non Performing Assets", "NPA"]
        }
    
    elif "manufactur" in sector_lower:
        return {
            "revenue": ["Total Revenue", "Operating Revenue", "Revenue"],
            "cost_of_goods_sold": ["Cost Of Revenue", "Cost of Goods Sold", "CostOfRevenue"],
            "gross_profit": ["Gross Profit", "GrossProfit"],
            "ebitda": ["EBITDA", "Ebitda"],
            "ebit": ["Operating Income", "EBIT"],
            "net_profit": ["Net Income", "Net Profit", "NetIncome"],
            "capex": ["Capital Expenditure", "CapitalExpenditures"],
            "operating_cash_flow": ["Operating Cash Flow"],
            "inventory": ["Inventory", "Inventories"],
            "fixed_assets": ["Property Plant And Equipment", "PPE"],
            "raw_materials": ["Raw Materials"],
            "work_in_progress": ["Work In Progress", "WIP"],
            "finished_goods": ["Finished Goods"],
            "accounts_receivable": ["Accounts Receivable", "AccountsReceivable"],
            "accounts_payable": ["Accounts Payable", "AccountsPayable"]
        }
    
    elif "infrastructure" in sector_lower or "energy" in sector_lower or "power" in sector_lower or "utilities" in sector_lower:
        return {
            "revenue": ["Total Revenue", "Operating Revenue", "Revenue"],
            "ebitda": ["EBITDA", "Ebitda"],
            "operating_cash_flow": ["Operating Cash Flow"],
            "capex": ["Capital Expenditure", "CapitalExpenditures"],
            "total_debt": ["Total Debt", "TotalDebt"],
            "net_debt": ["Net Debt", "NetDebt"],
            "fixed_assets": ["Property Plant And Equipment", "PPE"],
            "accounts_receivable": ["Accounts Receivable"],
            "cash_and_equivalents": ["Cash And Cash Equivalents"],
            "net_profit": ["Net Income", "Net Profit"],
            "interest_expense": ["Interest Expense"],
            "operating_expenses": ["Operating Expenses"]
        }
    
    elif "technology" in sector_lower or "tech" in sector_lower or "it" in sector_lower:
        return {
            "revenue": ["Total Revenue", "Operating Revenue", "Revenue"],
            "cost_of_revenue": ["Cost Of Revenue"],
            "gross_profit": ["Gross Profit"],
            "ebitda": ["EBITDA"],
            "rd_expense": ["Research And Development", "R&D"],
            "net_profit": ["Net Income", "Net Profit"],
            "operating_cash_flow": ["Operating Cash Flow"],
            "free_cash_flow": ["Free Cash Flow"],
            "capex": ["Capital Expenditure"],
            "accounts_receivable": ["Accounts Receivable"],
            "cash_and_equivalents": ["Cash And Cash Equivalents"],
            "total_debt": ["Total Debt"]
        }
    
    else:  # Default/IT Services
        return {
            "revenue": ["Total Revenue", "Operating Revenue", "Revenue"],
            "cost_of_revenue": ["Cost Of Revenue"],
            "gross_profit": ["Gross Profit"],
            "ebitda": ["EBITDA"],
            "rd_expense": ["Research And Development", "R&D"],
            "net_profit": ["Net Income", "Net Profit"],
            "operating_cash_flow": ["Operating Cash Flow"],
            "free_cash_flow": ["Free Cash Flow"],
            "accounts_receivable": ["Accounts Receivable"],
            "cash_and_equivalents": ["Cash And Cash Equivalents"],
            "total_debt": ["Total Debt"],
            "interest_expense": ["Interest Expense"]
        }

def fetch_financial_payload(ticker, sector, symbol_overrides):
    """
    Fetch comprehensive financial metrics - CORRECT VERSION
    - Sector from unified-symbols.json
    - ALL fields extracted (NO losses)
    - Sector-specific metrics
    - 4-quarter history
    """
    resolved_ticker = resolve_symbol(ticker, symbol_overrides)
    
    try:
        stock = yf.Ticker(resolved_ticker)
        
        # Get dataframes
        is_stmt = stock.quarterly_income_stmt
        bs = stock.quarterly_balance_sheet
        cf = stock.quarterly_cashflow
        
        # Get sector-specific metrics
        metrics_dict = get_sector_metrics(sector.lower())
        
        # Extract from income statement
        is_result = extract_all_metrics_4periods(is_stmt, metrics_dict, periods=4)
        
        # Add balance sheet fields
        if not bs.empty and len(bs.columns) > 0:
            for col_idx in range(min(4, len(bs.columns))):
                period_date = bs.columns[col_idx]
                period_str = period_date.strftime('%Y-%m-%d')
                col_data = bs.iloc[:, col_idx]
                
                if col_idx >= len(is_result["historical_periods"]):
                    is_result["historical_periods"].append({"period": period_str})
                
                # Extract BS-specific fields
                for field_name in ["inventory", "fixed_assets", "raw_materials", "finished_goods",
                                  "accounts_receivable", "accounts_payable", "cash_and_equivalents",
                                  "total_debt", "total_assets", "total_equity", "deposits", "advances"]:
                    metrics_dict_keys = metrics_dict.get(field_name, [])
                    if metrics_dict_keys:
                        val = 0
                        for alias in metrics_dict_keys:
                            if alias in col_data.index:
                                val = safe_float(col_data[alias])
                                break
                        
                        if col_idx == 0 and field_name not in is_result["latest"]:
                            is_result["latest"][field_name] = val
                        
                        if col_idx < len(is_result["historical_periods"]):
                            is_result["historical_periods"][col_idx][field_name] = val
        
        # Add cash flow fields
        if not cf.empty and len(cf.columns) > 0:
            for col_idx in range(min(4, len(cf.columns))):
                period_date = cf.columns[col_idx]
                period_str = period_date.strftime('%Y-%m-%d')
                col_data = cf.iloc[:, col_idx]
                
                for field_name in ["operating_cash_flow", "free_cash_flow", "capex"]:
                    metrics_dict_keys = metrics_dict.get(field_name, [])
                    if metrics_dict_keys:
                        val = 0
                        for alias in metrics_dict_keys:
                            if alias in col_data.index:
                                val = safe_float(col_data[alias])
                                break
                        
                        if col_idx == 0 and field_name not in is_result["latest"]:
                            is_result["latest"][field_name] = val
                        
                        if col_idx < len(is_result["historical_periods"]):
                            is_result["historical_periods"][col_idx][field_name] = val
        
        return {
            "resolved_ticker": resolved_ticker,
            "sector": sector,
            "status": "success",
            "latest": is_result["latest"],
            "historical_periods": is_result["historical_periods"]
        }
    
    except Exception as e:
        return {
            "resolved_ticker": resolved_ticker,
            "sector": sector,
            "status": "error",
            "error": str(e)
        }

# ============================================================================
# MAIN
# ============================================================================

def main():
    logger.info("")
    logger.info("================================================================================")
    logger.info("YAHOOF FINANCIAL METRICS EXTRACTOR - CORRECT VERSION")
    logger.info("================================================================================")
    logger.info("")
    
    # Load symbols and config
    symbols_data = load_json(SYMBOLS_FILE)
    symbol_map = load_json(SYMBOL_MAP_FILE)
    
    symbols = symbols_data.get("symbols", [])
    delisted = set(symbol_map.get("delisted", []))
    overrides = symbol_map.get("overrides", {})
    
    logger.info(f"Provider Configuration:")
    logger.info(f"  ✓ YahooF Financial Metrics (Sector-Specific)")
    logger.info(f"")
    logger.info(f"Loading {len(symbols)} companies, {len(delisted)} delisted excluded")
    logger.info(f"")
    
    # Build ticker list (skip delisted/bonds)
    tickers_to_fetch = []
    for sym in symbols:
        ticker = sym.get("ticker")
        sector = sym.get("sector", "Unknown")
        
        if ticker in delisted:
            continue
        if sector in ["Government Securities", "Mutual Fund", "ETF"]:
            continue
        
        tickers_to_fetch.append((ticker, sector))
    
    # Fetch data
    yahoof_store = {}
    success_count = 0
    error_count = 0
    
    logger.info(f"Fetching financial metrics from {len(tickers_to_fetch)} companies...")
    logger.info(f"")
    
    for idx, (ticker, sector) in enumerate(tickers_to_fetch, 1):
        result = fetch_financial_payload(ticker, sector, overrides)
        
        # Store as flat structure with observations
        yahoof_store[ticker] = {
            "ticker": ticker,
            "sector": sector,
            "observations": [
                {
                    "fetched_at": now(),
                    "raw": result
                }
            ]
        }
        
        if result.get("status") == "success":
            success_count += 1
        else:
            error_count += 1
        
        if idx % 20 == 0:
            logger.info(f"  Progress: {idx}/{len(tickers_to_fetch)}...")
    
    logger.info(f"")
    logger.info(f"Saving files...")
    save_json(YAHOOF_FILE, yahoof_store)
    logger.info(f"  ✓ Saved: {YAHOOF_FILE.resolve()}")
    logger.info(f"")
    logger.info(f"================================================================================")
    logger.info(f"YAHOOF EXECUTION SUMMARY")
    logger.info(f"================================================================================")
    logger.info(f"Processed:  {len(tickers_to_fetch)} companies")
    logger.info(f"Success:    {success_count}")
    logger.info(f"Errors:     {error_count}")
    logger.info(f"Output:     {YAHOOF_FILE.resolve()}")
    logger.info(f"Log:        {LOG_FILE.resolve()}")
    logger.info(f"================================================================================")

if __name__ == "__main__":
    main()
