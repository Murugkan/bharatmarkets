#!/usr/bin/env python3
"""
INTRADAY Fetch
- Schedule: Every 1 hour during trading (09:15-16:30 IST)
- Data: Prices only (lightweight)
- File: intraday_yahoo_YYYY-MM-DD.json (temporary, purged daily)
- Log: intraday_yahoo_YYYYMMDD_HHMMSS.log
- Lifecycle: Temporary (recreated each day, purged after daily.py)
"""

import json
import logging
from pathlib import Path
from datetime import datetime, UTC
import yfinance as yf
import sys

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

TYPE = "intraday"
PROVIDER = "yahoo"
TODAY = datetime.now(UTC).strftime("%Y-%m-%d")

DATA_FILE = DATA_DIR / f"{TYPE}_{PROVIDER}_{TODAY}.json"
META_FILE = DATA_DIR / f"meta_{TYPE}_{PROVIDER}_{TODAY}.json"
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

def main():
    logger.info(f"\n{'='*60}")
    logger.info(f"{TYPE.upper()} - Prices (1-hour schedule)")
    logger.info(f"File: {DATA_FILE.name}")
    logger.info(f"Lifecycle: Temporary (purged after daily)")
    logger.info(f"{'='*60}\n")
    
    data = load_json(DATA_FILE)
    processed = 0
    failed = 0
    
    for ticker in SYMBOLS:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            if ticker not in data:
                data[ticker] = {"hourly_snapshots": []}
            
            data[ticker]["hourly_snapshots"].append({
                "timestamp": datetime.now(UTC).isoformat(),
                "price": info.get("currentPrice"),
                "volume": info.get("volume"),
                "change": info.get("regularMarketChangePercent"),
                "bid": info.get("bid"),
                "ask": info.get("ask"),
            })
            processed += 1
            
        except Exception as e:
            logger.debug(f"  {ticker}: {e}")
            failed += 1
    
    save_json(DATA_FILE, data)
    
    meta = {
        "timestamp": datetime.now(UTC).isoformat(),
        "type": TYPE,
        "provider": PROVIDER,
        "file": str(DATA_FILE),
        "lifecycle": "temporary (purged daily)",
        "processed": processed,
        "failed": failed,
        "total_snapshots": sum(len(t.get("hourly_snapshots", [])) for t in data.values()) if data else 0,
    }
    save_json(META_FILE, meta)
    
    logger.info(f"✓ {processed}/{len(SYMBOLS)} processed")
    logger.info(f"  File: {DATA_FILE.name}")
    logger.info(f"  Snapshots: {meta['total_snapshots']}")
    logger.info(f"  ℹ️  Purged after daily syncs\n")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
