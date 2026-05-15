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
MERGED_FILE = BASE_DIR / "merged_fundamentals.json"

def setup_logging():
    """Setup logging to file"""
    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "merge-script.log"
    
    logger = logging.getLogger("STEP2-MERGE")
    logger.setLevel(logging.INFO)
    
    # File handler
    fh = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    return logger

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
    logger = setup_logging()
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("STEP 2: MERGE & CONSOLIDATE MODULE")
    logger.info("=" * 80)
    logger.info("")
    
    logger.info("Verifying paths...")
    logger.info(f"  Working directory: {BASE_DIR}")
    logger.info(f"  DATA_DIR: {DATA_DIR}")
    
    if not YAHOO_FILE.exists():
        logger.error(f"Yahoo file not found: {YAHOO_FILE}")
        return
    if not SCREENER_FILE.exists():
        logger.error(f"Screener file not found: {SCREENER_FILE}")
        return
    if not FINNHUB_FILE.exists():
        logger.error(f"Finnhub file not found: {FINNHUB_FILE}")
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
    
    for ticker in set(list(yahoo_data.keys()) + list(screener_data.keys()) + list(finnhub_data.keys())):
        merged[ticker] = {
            "ticker": ticker,
            "yahoo": yahoo_data.get(ticker, {}),
            "screener": screener_data.get(ticker, {}),
            "finnhub": finnhub_data.get(ticker, {})
        }
    
    logger.info(f"  ✓ Consolidated {len(merged)} tickers")
    logger.info("")
    
    logger.info("Saving merged file...")
    save_json(MERGED_FILE, merged)
    logger.info(f"  ✓ {MERGED_FILE.name}")
    logger.info("")
    
    logger.info("=" * 80)
    logger.info("STEP 2 SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Sources: Yahoo + Screener + Finnhub")
    logger.info(f"Tickers: {len(merged)}")
    logger.info(f"Output: {MERGED_FILE.name}")
    logger.info("=" * 80)

if __name__ == "__main__":
    main()
