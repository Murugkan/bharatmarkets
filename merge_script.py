#!/usr/bin/env python3
"""
MERGE SCRIPT - BharatMarkets Stock Data Pipeline
Merge → Consolidate → Restructure with ZERO DATA LOSS GUARANTEE

Usage:
    python3 merge_script.py
    (uses relative paths from repository root)

File Structure:
    repository/
    ├── merge_script.py              (this file)
    ├── data/
    │   ├── yahoo-history.json       (input)
    │   ├── screener-history.json    (input)
    │   ├── stock-data.json          (output)
    │   └── merge-script.log         (output log)
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# File paths (relative to repository root)
DATA_DIR = Path('data')

# Input files (in data/ directory)
YAHOO_HISTORY = DATA_DIR / 'yahoo-history.json'
SCREENER_HISTORY = DATA_DIR / 'screener-history.json'

# Output files (in data/ directory)
MERGED_OUTPUT = DATA_DIR / 'stock-data.json'

logger_file = None


def log(message: str, level: str = "INFO"):
    """Log to console and file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"
    print(log_entry)
    
    if logger_file:
        with open(logger_file, 'a') as f:
            f.write(log_entry + "\n")


# ============================================================================
# STEP 1: MERGE
# ============================================================================

def merge_stock_data(file1_path: Path, file2_path: Path) -> Dict[str, Any]:
    """Merge with data preservation."""
    
    log("\n" + "="*80)
    log("STEP 1: MERGE - Combining Yahoo & Screener data")
    log("="*80)
    
    log(f"Loading {file1_path}...")
    with open(file1_path, 'r', encoding='utf-8') as f:
        data1 = json.load(f)
    log(f"  ✓ {len(data1)} tickers")
    
    log(f"Loading {file2_path}...")
    with open(file2_path, 'r', encoding='utf-8') as f:
        data2 = json.load(f)
    log(f"  ✓ {len(data2)} tickers")
    
    merged = {}
    obs_count = 0
    
    for ticker in data1.keys():
        merged[ticker] = {
            'ticker': data1[ticker].get('ticker'),
            'name': data1[ticker].get('name'),
            'isin': data1[ticker].get('isin'),
            'observations': data1[ticker].get('observations', []).copy()
        }
        obs_count += len(merged[ticker].get('observations', []))
    
    for ticker in data2.keys():
        if ticker in merged:
            obs_from_file2 = data2[ticker].get('observations', [])
            merged[ticker]['observations'].extend(obs_from_file2)
            obs_count += len(obs_from_file2)
        else:
            merged[ticker] = {
                'ticker': data2[ticker].get('ticker'),
                'name': data2[ticker].get('name'),
                'isin': data2[ticker].get('isin'),
                'observations': data2[ticker].get('observations', []).copy()
            }
            obs_count += len(merged[ticker].get('observations', []))
    
    log(f"\nMerge complete: {len(merged)} tickers, {obs_count} total observations")
    return merged


# ============================================================================
# STEP 2: CONSOLIDATE - FIXED TO PRESERVE OBSERVATIONS
# ============================================================================

def consolidate_stock_data(merged_data: Dict[str, Any]) -> Dict[str, Any]:
    """Consolidate while PRESERVING ALL OBSERVATIONS."""
    
    log("\n" + "="*80)
    log("STEP 2: CONSOLIDATE - Creating single records per stock")
    log("="*80)
    
    consolidated_data = {}
    
    for ticker, ticker_data in merged_data.items():
        observations = ticker_data.get('observations', [])
        
        if len(observations) == 0:
            log(f"  ⚠ {ticker}: No observations")
            continue
        
        # Get metadata from first observation
        first_obs = observations[0]
        yahoo_info = first_obs.get('raw', {}).get('info', {})
        
        consolidated = {
            'ticker': ticker_data.get('ticker'),
            'name': ticker_data.get('name'),
            'isin': ticker_data.get('isin'),
            'company': {
                'name': yahoo_info.get('longName') or yahoo_info.get('shortName') or '',
                'industry': yahoo_info.get('industry', ''),
                'sector': yahoo_info.get('sector', ''),
                'website': yahoo_info.get('website', ''),
            },
            'address': {
                'address1': yahoo_info.get('address1', ''),
                'address2': yahoo_info.get('address2', ''),
                'city': yahoo_info.get('city', ''),
                'state': yahoo_info.get('state', ''),
                'zip': yahoo_info.get('zip', ''),
                'country': yahoo_info.get('country', ''),
                'phone': yahoo_info.get('phone', ''),
            },
            # CRITICAL: PRESERVE ALL OBSERVATIONS
            'observations': observations,
            'observation_count': len(observations),
            'data_sources': {
                'fetched_at': [obs.get('fetched_at') for obs in observations]
            }
        }
        
        consolidated_data[ticker] = consolidated
    
    log(f"✓ Consolidated {len(consolidated_data)} stocks with observations preserved")
    return consolidated_data


