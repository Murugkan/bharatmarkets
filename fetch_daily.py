import json
import time
import requests
import yfinance as yf
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime, UTC, timedelta
import logging
import sys

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

YAHOO_5DAYS = DATA_DIR / "daily_yahoo_5days.json"
SCREENER_5DAYS = DATA_DIR / "daily_screener_5days.json"

SYMBOLS_FILE = BASE_DIR / "unified-symbols.json"
SYMBOL_MAP_FILE = BASE_DIR / "symbol_map.json"

HEADERS = {"User-Agent": "Mozilla/5.0"}

TIME_BOUND_FIELDS = {
    "price", "volume", "open", "high", "low", "close",
    "pe_ratio", "dividend_yield", "market_cap_change"
}

NON_TIME_BOUND_FIELDS = {
    "sector", "industry", "company_name", "exchange", 
    "currency", "isin", "website"
}

def setup_logging(trading_date):
    """Setup WARNING+ logging (skip verbose INFO, capture issues)"""
    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"daily_{log_timestamp}.log"
    
    logger = logging.getLogger("daily_fetch")
    logger.setLevel(logging.WARNING)
    
    # File handler (warnings & errors)
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

def field_exists_for_date(data_array, target_date):
    """Check if date exists (idempotent)"""
    if not isinstance(data_array, list):
        return False
    return any(entry.get("date") == target_date for entry in data_array)

def merge_field_level(logger, existing_data, new_data, trading_date_str, stats):
    """Merge with field-level logic"""
    for ticker, new_ticker_data in new_data.items():
        try:
            if ticker not in existing_data:
                existing_data[ticker] = {"ticker": ticker, "metadata": {}, "fields": {}}
            
            existing_ticker = existing_data[ticker]
            if "metadata" not in existing_ticker:
                existing_ticker["metadata"] = {}
            if "fields" not in existing_ticker:
                existing_ticker["fields"] = {}
            
            # Merge metadata
            for field, value in new_ticker_data.get("metadata", {}).items():
                if field in NON_TIME_BOUND_FIELDS and value:
                    existing_ticker["metadata"][field] = value
            
            # Merge fields
            fields_appended = 0
            for field, value in new_ticker_data.get("fields", {}).items():
                if field in TIME_BOUND_FIELDS and value is not None:
                    if field not in existing_ticker["fields"]:
                        existing_ticker["fields"][field] = []
                    
                    if not field_exists_for_date(existing_ticker["fields"][field], trading_date_str):
                        existing_ticker["fields"][field].append({"date": trading_date_str, "value": value})
                        fields_appended += 1
            
            stats["fields_appended"] += fields_appended
            stats["stocks_merged"] += 1
            
        except Exception as e:
            logger.error(f"Merge error {ticker}: {str(e)}")
            stats["merge_errors"] += 1

def trim_to_5_days(logger, data, trading_date_str, stats):
    """Keep only last 5 trading days"""
    try:
        cutoff_date = (datetime.strptime(trading_date_str, "%Y-%m-%d") - timedelta(days=5)).strftime("%Y-%m-%d")
        trimmed_count = 0
        
        for ticker in data:
            if isinstance(data[ticker], dict):
                for field in TIME_BOUND_FIELDS:
                    if field in data[ticker].get("fields", {}) and isinstance(data[ticker]["fields"][field], list):
                        before = len(data[ticker]["fields"][field])
                        data[ticker]["fields"][field] = [e for e in data[ticker]["fields"][field] if e.get("date", "") >= cutoff_date]
                        trimmed_count += (before - len(data[ticker]["fields"][field]))
        
        stats["entries_trimmed"] = trimmed_count
    except Exception as e:
        logger.error(f"Trim error: {str(e)}")

def fetch_yahoo_data(logger, ticker, yahoo_overrides):
    """Fetch Yahoo Finance"""
    payload = {}
    try:
        yahoo_symbol = yahoo_overrides.get(ticker, f"{ticker}.NS")
        stock = yf.Ticker(yahoo_symbol)
        info = stock.info
        hist = stock.history(period="5d", interval="1d")
        
        if hist.empty:
            logger.warning(f"{ticker}: Yahoo - No history data")
            return payload
        
        latest = hist.iloc[-1]
        payload["metadata"] = {"company_name": info.get("longName"), "sector": info.get("sector"), "industry": info.get("industry"), "exchange": info.get("exchange"), "currency": info.get("currency")}
        payload["fields"] = {"price": float(latest["Close"]), "volume": int(latest["Volume"]), "open": float(latest["Open"]), "high": float(latest["High"]), "low": float(latest["Low"]), "pe_ratio": info.get("trailingPE"), "dividend_yield": info.get("dividendYield")}
        
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

