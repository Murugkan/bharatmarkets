import json
import time
import requests
import yfinance as yf
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime, UTC

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TODAY = datetime.now(UTC).strftime("%Y-%m-%d")

DATA_FILE = DATA_DIR / f"intraday_yahoo_{TODAY}.json"
SYMBOLS_FILE = BASE_DIR / "unified-symbols.json"
SYMBOL_MAP_FILE = BASE_DIR / "symbol_map.json"

HEADERS = {"User-Agent": "Mozilla/5.0"}

def now():
    return datetime.now(UTC).isoformat()

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

symbol_map = load_json(SYMBOL_MAP_FILE)
YAHOO_OVERRIDES = symbol_map.get("overrides", {})
DELISTED = set(symbol_map.get("delisted", []))

def is_bond(ticker):
    t = str(ticker).upper().strip()
    return t.startswith("SGB") or "BOND" in t

def resolve_yahoo_symbol(ticker):
    return YAHOO_OVERRIDES.get(ticker, f"{ticker}.NS")

def fetch_yahoo_payload(ticker):
    payload = {}
    yahoo_symbol = resolve_yahoo_symbol(ticker)
    stock = yf.Ticker(yahoo_symbol)
    
    try:
        payload["info"] = stock.info
    except Exception as e:
        payload["info_error"] = str(e)
    
    try:
        hist = stock.history(period="1y", interval="1d")
        payload["history_1y_1d"] = hist.reset_index().astype(str).to_dict("records")
    except Exception as e:
        payload["history_error"] = str(e)
    
    return payload

def ensure_stock(store, symbol):
    ticker = symbol["ticker"]
    if ticker not in store:
        store[ticker] = {
            "ticker": ticker,
            "name": symbol.get("name"),
            "isin": symbol.get("isin"),
            "observations": []
        }
    return store[ticker]

def add_observation(stock, provider, payload):
    stock["observations"].append({
        "provider": provider,
        "fetched_at": now(),
        "raw": payload
    })

def main():
    start = time.time()
    store = load_json(DATA_FILE)
    
    symbols_master = load_json(SYMBOLS_FILE)
    symbols = symbols_master.get("symbols", [])
    
    processed = 0
    skipped = 0
    
    for symbol in symbols:
        ticker = str(symbol["ticker"]).strip()
        
        if ticker in DELISTED:
            continue
        if is_bond(ticker):
            skipped += 1
            continue
        
        stock = ensure_stock(store, symbol)
        
        try:
            yahoo_payload = fetch_yahoo_payload(ticker)
            add_observation(stock, "yahoo_finance", yahoo_payload)
            processed += 1
        except Exception as e:
            add_observation(stock, "yahoo_finance", {"error": str(e)})
    
    save_json(DATA_FILE, store)
    
    runtime = round(time.time() - start, 2)
    print(f"\n{'='*50}\nINTRADAY\n{'='*50}\nProcessed: {processed}\nSkipped: {skipped}\nRuntime: {runtime}s\n{'='*50}\n")

if __name__ == "__main__":
    main()
