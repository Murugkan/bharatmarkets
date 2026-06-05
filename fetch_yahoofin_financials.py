#!/usr/bin/env python3
"""
YahooF Financial Metrics Extractor
===================================
- Missing fields return blank "" not 0
- Sector-specific metrics from unified-symbols.json
- 4-quarter history for each metric
"""

import json
import time
import logging
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime, UTC

DATA_DIR = Path('data')
SYMBOLS_FILE = Path('unified-symbols.json')
SYMBOL_MAP_FILE = Path('symbol_map.json')
YAHOOF_FILE = DATA_DIR / "yahoofin_financials.json"
LOG_FILE = DATA_DIR / "logs/fetch_yahoofin_financials.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-10s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("YAHOOF-FIN")

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

def resolve_symbol(ticker, overrides):
    if ticker in overrides:
        return overrides[ticker]
    if not any(ticker.endswith(ext) for ext in [".NS", ".BO"]):
        return f"{ticker}.NS"
    return ticker

def build_sector_mapping(symbols_list):
    mapping = {}
    for symbol in symbols_list:
        ticker = str(symbol["ticker"]).strip()
        sector = symbol.get("sector") or symbol.get("industry") or symbol.get("group") or "Other"
        mapping[ticker] = sector
    return mapping

def safe_float(val):
    """Return float or empty string if missing"""
    try:
        if pd.isna(val):
            return ""
        return float(val)
    except:
        return ""

def find_field(series_data, aliases):
    """Find field value from pandas Series using case-insensitive matching"""
    if series_data.empty or series_data.index is None:
        return ""
    
    # Create lowercase index mapping
    index_map = {}
    for idx in series_data.index:
        idx_str = str(idx).lower().strip()
        index_map[idx_str] = idx
    
    # Try each alias
    for alias in aliases:
        alias_lower = alias.lower().strip()
        if alias_lower in index_map:
            try:
                actual_idx = index_map[alias_lower]
                val = series_data[actual_idx]
                # If value exists (even if 0), return it
                if pd.notna(val):
                    return safe_float(val)
            except Exception as e:
                pass
    
    # Field not found
    return ""

