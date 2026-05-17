#!/usr/bin/env python3
"""
YahooF Financial Metrics Extractor
===================================
Matches fetch_history.py engine structure EXACTLY
- Uses "ticker" field from unified-symbols.json
- Flat storage with ticker keys
- Observations array pattern
- 4-quarter raw historical data
"""

import json
import time
import logging
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime, UTC

# ============================================================================
# PATHS - All relative to current working directory (repository root)
# ============================================================================

DATA_DIR = Path('data')
SYMBOLS_FILE = Path('unified-symbols.json')
SYMBOL_MAP_FILE = Path('symbol_map.json')

# Output files
YAHOOF_FILE = DATA_DIR / "yahoof_financials_1.json"
LOG_FILE = DATA_DIR / "logs/yahoof_financials_1.log"

# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-10s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("YAHOOF-FIN")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def now():
    return datetime.now(UTC).isoformat()

def load_json(path):
    """Load JSON file safely"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Cannot load {path.name}: {e}")
        return {}

def save_json(path, data):
    """Save JSON file with pretty formatting"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def resolve_symbol(ticker, overrides):
    """Resolve symbol using override mapping"""
    if ticker in overrides:
        return overrides[ticker]
    if not any(ticker.endswith(ext) for ext in [".NS", ".BO"]):
        return f"{ticker}.NS"
    return ticker

def build_sector_mapping(symbols_list):
    """Build sector mapping dynamically from unified-symbols.json"""
    mapping = {}
    for symbol in symbols_list:
        ticker = str(symbol["ticker"]).strip()
        sector = symbol.get("sector") or symbol.get("industry") or symbol.get("group") or "Other"
        mapping[ticker] = sector
    return mapping

# ============================================================================
# FINANCIAL METRICS EXTRACTION
# ============================================================================

def safe_float(val):
    """Safe float conversion"""
    try:
        if pd.isna(val):
            return 0
        return float(val)
    except:
        return 0

def fetch_financial_payload(ticker, sector, symbol_overrides):
    """
    Fetch financial metrics from yfinance
    Returns: {"resolved_ticker", "sector", "metrics": {...}}
    Matches fetch_history.py structure EXACTLY
    """
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
        
        # ========== DEBT DETAILS (4 quarters) ==========
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
        
        # ========== EXCEPTIONAL ITEMS (4 quarters) ==========
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

def main():
    # Setup logging file
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
    
    # Load fetch configuration
    fetch_config = load_json(Path('.fetch_config.json'))
    FETCH_YAHOOF = fetch_config.get('yahoof', True)
    
    logger.info(f"\nProvider Configuration:")
    logger.info(f"  {'✓' if FETCH_YAHOOF else '✗'} YahooF Financial Metrics")
    
    # Verify paths
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
    
    # Load symbols and mappings
    logger.info("\nLoading configuration...")
    symbols_master = load_json(SYMBOLS_FILE)
    symbols = symbols_master.get("symbols", [])
    symbol_map = load_json(SYMBOL_MAP_FILE)
    
    DELISTED = set(symbol_map.get("delisted", []))
    SYMBOL_OVERRIDES = symbol_map.get("overrides", {})
    
    logger.info(f"  ✓ {len(symbols)} companies to fetch")
    logger.info(f"  ✓ {len(DELISTED)} delisted excluded")
    
    # Build sector mapping
    logger.info("\nBuilding sector mapping...")
    SECTOR_MAPPING = build_sector_mapping(symbols)
    logger.info(f"  ✓ Sector mapping built: {len(SECTOR_MAPPING)} stocks")
    unique_sectors = set(SECTOR_MAPPING.values())
    logger.info(f"  ✓ Unique sectors: {', '.join(sorted(unique_sectors))}")
    
    # Initialize store
    yahoof_store = {}
    
    processed = 0
    skipped = 0
    success_count = 0
    error_count = 0
    
    # Fetch financial data
    logger.info(f"\nFetching financial metrics...")
    for symbol in symbols:
        ticker = str(symbol["ticker"]).strip()
        
        # Skip delisted and bonds
        if ticker in DELISTED:
            skipped += 1
            continue
        
        if str(ticker).upper().startswith("SGB") or "BOND" in str(ticker).upper():
            skipped += 1
            continue
        
        # Initialize ticker store
        sector = SECTOR_MAPPING.get(ticker, "Other")
        if ticker not in yahoof_store:
            yahoof_store[ticker] = {
                "ticker": ticker,
                "name": symbol.get("name"),
                "isin": symbol.get("isin"),
                "sector": sector,
                "observations": []
            }
        
        # Fetch financial payload
        try:
            payload = fetch_financial_payload(ticker, sector, SYMBOL_OVERRIDES)
            yahoof_store[ticker]["observations"].append({
                "fetched_at": now(),
                "raw": payload
            })
            
            if payload.get("metrics", {}).get("status") == "success":
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
    
    # Save output
    logger.info(f"\nSaving files...")
    logger.info(f"  Current directory: {Path.cwd()}")
    
    save_json(YAHOOF_FILE, yahoof_store)
    logger.info(f"  ✓ Saved: {YAHOOF_FILE.resolve()}")
    
    # Summary
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
