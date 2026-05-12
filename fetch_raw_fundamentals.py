import json
import time
import logging
import requests
import yfinance as yf
import subprocess
import os

from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime, UTC


BASE_DIR = Path(__file__).resolve().parent

RAW_YAHOO_FILE = BASE_DIR / "raw_yahoo_fundamentals.json"
RAW_SCREENER_FILE = BASE_DIR / "raw_screener_fundamentals.json"
LOG_FILE = BASE_DIR / "fetch_runtime.log"

SYMBOLS_FILE = BASE_DIR / "unified-symbols.json"
SYMBOL_MAP_FILE = BASE_DIR / "symbol_map.json"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def now():
    return datetime.now(UTC).isoformat()


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


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


# ============================================================================
# YAHOO FINANCE FUNCTIONS
# ============================================================================

def fetch_yahoo_info(ticker, yahoo_symbol):
    """Fetch Yahoo Finance info and history"""
    
    payload = {}
    stock = yf.Ticker(yahoo_symbol)
    
    # Fetch info
    try:
        payload["info"] = stock.info
    except Exception as e:
        payload["info_error"] = str(e)
        logger.warning(f"Yahoo info error for {ticker}: {str(e)}")
    
    # Fetch 1-year daily history
    try:
        hist = stock.history(period="1y", interval="1d")
        payload["history_1y_1d"] = (
            hist
            .reset_index()
            .astype(str)
            .to_dict("records")
        )
    except Exception as e:
        payload["history_error"] = str(e)
        logger.warning(f"Yahoo history error for {ticker}: {str(e)}")
    
    return payload


# ============================================================================
# SCREENER.IN FUNCTIONS
# ============================================================================

def extract_table(table):
    """Extract rows from HTML table"""
    rows = []
    
    for tr in table.select("tr"):
        cols = tr.select("th,td")
        row = []
        
        for col in cols:
            row.append(col.get_text(" ", strip=True))
        
        if row:
            rows.append(row)
    
    return rows


def fetch_screener_data(ticker, screener_symbol):
    """Fetch Screener.in company data and tables"""
    
    payload = {}
    
    url = f"https://www.screener.in/company/{screener_symbol}/"
    payload["url"] = url
    
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )
        
        soup = BeautifulSoup(response.text, "html.parser")
        payload["tables"] = []
        
        for section in soup.select("section"):
            table = section.select_one("table")
            
            if not table:
                continue
            
            heading = section.select_one("h2")
            
            payload["tables"].append({
                "section": (
                    heading.get_text(" ", strip=True)
                    if heading else None
                ),
                "rows": extract_table(table)
            })
        
    except Exception as e:
        payload["error"] = str(e)
        logger.warning(f"Screener fetch error for {ticker}: {str(e)}")
    
    return payload


# ============================================================================
# GIT OPERATIONS - AUTO COMMIT & PUSH
# ============================================================================