def get_sector_metrics(sector_lower):
    """Return sector-specific field aliases - using actual yfinance field names"""
    common_debt = {
        "total_debt": ["Total Debt"],
        "net_debt": ["Net Debt"],
        "short_term_debt": ["Short Term Debt", "Short Long Term Debt"],
        "long_term_debt": ["Long Term Debt"]
    }
    
    common_additional = {
        "diluted_eps": ["Diluted EPS"],
        "basic_eps": ["Basic EPS"],
        "diluted_shares": ["Diluted Average Shares"],
        "basic_shares": ["Basic Average Shares"],
        "shares_outstanding": ["Ordinary Shares Number", "Share Issued"],
        "normalized_income": ["Normalized Income"],
        "operating_income": ["Total Operating Income As Reported"],
        "tax_rate": ["Tax Rate For Calcs"],
        "total_capitalization": ["Total Capitalization"],
        "minority_interest": ["Minority Interest"],
        "capital_lease_obligations": ["Capital Lease Obligations"],
        "unusual_items": ["Total Unusual Items"]
    }
    
    if "bank" in sector_lower or "financial" in sector_lower:
        metrics = {
            "net_profit": ["Net Income", "Net Income Common Stockholders"],
            "interest_income": ["Net Interest Income", "Interest Income"],
            "interest_expense": ["Interest Expense"],
            "operating_expenses": ["Total Expenses"],
            "total_assets": ["Total Assets"],
            "total_liabilities": ["Total Liabilities Net Minority Interest"],
            "total_equity": ["Stockholders Equity", "Total Equity Gross Minority Interest"],
            "retained_earnings": ["Retained Earnings"],
            "tangible_book_value": ["Tangible Book Value"],
            "invested_capital": ["Invested Capital"],
            "deposits": ["Total Deposits", "Deposits"],
            "advances": ["Advances"],
            "npa": ["Non Performing Assets", "NPA"],
            "ebit": ["EBIT"],
            "depreciation": ["Reconciled Depreciation"]
        }
        metrics.update(common_debt)
        metrics.update(common_additional)
        return metrics
        
    elif "manufactur" in sector_lower:
        metrics = {
            "revenue": ["Total Revenue"],
            "cost_of_revenue": ["Reconciled Cost Of Revenue", "Cost Of Revenue"],
            "gross_profit": ["Gross Profit"],
            "ebitda": ["EBITDA"],
            "ebit": ["EBIT"],
            "net_profit": ["Net Income"],
            "capex": ["Capital Expenditure", "Capital Expenditures", "Capex"],
            "operating_cash_flow": ["Operating Cash Flow"],
            "depreciation": ["Reconciled Depreciation"],
            "working_capital": ["Working Capital"],
            "inventory": ["Inventory"],
            "fixed_assets": ["Property Plant Equipment"],
            "accounts_receivable": ["Accounts Receivable"],
            "accounts_payable": ["Accounts Payable"],
            "raw_materials": ["Raw Materials"],
            "finished_goods": ["Finished Goods"],
            "wip": ["Work In Progress"],
            "invested_capital": ["Invested Capital"],
            "tangible_book_value": ["Tangible Book Value"]
        }
        metrics.update(common_debt)
        metrics.update(common_additional)
        return metrics
        
    elif "energy" in sector_lower or "utilit" in sector_lower:
        metrics = {
            "revenue": ["Total Revenue"],
            "ebitda": ["EBITDA", "Normalized EBITDA"],
            "ebit": ["EBIT"],
            "operating_cash_flow": ["Operating Cash Flow"],
            "capex": ["Capital Expenditure", "Capital Expenditures", "Capex"],
            "total_liabilities": ["Total Liabilities Net Minority Interest"],
            "fixed_assets": ["Property Plant Equipment"],
            "accounts_receivable": ["Accounts Receivable"],
            "cash_and_equivalents": ["Cash And Cash Equivalents"],
            "net_profit": ["Net Income"],
            "interest_expense": ["Interest Expense"],
            "operating_expenses": ["Total Expenses"],
            "depreciation": ["Reconciled Depreciation"],
            "invested_capital": ["Invested Capital"],
            "working_capital": ["Working Capital"]
        }
        metrics.update(common_debt)
        metrics.update(common_additional)
        return metrics
        
    elif "technolog" in sector_lower or "it " in sector_lower:
        metrics = {
            "revenue": ["Total Revenue"],
            "cost_of_revenue": ["Reconciled Cost Of Revenue"],
            "gross_profit": ["Gross Profit"],
            "ebitda": ["EBITDA", "Normalized EBITDA"],
            "ebit": ["EBIT"],
            "rd_expense": ["Research And Development"],
            "net_profit": ["Net Income"],
            "operating_cash_flow": ["Operating Cash Flow"],
            "free_cash_flow": ["Free Cash Flow"],
            "capex": ["Capital Expenditure", "Capital Expenditures", "Capex"],
            "accounts_receivable": ["Accounts Receivable"],
            "cash_and_equivalents": ["Cash And Cash Equivalents"],
            "interest_expense": ["Interest Expense"],
            "depreciation": ["Reconciled Depreciation"],
            "invested_capital": ["Invested Capital"],
            "working_capital": ["Working Capital"],
            "net_tangible_assets": ["Net Tangible Assets"]
        }
        metrics.update(common_debt)
        metrics.update(common_additional)
        return metrics
        
    else:
        metrics = {
            "revenue": ["Total Revenue"],
            "ebitda": ["EBITDA", "Normalized EBITDA"],
            "ebit": ["EBIT"],
            "operating_cash_flow": ["Operating Cash Flow"],
            "net_profit": ["Net Income"],
            "gross_profit": ["Gross Profit"],
            "total_liabilities": ["Total Liabilities Net Minority Interest"],
            "accounts_receivable": ["Accounts Receivable"],
            "cash_and_equivalents": ["Cash And Cash Equivalents"],
            "interest_expense": ["Interest Expense"],
            "capex": ["Capital Expenditure", "Capital Expenditures", "Capex"],
            "free_cash_flow": ["Free Cash Flow"],
            "depreciation": ["Reconciled Depreciation"],
            "working_capital": ["Working Capital"],
            "invested_capital": ["Invested Capital"],
            "net_tangible_assets": ["Net Tangible Assets"]
        }
        metrics.update(common_debt)
        metrics.update(common_additional)
        return metrics