def fetch_screener_data(logger, ticker, screener_overrides):
    """Fetch Screener.in"""
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
        
        payload["metadata"] = {"sector": soup.select_one("[data-field='sector']").text if soup.select_one("[data-field='sector']") else None}
        payload["fields"] = {}
        
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
                        payload["fields"][f"{section_name}_{field_name}"] = field_value
        
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
    print("DAILY FETCH - Field-Level Merge (5-Day Rolling)")
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
    
    try:
        yahoo_data = load_json(YAHOO_5DAYS)
        screener_data = load_json(SCREENER_5DAYS)
        print(f"Loaded rolling windows: Yahoo={len(yahoo_data)}, Screener={len(screener_data)}")
    except Exception as e:
        logger.error(f"Rolling window load error: {str(e)}")
        return
    
    stats = {"processed": 0, "skipped": 0, "delisted_skipped": 0, "bond_skipped": 0, "yahoo_success": 0, "yahoo_errors": 0, "screener_success": 0, "screener_errors": 0, "stocks_merged": 0, "fields_appended": 0, "merge_errors": 0, "entries_trimmed": 0}
    
    print()
    print("Fetching data...")
    
    fetch_start = time.time()
    new_yahoo_data = {}
    new_screener_data = {}
    
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
        
        new_yahoo_data[ticker] = {"ticker": ticker, "metadata": {}, "fields": {}}
        new_screener_data[ticker] = {"ticker": ticker, "metadata": {}, "fields": {}}
        
        # Fetch Yahoo
        yahoo_payload = fetch_yahoo_data(logger, ticker, yahoo_overrides)
        new_yahoo_data[ticker].update(yahoo_payload)
        if "error" not in yahoo_payload:
            stats["yahoo_success"] += 1
        else:
            stats["yahoo_errors"] += 1
        
        # Fetch Screener
        screener_payload = fetch_screener_data(logger, ticker, screener_overrides)
        new_screener_data[ticker].update(screener_payload)
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
    
    print("Merging data...")
    merge_start = time.time()
    merge_field_level(logger, yahoo_data, new_yahoo_data, trading_date, stats)
    merge_field_level(logger, screener_data, new_screener_data, trading_date, stats)
    merge_duration = round(time.time() - merge_start, 2)
    
    print(f"Merge: {merge_duration}s ({stats['fields_appended']} fields appended, {stats['merge_errors']} errors)")
    
    print("Trimming to 5-day window...")
    trim_to_5_days(logger, yahoo_data, trading_date, stats)
    trim_to_5_days(logger, screener_data, trading_date, stats)
    print(f"Trimmed: {stats['entries_trimmed']} old entries")
    
    print("Saving files...")
    try:
        save_json(YAHOO_5DAYS, yahoo_data)
        print(f"✓ {YAHOO_5DAYS.name}")
    except Exception as e:
        logger.error(f"Yahoo save error: {str(e)}")
    
    try:
        save_json(SCREENER_5DAYS, screener_data)
        print(f"✓ {SCREENER_5DAYS.name}")
    except Exception as e:
        logger.error(f"Screener save error: {str(e)}")
    
    total_duration = round(time.time() - script_start, 2)
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total runtime: {total_duration}s")
    print(f"Processed: {stats['processed']} | Skipped: {stats['skipped']} (delisted={stats['delisted_skipped']}, bonds={stats['bond_skipped']})")
    print(f"Yahoo: {stats['yahoo_success']}/{stats['processed']} | Screener: {stats['screener_success']}/{stats['processed']}")
    print(f"Appended: {stats['fields_appended']} fields | Trimmed: {stats['entries_trimmed']} entries")
    if stats["yahoo_errors"] + stats["screener_errors"] + stats["merge_errors"] > 0:
        print(f"Total Errors: {stats['yahoo_errors']} + {stats['screener_errors']} + {stats['merge_errors']} (check log)")
    print(f"Log: {log_file.name}")
    print("=" * 80)

if __name__ == "__main__":
    main()
