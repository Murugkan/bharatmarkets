import json
import time
from pathlib import Path
from datetime import datetime, UTC
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
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    
    # File handler
    fh = logging.FileHandler(log_file, mode='w', encoding='utf-8', delay=False)
    fh.setLevel(logging.WARNING)
    formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
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
    
    # Verify paths
    if not DATA_DIR.exists():
        logger.error(f"DATA_DIR does not exist: {DATA_DIR}")
        return
    
    if not YAHOO_FILE.exists():
        logger.error(f"Yahoo file not found: {YAHOO_FILE}")
        return
    if not SCREENER_FILE.exists():
        logger.error(f"Screener file not found: {SCREENER_FILE}")
        return
    if not FINNHUB_FILE.exists():
        logger.error(f"Finnhub file not found: {FINNHUB_FILE}")
        return
    
    # Load source files
    yahoo_data = load_json(YAHOO_FILE)
    screener_data = load_json(SCREENER_FILE)
    finnhub_data = load_json(FINNHUB_FILE)
    
    # Merge all tickers with timestamp
    merged = {
        "updated_at": datetime.now(UTC).isoformat()
    }
    
    try:
        for ticker in set(list(yahoo_data.keys()) + list(screener_data.keys()) + list(finnhub_data.keys())):
            merged[ticker] = {
                "ticker": ticker,
                "yahoo": yahoo_data.get(ticker, {}),
                "screener": screener_data.get(ticker, {}),
                "finnhub": finnhub_data.get(ticker, {})
            }
    except Exception as e:
        logger.error(f"ERROR during consolidation: {str(e)}")
        return
    
    # Save merged file
    try:
        save_json(MERGED_FILE, merged)
    except Exception as e:
        logger.error(f"ERROR saving merged file: {str(e)}")
        return
    
    # Print summary to console
    print(f"✓ Merge complete: {len(merged) - 1} tickers consolidated")
    print(f"✓ Updated at: {merged['updated_at']}")
    print(f"✓ Output: {MERGED_FILE.name}")

if __name__ == "__main__":
    main()
