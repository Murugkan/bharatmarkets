import json
import time
from pathlib import Path
from datetime import datetime
import logging

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

YAHOO_FILE = DATA_DIR / "yahoo-history.json"
SCREENER_FILE = DATA_DIR / "screener-history.json"
FINNHUB_FILE = DATA_DIR / "finnhub-history.json"
MERGED_FILE = DATA_DIR / "merged_fundamentals.json"

def setup_logging():
    """Setup logging to file"""
    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "merge-script.log"
    
    logger = logging.getLogger("STEP2-MERGE")
    logger.handlers.clear()  # Clear any existing handlers
    logger.setLevel(logging.INFO)
    logger.propagate = False
    
    # File handler
    fh = logging.FileHandler(log_file, mode='w', encoding='utf-8', delay=False)
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    return logger, log_file

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    logger, log_file = setup_logging()
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("STEP 2: MERGE & CONSOLIDATE MODULE")
    logger.info("=" * 80)
    logger.info("")
    
    logger.info("Verifying paths...")
    logger.info(f"  Working directory: {BASE_DIR}")
    logger.info(f"  DATA_DIR: {DATA_DIR}")
    
    logger.info(f"  Checking YAHOO_FILE: {YAHOO_FILE}")
    logger.info(f"    Exists: {YAHOO_FILE.exists()}")
    
    logger.info(f"  Checking SCREENER_FILE: {SCREENER_FILE}")
    logger.info(f"    Exists: {SCREENER_FILE.exists()}")
    
    logger.info(f"  Checking FINNHUB_FILE: {FINNHUB_FILE}")
    logger.info(f"    Exists: {FINNHUB_FILE.exists()}")
    
    # List what's actually in data directory
    if DATA_DIR.exists():
        logger.info(f"  Files in {DATA_DIR}:")
        for f in DATA_DIR.iterdir():
            logger.info(f"    - {f.name}")
    else:
        logger.error(f"  DATA_DIR does not exist: {DATA_DIR}")
        return
    
    if not YAHOO_FILE.exists():
        logger.error(f"ERROR: Yahoo file not found: {YAHOO_FILE}")
        return
    if not SCREENER_FILE.exists():
        logger.error(f"ERROR: Screener file not found: {SCREENER_FILE}")
        return
    if not FINNHUB_FILE.exists():
        logger.error(f"ERROR: Finnhub file not found: {FINNHUB_FILE}")
        return
    
    logger.info(f"  ✓ YAHOO_FILE: {YAHOO_FILE}")
    logger.info(f"  ✓ SCREENER_FILE: {SCREENER_FILE}")
    logger.info(f"  ✓ FINNHUB_FILE: {FINNHUB_FILE}")
    logger.info("")
    
    logger.info("Loading source files...")
    
    yahoo_data = load_json(YAHOO_FILE)
    screener_data = load_json(SCREENER_FILE)
    finnhub_data = load_json(FINNHUB_FILE)
    
    logger.info(f"  ✓ Yahoo: {len(yahoo_data)} tickers")
    logger.info(f"  ✓ Screener: {len(screener_data)} tickers")
    logger.info(f"  ✓ Finnhub: {len(finnhub_data)} tickers")
    logger.info("")
    
    logger.info("Consolidating data...")
    
    # Merge all tickers
    merged = {}
    
    try:
        for ticker in set(list(yahoo_data.keys()) + list(screener_data.keys()) + list(finnhub_data.keys())):
            merged[ticker] = {
                "ticker": ticker,
                "yahoo": yahoo_data.get(ticker, {}),
                "screener": screener_data.get(ticker, {}),
                "finnhub": finnhub_data.get(ticker, {})
            }
        
        logger.info(f"  ✓ Consolidated {len(merged)} tickers")
    except Exception as e:
        logger.error(f"ERROR during consolidation: {str(e)}")
        return
    
    logger.info("")
    
    logger.info("Saving merged file...")
    try:
        save_json(MERGED_FILE, merged)
        logger.info(f"  ✓ Saved: {MERGED_FILE}")
        logger.info(f"    File size: {MERGED_FILE.stat().st_size} bytes")
    except Exception as e:
        logger.error(f"ERROR saving merged file: {str(e)}")
        return
    
    logger.info("=" * 80)
    logger.info("STEP 2 SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Sources: Yahoo + Screener + Finnhub")
    logger.info(f"Tickers: {len(merged)}")
    logger.info(f"Output: {MERGED_FILE.name}")
    logger.info("=" * 80)

if __name__ == "__main__":
    main()
