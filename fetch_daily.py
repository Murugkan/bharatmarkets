#!/usr/bin/env python3
"""
DAILY Fetch
- Schedule: Once daily after market close (16:00 IST = 10:30 UTC)
- Data: Prices (1Y history) + All fundamentals
- Files: daily_yahoo_prices.json, daily_yahoo_fundamentals.json (permanent)
- Log: daily_yahoo_YYYYMMDD_HHMMSS.log
- Also: Purges intraday_yahoo_*.json files
"""

import json
import logging
from pathlib import Path
from datetime import datetime, UTC
import yfinance as yf
import sys
import glob

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

TYPE = "daily"
PROVIDER = "yahoo"

PRICES_FILE = DATA_DIR / f"{TYPE}_{PROVIDER}_prices.json"
FUNDAMENTALS_FILE = DATA_DIR / f"{TYPE}_{PROVIDER}_fundamentals.json"
META_PRICES = DATA_DIR / f"meta_{TYPE}_{PROVIDER}_prices.json"
META_FUNDAMENTALS = DATA_DIR / f"meta_{TYPE}_{PROVIDER}_fundamentals.json"
LOG_FILE = DATA_DIR / f"{TYPE}_{PROVIDER}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger()

with open(BASE_DIR / "symbol_list.json") as f:
    SYMBOLS = json.load(f).get("symbols", [])

def load_json(filepath):
    if filepath.exists():
        with open(filepath) as f:
            return json.load(f)
    return {}

def save_json(filepath, data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def purge_intraday():
    """Delete temporary intraday files"""
    logger.info("\nCleaning up intraday files...")
    
    files = glob.glob(str(DATA_DIR / f"intraday_{PROVIDER}_*.json"))
    files += glob.glob(str(DATA_DIR / f"meta_intraday_{PROVIDER}_*.json"))
    
    deleted = 0
    for file in files:
        try:
            Path(file).unlink()
            logger.info(f"  Purged: {Path(file).name}")
            deleted += 1
        except Exception as e:
            logger.warning(f"  Could not delete {Path(file).name}: {e}")
    
    if deleted > 0:
        logger.info(f"✓ Purged {deleted} intraday files")

def main():
    logger.info(f"\n{'='*60}")
    logger.info(f"{TYPE.upper()} - Comprehensive Sync (After market close)")
    logger.info(f"Schedule: 16:00 IST (10:30 UTC)")
    logger.info(f"{'='*60}\n")
    
    # PRICES
    logger.info("1. Syncing prices (1-year history)...")
    prices_data = load_json(PRICES_FILE)
    prices_ok = 0
    prices_failed = 0
    
    for ticker in SYMBOLS:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            
            if not hist.empty:
                if ticker not in prices_data:
                    prices_data[ticker] = {"observations": []}
                
                prices_data[ticker]["observations"].append({
                    "timestamp": datetime.now(UTC).isoformat(),
                    "data": {
                        "history": hist[["Open", "High", "Low", "Close", "Volume"]].to_dict(orient="records"),
                        "current_price": stock.info.get("currentPrice"),
                    }
                })
                prices_ok += 1
            else:
                prices_failed += 1
                
        except Exception as e:
            logger.debug(f"  {ticker}: {e}")
            prices_failed += 1
    
    save_json(PRICES_FILE, prices_data)
    save_json(META_PRICES, {
        "timestamp": datetime.now(UTC).isoformat(),
        "type": TYPE,
        "provider": PROVIDER,
        "scope": "prices",
        "schedule": "Daily after market close",
        "processed": prices_ok,
        "failed": prices_failed,
    })
    logger.info(f"✓ Prices: {prices_ok} synced")
    
    # FUNDAMENTALS
    logger.info("\n2. Syncing fundamentals (all fields)...")
    fundamentals_data = load_json(FUNDAMENTALS_FILE)
    fundamentals_ok = 0
    fundamentals_failed = 0
    
    for ticker in SYMBOLS:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            if ticker not in fundamentals_data:
                fundamentals_data[ticker] = {"observations": []}
            
            fundamentals_data[ticker]["observations"].append({
                "timestamp": datetime.now(UTC).isoformat(),
                "data": {
                    "revenue": info.get("totalRevenue"),
                    "eps": info.get("trailingEps"),
                    "pe": info.get("forwardPE"),
                    "pb": info.get("priceToBook"),
                    "ps": info.get("priceToSalesTrailing12Months"),
                    "roe": info.get("returnOnEquity"),
                    "roa": info.get("returnOnAssets"),
                    "debt_equity": info.get("debtToEquity"),
                    "profit_margin": info.get("profitMargins"),
                    "operating_margin": info.get("operatingMargins"),
                    "gross_margin": info.get("grossMargins"),
                    "market_cap": info.get("marketCap"),
                    "enterprise_value": info.get("enterpriseValue"),
                    "current_ratio": info.get("currentRatio"),
                    "quick_ratio": info.get("quickRatio"),
                    "total_debt": info.get("totalDebt"),
                    "total_cash": info.get("totalCash"),
                    "free_cash_flow": info.get("freeCashflow"),
                }
            })
            fundamentals_ok += 1
            
        except Exception as e:
            logger.debug(f"  {ticker}: {e}")
            fundamentals_failed += 1
    
    save_json(FUNDAMENTALS_FILE, fundamentals_data)
    save_json(META_FUNDAMENTALS, {
        "timestamp": datetime.now(UTC).isoformat(),
        "type": TYPE,
        "provider": PROVIDER,
        "scope": "fundamentals",
        "schedule": "Daily after market close",
        "processed": fundamentals_ok,
        "failed": fundamentals_failed,
    })
    logger.info(f"✓ Fundamentals: {fundamentals_ok} synced")
    
    # PURGE INTRADAY
    purge_intraday()
    
    logger.info(f"\n{'='*60}")
    logger.info(f"✓ {TYPE.upper()} SYNC COMPLETE")
    logger.info(f"  Prices: {prices_ok} observations")
    logger.info(f"  Fundamentals: {fundamentals_ok} observations")
    logger.info(f"  Cleaned: Intraday files purged")
    logger.info(f"{'='*60}\n")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