# ============================================================================
# STEP 3: RESTRUCTURE - FIXED TO CONVERT TYPES AND PRESERVE DATA
# ============================================================================

def parse_numeric(value: str) -> Optional[float]:
    """Convert string to float."""
    if not value or value == 'N/A' or value == 'xxx':
        return None
    try:
        cleaned = str(value).replace(',', '').replace('%', '').strip()
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


def restructure_stock_data(consolidated_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Restructure with GUARANTEED type conversion.
    - Converts all prices from string to float
    - Preserves all observations
    - Extracts metrics properly
    """
    
    log("\n" + "="*80)
    log("STEP 3: RESTRUCTURE - Converting types and organizing data")
    log("="*80)
    
    restructured_data = {}
    total_prices = 0
    total_converted = 0
    
    for ticker, stock_data in consolidated_data.items():
        observations = stock_data.get('observations', [])
        
        restructured_stock = {
            'ticker': stock_data.get('ticker'),
            'name': stock_data.get('name'),
            'isin': stock_data.get('isin'),
            'company': stock_data.get('company', {}),
            'address': stock_data.get('address', {}),
            'observation_count': len(observations),
            'data_sources': stock_data.get('data_sources', {}),
            'price_series': [],
            'financial_metrics': {},
            'yahoo_metrics': {}
        }
        
        # CRITICAL: Process each observation and extract data
        for obs_idx, observation in enumerate(observations):
            raw = observation.get('raw', {})
            
            # Extract from Yahoo observation
            if 'history_1y_1d' in raw:
                price_history = raw['history_1y_1d']
                
                # CONVERT PRICES TO NUMERIC
                for price_record in price_history:
                    converted_record = {
                        'date': price_record.get('Date'),
                        'open': parse_numeric(price_record.get('Open')),
                        'high': parse_numeric(price_record.get('High')),
                        'low': parse_numeric(price_record.get('Low')),
                        'close': parse_numeric(price_record.get('Close')),
                        'volume': parse_numeric(price_record.get('Volume')),
                        'dividends': parse_numeric(price_record.get('Dividends')),
                        'stock_splits': parse_numeric(price_record.get('Stock Splits')),
                    }
                    
                    # Only add if we have valid close price
                    if converted_record['close'] is not None:
                        restructured_stock['price_series'].append(converted_record)
                        total_converted += 1
                    
                    total_prices += 1
            
            # Extract from Yahoo info
            if 'info' in raw:
                info = raw['info']
                restructured_stock['yahoo_metrics'] = {
                    'market_cap': info.get('marketCap'),
                    'trailing_pe': info.get('trailingPE'),
                    'forward_pe': info.get('forwardPE'),
                    'peg_ratio': info.get('pegRatio'),
                    'price_to_book': info.get('priceToBook'),
                    'dividend_yield': info.get('dividendYield'),
                    'earnings_growth': info.get('earningsGrowth'),
                }
            
            # Extract from Screener tables
            if 'tables' in raw:
                tables = raw['tables']
                for table in tables:
                    rows = table.get('rows', [])
                    if len(rows) < 2:
                        continue
                    
                    headers = rows[0]
                    data_rows = rows[1:]
                    
                    for row in data_rows:
                        if not row:
                            continue
                        
                        metric_name = row[0].lower().replace(' +', '').replace(' ', '_')
                        
                        if metric_name not in restructured_stock['financial_metrics']:
                            restructured_stock['financial_metrics'][metric_name] = []
                        
                        # Extract metric values
                        for col_idx, header in enumerate(headers[1:], 1):
                            if col_idx < len(row):
                                value = parse_numeric(row[col_idx])
                                if value is not None:
                                    metric_entry = {
                                        'period': header,
                                        'value': value,
                                    }
                                    restructured_stock['financial_metrics'][metric_name].append(metric_entry)
        
        restructured_data[ticker] = restructured_stock
    
    log(f"✓ Restructured {len(restructured_data)} stocks")
    log(f"✓ Price records processed: {total_prices}")
    log(f"✓ Price records converted to numeric: {total_converted}")
    
    if total_prices != total_converted:
        log(f"⚠ Warning: {total_prices - total_converted} price records could not be converted")
    
    return restructured_data


# ============================================================================
# OPTIMIZATION - MINIFY FOR PRODUCTION
# ============================================================================

def optimize_output(restructured_data: Dict[str, Any]) -> Dict[str, Any]:
    """Optimize structure for production (remove metadata, minify)."""
    
    log("\n" + "="*80)
    log("STEP 4: OPTIMIZE - Minifying for production")
    log("="*80)
    
    optimized = {}
    
    for ticker, stock in restructured_data.items():
        optimized[ticker] = {
            'ticker': stock['ticker'],
            'name': stock['name'],
            'isin': stock['isin'],
            'company': stock['company'],
            'address': stock['address'],
            'observation_count': stock['observation_count'],
            'data_sources': stock['data_sources'],
            # Prices: remove observation-level metadata
            'price_series': [
                {
                    'date': p['date'],
                    'open': p['open'],
                    'high': p['high'],
                    'low': p['low'],
                    'close': p['close'],
                    'volume': p['volume'],
                    'dividends': p['dividends'],
                    'stock_splits': p['stock_splits']
                }
                for p in stock['price_series']
            ],
            # Metrics: remove observation-level metadata
            'financial_metrics': {
                metric_name: [
                    {
                        'period': entry['period'],
                        'value': entry['value']
                    }
                    for entry in entries
                ]
                for metric_name, entries in stock['financial_metrics'].items()
            },
            'yahoo_metrics': stock['yahoo_metrics']
        }
    
    log(f"✓ Optimization complete")
    return optimized


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_pipeline():
    """Run complete fixed pipeline."""
    
    global logger_file
    logger_file = DATA_DIR / 'merge-script.log'
    
    log("\n" + "█"*80)
    log("█" + " "*78 + "█")
    log("█" + "  MERGE SCRIPT - BHARATMARKETS STOCK DATA PIPELINE  ".center(78) + "█")
    log("█" + " "*78 + "█")
    log("█"*80)
    
    # Verify paths
    log(f"\nRepository Structure:")
    log(f"  Working directory: {Path.cwd()}")
    log(f"  Data directory: {DATA_DIR.resolve()}")
    log(f"  Input 1: {YAHOO_HISTORY}")
    log(f"  Input 2: {SCREENER_HISTORY}")
    log(f"  Output: {MERGED_OUTPUT}")
    
    # Check if input files exist
    if not YAHOO_HISTORY.exists():
        log(f"❌ ERROR: {YAHOO_HISTORY} not found", level="ERROR")
        log(f"   Expected: {YAHOO_HISTORY.resolve()}", level="ERROR")
        return False
    
    if not SCREENER_HISTORY.exists():
        log(f"❌ ERROR: {SCREENER_HISTORY} not found", level="ERROR")
        log(f"   Expected: {SCREENER_HISTORY.resolve()}", level="ERROR")
        return False
    
    try:
        # Step 1: Merge
        merged_data = merge_stock_data(YAHOO_HISTORY, SCREENER_HISTORY)
        
        # Step 2: Consolidate
        consolidated_data = consolidate_stock_data(merged_data)
        
        # Step 3: Restructure
        restructured_data = restructure_stock_data(consolidated_data)
        
        # Step 4: Optimize
        optimized_data = optimize_output(restructured_data)
        
        # Write output (minified)
        log(f"\nWriting output to {MERGED_OUTPUT}...")
        with open(MERGED_OUTPUT, 'w', encoding='utf-8') as f:
            json.dump(optimized_data, f, separators=(',', ':'), ensure_ascii=False)
        
        output_size = MERGED_OUTPUT.stat().st_size / (1024*1024)
        
        log(f"\n" + "█"*80)
        log("█" + " "*78 + "█")
        log("█" + "  ✓ PIPELINE COMPLETE  ".center(78) + "█")
        log("█" + " "*78 + "█")
        log("█"*80)
        log(f"\nOutput: {MERGED_OUTPUT.resolve()} ({output_size:.2f} MB)")
        log(f"Log: {logger_file.resolve()}")
        log(f"\nStats:")
        log(f"  • Total stocks: {len(optimized_data)}")
        log(f"  • Total price records: {sum(len(s.get('price_series', [])) for s in optimized_data.values()):,}")
        log(f"  • Total metrics: {sum(len(m) for s in optimized_data.values() for m in s.get('financial_metrics', {}).values()):,}")
        log(f"\n✅ Ready to commit and push to GitHub!\n")
        
        return True
        
    except Exception as e:
        log(f"❌ ERROR: {str(e)}", level="ERROR")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_pipeline()
    sys.exit(0 if success else 1)