def git_commit_and_push(files_to_commit):
    """Commit and push files to GitHub repository"""
    
    try:
        logger.info("=" * 60)
        logger.info("GIT OPERATIONS - COMMITTING & PUSHING")
        logger.info("=" * 60)
        
        # Check if we're in a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            logger.warning("Not a git repository - skipping commit")
            return False
        
        logger.info("✓ Git repository detected")
        
        # Configure git user (for GitHub Actions)
        subprocess.run(
            ["git", "config", "user.name", "github-actions[bot]"],
            capture_output=True,
            timeout=10
        )
        subprocess.run(
            ["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"],
            capture_output=True,
            timeout=10
        )
        logger.info("✓ Git user configured")
        
        # Add files
        for file in files_to_commit:
            if os.path.exists(file):
                subprocess.run(
                    ["git", "add", file],
                    capture_output=True,
                    timeout=10
                )
                logger.info(f"  Added: {file}")
        
        # Check if there are changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if not result.stdout.strip():
            logger.info("No changes to commit")
            return True
        
        # Commit
        timestamp = datetime.now(UTC).isoformat()
        commit_msg = f"chore: update fundamentals data [{timestamp}]"
        
        result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            logger.info(f"✓ Committed: {commit_msg}")
        else:
            logger.warning(f"Commit warning: {result.stderr}")
        
        # Push
        result = subprocess.run(
            ["git", "push"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info("✓ Pushed to repository")
            logger.info("=" * 60)
            return True
        else:
            logger.error(f"Push failed: {result.stderr}")
            logger.info("=" * 60)
            return False
    
    except Exception as e:
        logger.error(f"Git operation failed: {str(e)}")
        return False


def main():
    
    start = time.time()
    
    logger.info("=" * 60)
    logger.info("STARTING UNIFIED FUNDAMENTALS & PROVIDER DATA FETCH")
    logger.info("=" * 60)
    
    # Initialize separate stores for each provider
    yahoo_store = {}
    screener_store = {}
    
    symbols_master = load_json(SYMBOLS_FILE)
    symbols = symbols_master.get("symbols", [])
    
    processed = 0
    skipped = 0
    yahoo_success = 0
    yahoo_errors = 0
    screener_success = 0
    screener_errors = 0
    
    logger.info(f"Total symbols to process: {len(symbols)}")
    logger.info("")
    
    for idx, symbol in enumerate(symbols, 1):
        
        ticker = str(symbol["ticker"]).strip()
        
        # Skip delisted stocks
        if ticker in DELISTED:
            logger.debug(f"[{idx}/{len(symbols)}] Skipping delisted: {ticker}")
            continue
        
        # Skip bonds
        if is_bond(ticker):
            logger.debug(f"[{idx}/{len(symbols)}] Skipping bond: {ticker}")
            skipped += 1
            continue
        
        logger.info(f"[{idx}/{len(symbols)}] Processing {ticker}")
        
        # ====== YAHOO FINANCE FETCH ======
        try:
            yahoo_symbol = resolve_yahoo_symbol(ticker)
            logger.debug(f"  -> Yahoo symbol: {yahoo_symbol}")
            
            yahoo_payload = fetch_yahoo_info(ticker, yahoo_symbol)
            
            if ticker not in yahoo_store:
                yahoo_store[ticker] = {
                    "ticker": ticker,
                    "name": symbol.get("name"),
                    "isin": symbol.get("isin"),
                    "observations": []
                }
            
            yahoo_store[ticker]["observations"].append({
                "fetched_at": now(),
                "raw": yahoo_payload
            })
            
            yahoo_success += 1
            logger.debug(f"  OK Yahoo data fetched")
        
        except Exception as e:
            yahoo_errors += 1
            logger.error(f"  FAIL Yahoo error: {str(e)}")
            
            if ticker not in yahoo_store:
                yahoo_store[ticker] = {
                    "ticker": ticker,
                    "name": symbol.get("name"),
                    "isin": symbol.get("isin"),
                    "observations": []
                }
            
            yahoo_store[ticker]["observations"].append({
                "fetched_at": now(),
                "raw": {"error": str(e)}
            })
        
        # ====== SCREENER.IN FETCH ======
        try:
            screener_symbol = resolve_screener_symbol(ticker)
            logger.debug(f"  -> Screener symbol: {screener_symbol}")
            
            screener_payload = fetch_screener_data(ticker, screener_symbol)
            
            if ticker not in screener_store:
                screener_store[ticker] = {
                    "ticker": ticker,
                    "name": symbol.get("name"),
                    "isin": symbol.get("isin"),
                    "observations": []
                }
            
            screener_store[ticker]["observations"].append({
                "fetched_at": now(),
                "raw": screener_payload
            })
            
            screener_success += 1
            logger.debug(f"  OK Screener data fetched")
        
        except Exception as e:
            screener_errors += 1
            logger.error(f"  FAIL Screener error: {str(e)}")
            
            if ticker not in screener_store:
                screener_store[ticker] = {
                    "ticker": ticker,
                    "name": symbol.get("name"),
                    "isin": symbol.get("isin"),
                    "observations": []
                }
            
            screener_store[ticker]["observations"].append({
                "fetched_at": now(),
                "raw": {"error": str(e)}
            })
        
        processed += 1
        logger.info("")
    
    # Save separate provider files
    logger.info("=" * 60)
    logger.info("SAVING DATA FILES")
    logger.info("=" * 60)
    
    logger.info(f"Saving Yahoo Finance data ({len(yahoo_store)} tickers)")
    save_json(RAW_YAHOO_FILE, yahoo_store)
    logger.info(f"OK Saved to {RAW_YAHOO_FILE}")
    
    logger.info(f"Saving Screener.in data ({len(screener_store)} tickers)")
    save_json(RAW_SCREENER_FILE, screener_store)
    logger.info(f"OK Saved to {RAW_SCREENER_FILE}")
    
    runtime = round(time.time() - start, 2)
    
    # Summary report
    summary = f"""
{'=' * 60}
UNIFIED FETCH SUMMARY
{'=' * 60}

PROCESSING STATISTICS:
  Total Symbols        : {len(symbols)}
  Processed            : {processed}
  Skipped (Bonds)      : {skipped}

YAHOO FINANCE:
  OK Success           : {yahoo_success}
  FAIL Errors          : {yahoo_errors}
  Output File          : {RAW_YAHOO_FILE}

SCREENER.IN:
  OK Success           : {screener_success}
  FAIL Errors          : {screener_errors}
  Output File          : {RAW_SCREENER_FILE}

RUNTIME INFORMATION:
  Duration             : {runtime} seconds
  Completed At         : {now()}
  Log File             : {LOG_FILE}

{'=' * 60}
"""
    
    logger.info(summary)
    print(summary)
    
    # Commit and push to GitHub
    files_to_commit = [
        str(RAW_YAHOO_FILE),
        str(RAW_SCREENER_FILE),
        str(LOG_FILE)
    ]
    
    git_commit_and_push(files_to_commit)


if __name__ == "__main__":
    main()
