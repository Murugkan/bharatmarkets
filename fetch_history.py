import json
import time
import requests
import yfinance as yf
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime, UTC
import logging
import sys

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

YAHOO_HISTORY = DATA_DIR / "history_yahoo.json"
SCREENER_HISTORY = DATA_DIR / "history_screener.json"

SYMBOLS_FILE = BASE_DIR / "unified-symbols.json"
SYMBOL_MAP_FILE = BASE_DIR / "symbol_map.json"

HEADERS = {"User-Agent": "Mozilla/5.0"}

def setup_logging(trading_date):
    """Setup WARNING+ logging"""
    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"history_{log_timestamp}.log"
    
    logger = logging.getLogger("history_fetch")
    logger.setLevel(logging.WARNING)
    
    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.WARNING)
    file_format = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(file_format)
    
    logger.addHandler(file_handler)
    return logger, log_file

def now():
    return datetime.now(UTC).isoformat()

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

def find_last_trading_day(logger, sample_ticker="RELIANCE"):
    """Find the most recent trading day with volume"""
    try:
        symbol_map = load_json(SYMBOL_MAP_FILE)
        yahoo_overrides = symbol_map.get("overrides", {})
        yahoo_symbol = yahoo_overrides.get(sample_ticker, f"{sample_ticker}.NS")
        stock = yf.Ticker(yahoo_symbol)
        hist = stock.history(period="15d", interval="1d")
        trading_days = hist[hist["Volume"] > 0].sort_index(ascending=False)
        return trading_days.index[0].strftime("%Y-%m-%d") if not trading_days.empty else None
    except Exception as e:
        logger.error(f"Failed to find trading day: {str(e)}")
        return None

def fetch_yahoo_5year(logger, ticker, yahoo_overrides):
    """Fetch 5 years of Yahoo data - Returns arrays directly (no merge needed)"""
    payload = {}
    try:
        yahoo_symbol = yahoo_overrides.get(ticker, f"{ticker}.NS")
        stock = yf.Ticker(yahoo_symbol)
        info = stock.info
        hist = stock.history(period="5y", interval="1d")
        
        if hist.empty:
            logger.warning(f"{ticker}: Yahoo - No 5-year history")
            return payload
        
        # Extract metadata (non-time-bound)
        payload["metadata"] = {
            "company_name": info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "exchange": info.get("exchange"),
            "currency": info.get("currency"),
            "isin": info.get("isin"),
            "website": info.get("website")
        }
        
        # Build time-series arrays directly
        payload["fields"] = {
            "price": [],
            "volume": [],
            "open": [],
            "high": [],
            "low": [],
            "pe_ratio": []
        }
        
        # Populate arrays with all historical data
        for date_idx, row in hist.iterrows():
            date_str = date_idx.strftime("%Y-%m-%d")
            
            payload["fields"]["price"].append({
                "date": date_str,
                "value": float(row["Close"])
            })
            payload["fields"]["volume"].append({
                "date": date_str,
                "value": int(row["Volume"])
            })
            payload["fields"]["open"].append({
                "date": date_str,
                "value": float(row["Open"])
            })
            payload["fields"]["high"].append({
                "date": date_str,
                "value": float(row["High"])
            })
            payload["fields"]["low"].append({
                "date": date_str,
                "value": float(row["Low"])
            })
        
        # Add latest PE ratio (only latest date)
        latest_date = hist.index[-1].strftime("%Y-%m-%d")
        pe = info.get("trailingPE")
        if pe:
            payload["fields"]["pe_ratio"].append({
                "date": latest_date,
                "value": pe
            })
        
    except requests.exceptions.Timeout:
        logger.warning(f"{ticker}: Yahoo - Connection timeout")
        payload["error"] = "timeout"
    except requests.exceptions.ConnectionError:
        logger.warning(f"{ticker}: Yahoo - Connection error")
        payload["error"] = "connection_error"
    except Exception as e:
        logger.warning(f"{ticker}: Yahoo - {type(e).__name__}: {str(e)[:80]}")
        payload["error"] = str(e)
    
    return payload

def fetch_screener_latest(logger, ticker, screener_overrides):
    """Fetch latest Screener data - Returns arrays with today's date"""
    payload = {}
    try:
        screener_symbol = screener_overrides.get(ticker, ticker)
        url = f"https://www.screener.in/company/{screener_symbol}/"
        response = requests.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code == 404:
            logger.warning(f"{ticker}: Screener - Not found (404)")
            return payload
        
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Extract sector (metadata)
        sector_elem = soup.select_one("[data-field='sector']")
        payload["metadata"] = {
            "sector": sector_elem.text.strip() if sector_elem else None
        }
        
        # Extract financial tables as time-series with today's date
        payload["fields"] = {}
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        
        for section in soup.select("section"):
            table = section.select_one("table")
            if table:
                heading = section.select_one("h2")
                section_name = heading.text.strip() if heading else "unknown"
                
                for tr in table.select("tr"):
                    cols = tr.select("td")
                    if len(cols) >= 2:
                        field_name = cols[0].text.strip()
                        field_value = cols[1].text.strip()
                        field_key = f"{section_name}_{field_name}"
                        
                        # Initialize field array if needed
                        if field_key not in payload["fields"]:
                            payload["fields"][field_key] = []
                        
                        # Append as time-series entry
                        payload["fields"][field_key].append({
                            "date": today,
                            "value": field_value
                        })
        
    except requests.exceptions.Timeout:
        logger.warning(f"{ticker}: Screener - Connection timeout")
        payload["error"] = "timeout"
    except requests.exceptions.ConnectionError:
        logger.warning(f"{ticker}: Screener - Connection error")
        payload["error"] = "connection_error"
    except Exception as e:
        logger.warning(f"{ticker}: Screener - {type(e).__name__}: {str(e)[:80]}")
        payload["error"] = str(e)
    
    return payload

