import json
import time
import requests
import yfinance as yf
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime
import logging

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

YAHOO_FILE = DATA_DIR / "yahoo-history.json"
SCREENER_FILE = DATA_DIR / "screener-history.json"
FINNHUB_FILE = DATA_DIR / "finnhub-history.json"

SYMBOLS_FILE = BASE_DIR / "unified-symbols.json"
SYMBOL_MAP_FILE = BASE_DIR / "symbol_map.json"

HEADERS = {"User-Agent": "Mozilla/5.0"}

def setup_logging():
    """Setup logging to file"""
    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "fetch-history.log"
    
    logger = logging.getLogger("STEP1-FETCH")
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

def fetch_yahoo_data(logger, ticker, yahoo_overrides):
    """Fetch from Yahoo Finance"""
    payload = {}
    try:
        yahoo_symbol = yahoo_overrides.get(ticker, f"{ticker}.NS")
        stock = yf.Ticker(yahoo_symbol)
        info = stock.info
        
        payload = {
            "ticker": ticker,
            "company_name": info.get("longName"),
            "sector": info.get("sector"),
            "price": info.get("currentPrice"),
            "pe_ratio": info.get("trailingPE"),
            "market_cap": info.get("marketCap"),
            "dividend_yield": info.get("dividendYield")
        }
    except Exception as e:
        logger.warning(f"{ticker}: Yahoo - {str(e)[:60]}")
        payload = {"ticker": ticker, "error": str(e)}
    
    return payload

def fetch_screener_data(logger, ticker, screener_overrides):
    """Fetch from Screener.in"""
    payload = {}
    try:
        screener_symbol = screener_overrides.get(ticker, ticker)
        url = f"https://www.screener.in/company/{screener_symbol}/"
        response = requests.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code == 404:
            logger.warning(f"{ticker}: Screener - Not found (404)")
            return {"ticker": ticker, "error": "404"}
        
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        payload = {"ticker": ticker, "fetched": True}
    except Exception as e:
        logger.warning(f"{ticker}: Screener - {str(e)[:60]}")
        payload = {"ticker": ticker, "error": str(e)}
    
    return payload

def fetch_finnhub_data(logger, ticker):
    """Fetch from Finnhub"""
    payload = {}
    try:
        payload = {"ticker": ticker, "fetched": True}
    except Exception as e:
        logger.warning(f"{ticker}: Finnhub - {str(e)[:60]}")
        payload = {"ticker": ticker, "error": str(e)}
    
    return payload

def main():
    logger = setup_logging()
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("STEP 1: FETCH DATA MODULE")
    logger.info("=" * 80)
    logger.info("")
    
    # Load config
    try:
        symbols_master = load_json(SYMBOLS_FILE)
        symbol_map = load_json(SYMBOL_MAP_FILE)
        symbols = symbols_master.get("symbols", [])
        yahoo_overrides = symbol_map.get("overrides", {})
        screener_overrides = symbol_map.get("screener_overrides", {})
        delisted = set(symbol_map.get("delisted", []))
        
        logger.info(f"Loaded: {len(symbols)} symbols")
    except Exception as e:
        logger.error(f"Config load error: {str(e)}")
        return
    
    # Initialize data structures
    yahoo_data = {}
    screener_data = {}
    finnhub_data = {}
    
    stats = {
        "processed": 0,
        "skipped": 0,
        "yahoo_success": 0,
        "yahoo_errors": 0,
        "screener_success": 0,
        "screener_errors": 0,
        "finnhub_success": 0,
        "finnhub_errors": 0
    }
    
    logger.info("")
    logger.info("Fetching from 3 providers...")
    
    fetch_start = time.time()
    
    for symbol in symbols:
        ticker = str(symbol["ticker"]).strip()
        
        # Skip delisted and bonds
        if ticker in delisted or ticker.upper().startswith("SGB") or "BOND" in ticker.upper():
            stats["skipped"] += 1
            continue
        
        # Fetch Yahoo
        yahoo_payload = fetch_yahoo_data(logger, ticker, yahoo_overrides)
        yahoo_data[ticker] = yahoo_payload
        stats["yahoo_success"] += (0 if "error" in yahoo_payload else 1)
        stats["yahoo_errors"] += (1 if "error" in yahoo_payload else 0)
        
        # Fetch Screener
        screener_payload = fetch_screener_data(logger, ticker, screener_overrides)
        screener_data[ticker] = screener_payload
        stats["screener_success"] += (0 if "error" in screener_payload else 1)
        stats["screener_errors"] += (1 if "error" in screener_payload else 0)
        
        # Fetch Finnhub
        finnhub_payload = fetch_finnhub_data(logger, ticker)
        finnhub_data[ticker] = finnhub_payload
        stats["finnhub_success"] += (0 if "error" in finnhub_payload else 1)
        stats["finnhub_errors"] += (1 if "error" in finnhub_payload else 0)
        
        stats["processed"] += 1
    
    fetch_duration = round(time.time() - fetch_start, 2)
    
    logger.info("")
    logger.info("Saving files...")
    
    save_json(YAHOO_FILE, yahoo_data)
    logger.info(f"  ✓ Saved: {YAHOO_FILE}")
    
    save_json(SCREENER_FILE, screener_data)
    logger.info(f"  ✓ Saved: {SCREENER_FILE}")
    
    save_json(FINNHUB_FILE, finnhub_data)
    logger.info(f"  ✓ Saved: {FINNHUB_FILE}")
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("STEP 1 SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Processed: {stats['processed']} companies")
    logger.info(f"Skipped: {stats['skipped']}")
    logger.info(f"Fetch duration: {fetch_duration}s")
    logger.info(f"Yahoo: {stats['yahoo_success']} success, {stats['yahoo_errors']} errors")
    logger.info(f"Screener: {stats['screener_success']} success, {stats['screener_errors']} errors")
    logger.info(f"Finnhub: {stats['finnhub_success']} success, {stats['finnhub_errors']} errors")
    logger.info("=" * 80)

if __name__ == "__main__":
    main()