def fetch_financial_payload(ticker, sector, symbol_overrides):
    """Fetch financial metrics from yfinance"""
    resolved_ticker = resolve_symbol(ticker, symbol_overrides)
    
    try:
        stock = yf.Ticker(resolved_ticker)
        # Use annual statements for 10-year history.
        # yfinance exposes up to 4 annual periods via income_stmt/balance_sheet/cashflow.
        # quarterly_* variants only return ~4 recent quarters — not suitable for 10yr.
        is_stmt = stock.income_stmt
        bs = stock.balance_sheet
        cf = stock.cashflow
        
        metrics_dict = get_sector_metrics(sector.lower())
        
        result = {"latest": {}, "historical_periods": []}
        
        # DEBUG
        logger.debug(f"{ticker}: IS={is_stmt.shape if not is_stmt.empty else 'EMPTY'}, BS={bs.shape if not bs.empty else 'EMPTY'}, CF={cf.shape if not cf.empty else 'EMPTY'}")
        
        # Process all available annual periods (yfinance returns up to 4 years)
        max_periods = min(10, len(is_stmt.columns) if not is_stmt.empty else 0, 
                         len(bs.columns) if not bs.empty else 0,
                         len(cf.columns) if not cf.empty else 0)
        
        # If no periods with all 3 dataframes, try with just IS+BS
        if max_periods == 0:
            max_periods = min(10, len(is_stmt.columns) if not is_stmt.empty else 0,
                             len(bs.columns) if not bs.empty else 0)
        
        for col_idx in range(max_periods):
            period_date = is_stmt.columns[col_idx] if not is_stmt.empty else bs.columns[col_idx]
            period_str = period_date.strftime('%Y-%m-%d')
            period_data = {"period": period_str}
            
            # Get data for this period
            is_col = is_stmt.iloc[:, col_idx] if col_idx < len(is_stmt.columns) else pd.Series()
            bs_col = bs.iloc[:, col_idx] if col_idx < len(bs.columns) else pd.Series()
            cf_col = cf.iloc[:, col_idx] if col_idx < len(cf.columns) else pd.Series()
            
            # Extract each metric
            for field_name, aliases in metrics_dict.items():
                val = ""
                
                # Try income statement
                if not is_col.empty:
                    val = find_field(is_col, aliases)
                
                # Try balance sheet if not found
                if val == "" and not bs_col.empty:
                    val = find_field(bs_col, aliases)
                
                # Try cash flow if not found
                if val == "" and not cf_col.empty:
                    val = find_field(cf_col, aliases)
                
                period_data[field_name] = val
            
            result["historical_periods"].append(period_data)
            
            if col_idx == 0:
                result["latest"] = {k: v for k, v in period_data.items() if k != "period"}
        
        return {
            "resolved_ticker": resolved_ticker,
            "sector": sector,
            "status": "success",
            "latest": result["latest"],
            "historical_periods": result["historical_periods"]
        }
    except Exception as e:
        logger.error(f"Error fetching {ticker}: {e}")
        return {"error": str(e)}