def main():
    script_start = time.time()
    
    # Find trading date
    logger_temp = logging.getLogger("temp")
    logger_temp.disabled = True
    trading_date = find_last_trading_day(logger_temp)
    
    if not trading_date:
        print("ERROR: Could not determine last trading day")
        return
    
    logger, log_file = setup_logging(trading_date)
    
    print("=" * 80)
    print("WEEKLY HISTORY RESET - 5-Year Baseline")
    print("=" * 80)
    print(f"Trading day: {trading_date}")
    print(f"Log file: {log_file}")
    print()
    
    try:
        symbols_master = load_json(SYMBOLS_FILE)
        symbol_map = load_json(SYMBOL_MAP_FILE)
        symbols = symbols_master.get("symbols", [])
        yahoo_overrides = symbol_map.get("overrides", {})
        screener_overrides = symbol_map.get("screener_overrides", {})
        delisted = set(symbol_map.get("delisted", []))
        print(f"Loaded: {len(symbols)} symbols")
    except Exception as e:
        logger.error(f"Config load error: {str(e)}")
        print(f"ERROR: {str(e)}")
        return
    
    stats = {"processed": 0, "skipped": 0, "delisted_skipped": 0, "bond_skipped": 0, "yahoo_success": 0, "yahoo_errors": 0, "screener_success": 0, "screener_errors": 0, "save_errors": 0}
    
    print()
    print("Fetching 5-year baseline...")
    
    fetch_start = time.time()
    history_yahoo = {}
    history_screener = {}
    
    for symbol in symbols:
        ticker = str(symbol["ticker"]).strip()
        
        # Check skip conditions
        if ticker in delisted:
            logger.warning(f"{ticker}: SKIPPED - Delisted")
            stats["delisted_skipped"] += 1
            stats["skipped"] += 1
            continue
        
        if ticker.upper().startswith("SGB") or "BOND" in ticker.upper():
            logger.warning(f"{ticker}: SKIPPED - Bond/Instrument")
            stats["bond_skipped"] += 1
            stats["skipped"] += 1
            continue
        
        # Fetch Yahoo 5-year
        yahoo_payload = fetch_yahoo_5year(logger, ticker, yahoo_overrides)
        history_yahoo[ticker] = {"ticker": ticker}
        history_yahoo[ticker].update(yahoo_payload)
        if "error" not in yahoo_payload:
            stats["yahoo_success"] += 1
        else:
            stats["yahoo_errors"] += 1
        
        # Fetch Screener latest
        screener_payload = fetch_screener_latest(logger, ticker, screener_overrides)
        history_screener[ticker] = {"ticker": ticker}
        history_screener[ticker].update(screener_payload)
        if "error" not in screener_payload:
            stats["screener_success"] += 1
        else:
            stats["screener_errors"] += 1
        
        stats["processed"] += 1
    
    fetch_duration = round(time.time() - fetch_start, 2)
    print(f"Fetch: {stats['processed']} stocks in {fetch_duration}s")
    print(f"  Yahoo: {stats['yahoo_success']} success, {stats['yahoo_errors']} errors")
    print(f"  Screener: {stats['screener_success']} success, {stats['screener_errors']} errors")
    print(f"  Skipped: {stats['delisted_skipped']} delisted, {stats['bond_skipped']} bonds")
    
    print()
    print("Saving history files...")
    
    try:
        save_json(YAHOO_HISTORY, history_yahoo)
        print(f"✓ {YAHOO_HISTORY.name}")
    except Exception as e:
        logger.error(f"Yahoo save error: {str(e)}")
        stats["save_errors"] += 1
    
    try:
        save_json(SCREENER_HISTORY, history_screener)
        print(f"✓ {SCREENER_HISTORY.name}")
    except Exception as e:
        logger.error(f"Screener save error: {str(e)}")
        stats["save_errors"] += 1
    
    total_duration = round(time.time() - script_start, 2)
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total runtime: {total_duration}s")
    print(f"Processed: {stats['processed']} | Skipped: {stats['skipped']} (delisted={stats['delisted_skipped']}, bonds={stats['bond_skipped']})")
    print(f"Yahoo: {stats['yahoo_success']}/{stats['processed']} | Screener: {stats['screener_success']}/{stats['processed']}")
    if stats["yahoo_errors"] + stats["screener_errors"] + stats["save_errors"] > 0:
        print(f"Total Errors: {stats['yahoo_errors']} + {stats['screener_errors']} + {stats['save_errors']} (check log)")
    print(f"Data: 5-year baseline (~1260 trading days per stock)")
    print(f"Log: {log_file.name}")
    print("=" * 80)

if __name__ == "__main__":
    main()
