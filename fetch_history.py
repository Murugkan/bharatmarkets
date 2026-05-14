import json
import time
import requests
import yfinance as yf
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime, UTC

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# Changed to match merge_script.py expectations
YAHOO_FILE = DATA_DIR / "daily_yahoo.json"
SCREENER_FILE = DATA_DIR / "daily_screener.json"
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
SCREENER_OVERRIDES = symbol_map.get("screener_overrides", {})
DELISTED = set(symbol_map.get("delisted", []))

def is_bond(ticker):
    t = str(ticker).upper().strip()
    return t.startswith("SGB") or "BOND" in t

def resolve_yahoo_symbol(ticker):
    return YAHOO_OVERRIDES.get(ticker, f"{ticker}.NS")

def resolve_screener_symbol(ticker):
    return SCREENER_OVERRIDES.get(ticker, ticker)

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

def extract_table(table):
    rows = []
    for tr in table.select("tr"):
        cols = tr.select("th,td")
        row = []
        for col in cols:
            row.append(col.get_text(" ", strip=True))
        if row:
            rows.append(row)
    return rows

def fetch_screener_payload(ticker):
    payload = {}
    screener_symbol = resolve_screener_symbol(ticker)
    url = f"https://www.screener.in/company/{screener_symbol}/"
    payload["url"] = url
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        soup = BeautifulSoup(response.text, "html.parser")
        payload["tables"] = []
        
        for section in soup.select("section"):
            table = section.select_one("table")
            if not table:
                continue
            heading = section.select_one("h2")
            payload["tables"].append({
                "section": heading.get_text(" ", strip=True) if heading else None,
                "rows": extract_table(table)
            })
    except Exception as e:
        payload["error"] = str(e)
    
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

def add_observation(stock, payload):
    stock["observations"].append({
        "fetched_at": now(),
        "raw": payload
    })

def main():
    start = time.time()
    
    # Auto-create data directories
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "chart").mkdir(parents=True, exist_ok=True)
    
    symbols_master = load_json(SYMBOLS_FILE)
    symbols = symbols_master.get("symbols", [])
    
    yahoo_store = {}
    screener_store = {}
    
    processed = 0
    skipped = 0
    
    for symbol in symbols:
        ticker = str(symbol["ticker"]).strip()
        
        if ticker in DELISTED:
            continue
        if is_bond(ticker):
            skipped += 1
            continue
        
        # Yahoo
        try:
            yahoo_stock = ensure_stock(yahoo_store, symbol)
            yahoo_payload = fetch_yahoo_payload(ticker)
            add_observation(yahoo_stock, yahoo_payload)
        except Exception as e:
            yahoo_stock = ensure_stock(yahoo_store, symbol)
            add_observation(yahoo_stock, {"error": str(e)})
        
        # Screener
        try:
            screener_stock = ensure_stock(screener_store, symbol)
            screener_payload = fetch_screener_payload(ticker)
            add_observation(screener_stock, screener_payload)
        except Exception as e:
            screener_stock = ensure_stock(screener_store, symbol)
            add_observation(screener_stock, {"error": str(e)})
        
        processed += 1
    
    # Save with correct filenames for merge_script.py
    save_json(YAHOO_FILE, yahoo_store)
    save_json(SCREENER_FILE, screener_store)
    
    runtime = round(time.time() - start, 2)
    
    # Metadata & logs
    for provider, data_file in [("yahoo", YAHOO_FILE), ("screener", SCREENER_FILE)]:
        meta_file = DATA_DIR / f"meta_{provider}.json"
        metadata = {
            "timestamp": now(),
            "type": "history",
            "provider": provider,
            "processed": processed,
            "skipped": skipped,
            "runtime_seconds": runtime,
            "data_file": data_file.name,
            "operation": "fetch"
        }
        save_json(meta_file, metadata)
        
        log_timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        log_file = DATA_DIR / f"fetch_{provider}_{log_timestamp}.log"
        with open(log_file, "w") as f:
            f.write(f"Fetch {provider}\nTimestamp: {now()}\nData File: {data_file.name}\nProcessed: {processed}\nSkipped: {skipped}\nRuntime: {runtime}s\n")
    
    print(f"✓ Fetched: {processed} processed, {skipped} skipped, {runtime}s")
    print(f"✓ Output files ready for merge_script.py:")
    print(f"  - {YAHOO_FILE.name}")
    print(f"  - {SCREENER_FILE.name}")

if __name__ == "__main__":
    main()