def main():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(name)-10s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(file_handler)
    
    logger.info("\n" + "="*80)
    logger.info("YAHOOF FINANCIAL METRICS EXTRACTOR")
    logger.info("="*80)
    
    fetch_config = load_json(Path('.fetch_config.json'))
    FETCH_YAHOOF = fetch_config.get('yahoof', True)
    
    logger.info(f"\nProvider Configuration:")
    logger.info(f"  {'✓' if FETCH_YAHOOF else '✗'} YahooF Financial Metrics")
    
    logger.info("\nVerifying paths...")
    try:
        if not SYMBOLS_FILE.exists():
            raise FileNotFoundError(f"Missing: {SYMBOLS_FILE}")
        if not SYMBOL_MAP_FILE.exists():
            raise FileNotFoundError(f"Missing: {SYMBOL_MAP_FILE}")
        
        logger.info(f"  ✓ Working dir:   {Path.cwd()}")
        logger.info(f"  ✓ DATA_DIR:      {DATA_DIR.resolve()}")
        logger.info(f"  ✓ SYMBOLS_FILE:  {SYMBOLS_FILE.resolve()}")
        logger.info(f"  ✓ SYMBOL_MAP:    {SYMBOL_MAP_FILE.resolve()}")
    except FileNotFoundError as e:
        logger.error(f"  ✗ {e}")
        return 1
    
    start_time = time.time()
    
    logger.info("\nLoading configuration...")
    symbols_master = load_json(SYMBOLS_FILE)
    symbols = symbols_master.get("symbols", [])
    symbol_map = load_json(SYMBOL_MAP_FILE)
    
    DELISTED = set(symbol_map.get("delisted", []))
    SYMBOL_OVERRIDES = symbol_map.get("overrides", {})
    
    logger.info(f"  ✓ {len(symbols)} companies to fetch")
    logger.info(f"  ✓ {len(DELISTED)} delisted excluded")
    
    logger.info("\nBuilding sector mapping...")
    SECTOR_MAPPING = build_sector_mapping(symbols)
    logger.info(f"  ✓ Sector mapping built: {len(SECTOR_MAPPING)} stocks")
    
    yahoof_store = {}
    processed = 0
    skipped = 0
    success_count = 0
    error_count = 0
    
    logger.info(f"\nFetching financial metrics...")
    for symbol in symbols:
        ticker = str(symbol["ticker"]).strip()
        
        if ticker in DELISTED or str(ticker).upper().startswith("SGB") or "BOND" in str(ticker).upper():
            skipped += 1
            continue
        
        sector = SECTOR_MAPPING.get(ticker, "Other")
        if ticker not in yahoof_store:
            yahoof_store[ticker] = {
                "ticker": ticker,
                "name": symbol.get("name"),
                "isin": symbol.get("isin"),
                "sector": sector,
                "observations": []
            }
        
        try:
            payload = fetch_financial_payload(ticker, sector, SYMBOL_OVERRIDES)
            yahoof_store[ticker]["observations"].append({
                "fetched_at": now(),
                "raw": payload
            })
            
            if payload.get("status") == "success":
                success_count += 1
            else:
                error_count += 1
            
        except Exception as e:
            error_count += 1
            yahoof_store[ticker]["observations"].append({
                "fetched_at": now(),
                "raw": {"error": str(e)}
            })
        
        processed += 1
        if processed % 20 == 0:
            logger.info(f"  Progress: {processed}/{len(symbols)-skipped}...")
    
    runtime = round(time.time() - start_time, 2)
    
    logger.info(f"\nSaving files...")
    save_json(YAHOOF_FILE, yahoof_store)
    logger.info(f"  ✓ Saved: {YAHOOF_FILE.resolve()}")
    
    logger.info("\n" + "="*80)
    logger.info("YAHOOF EXECUTION SUMMARY")
    logger.info("="*80)
    logger.info(f"Processed:  {processed} companies")
    logger.info(f"Skipped:    {skipped} (bonds/delisted)")
    logger.info(f"Success:    {success_count}")
    logger.info(f"Errors:     {error_count}")
    logger.info(f"Runtime:    {runtime}s")
    logger.info(f"Output:     {YAHOOF_FILE.resolve()}")
    logger.info(f"Log:        {LOG_FILE.resolve()}")
    logger.info("="*80)
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
