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
DATA_DIR = BASE_DIR / "data"

# Create data folder if it doesn't exist
DATA_DIR.mkdir(parents=True, exist_ok=True)

RAW_YAHOO_FILE = DATA_DIR / "raw_yahoo_fundamentals.json"
RAW_SCREENER_FILE = DATA_DIR / "raw_screener_fundamentals.json"

LOG_FILE = DATA_DIR / "fetch_runtime.log"
YAHOO_LOG_FILE = DATA_DIR / "yahoo_fetch.log"
SCREENER_LOG_FILE = DATA_DIR / "screener_fetch.log"

SYMBOLS_FILE = BASE_DIR / "unified-symbols.json"
SYMBOL_MAP_FILE = BASE_DIR / "symbol_map.json"

# Configure main logger (only WARNING and above)
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
    ]
)
logger = logging.getLogger(__name__)

# Configure Yahoo logger (only WARNING and above)
yahoo_logger = logging.getLogger("yahoo_finance")
yahoo_handler = logging.FileHandler(YAHOO_LOG_FILE)
yahoo_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
yahoo_handler.setLevel(logging.WARNING)
yahoo_logger.addHandler(yahoo_handler)
yahoo_logger.setLevel(logging.WARNING)

# Configure Screener logger (only WARNING and above)
screener_logger = logging.getLogger("screener")
screener_handler = logging.FileHandler(SCREENER_LOG_FILE)
screener_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
screener_handler.setLevel(logging.WARNING)
screener_logger.addHandler(screener_handler)
screener_logger.setLevel(logging.WARNING)

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
        yahoo_logger.warning(f"Yahoo info error for {ticker}: {str(e)}")
    
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
        yahoo_logger.warning(f"Yahoo history error for {ticker}: {str(e)}")
    
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
        screener_logger.warning(f"Screener fetch error for {ticker}: {str(e)}")
    
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
    
    print("=" * 70)
    print("STARTING UNIFIED FUNDAMENTALS & PROVIDER DATA FETCH")
    print("=" * 70)
    print()
    
    # Initialize separate stores for each provider
    yahoo_store = {}
    screener_store = {}
    
    # Track failures for detailed summary
    yahoo_failures = {}
    screener_failures = {}
    
    symbols_master = load_json(SYMBOLS_FILE)
    symbols = symbols_master.get("symbols", [])
    
    processed = 0
    skipped = 0
    yahoo_success = 0
    yahoo_errors = 0
    screener_success = 0
    screener_errors = 0
    
    print(f"Processing {len(symbols)} symbols...")
    print()
    
    for idx, symbol in enumerate(symbols, 1):
        
        ticker = str(symbol["ticker"]).strip()
        
        # Skip delisted stocks
        if ticker in DELISTED:
            continue
        
        # Skip bonds
        if is_bond(ticker):
            skipped += 1
            continue
        
        # Progress indicator (every 10 stocks)
        if idx % 10 == 0:
            print(f"  [{idx}/{len(symbols)}] Processing...")
        
        # ====== YAHOO FINANCE FETCH ======
        try:
            yahoo_symbol = resolve_yahoo_symbol(ticker)
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
        
        except Exception as e:
            yahoo_errors += 1
            error_msg = str(e)
            yahoo_failures[ticker] = error_msg
            yahoo_logger.error(f"{ticker}: {error_msg}")
            
            if ticker not in yahoo_store:
                yahoo_store[ticker] = {
                    "ticker": ticker,
                    "name": symbol.get("name"),
                    "isin": symbol.get("isin"),
                    "observations": []
                }
            
            yahoo_store[ticker]["observations"].append({
                "fetched_at": now(),
                "raw": {"error": error_msg}
            })
        
        # ====== SCREENER.IN FETCH ======
        try:
            screener_symbol = resolve_screener_symbol(ticker)
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
        
        except Exception as e:
            screener_errors += 1
            error_msg = str(e)
            screener_failures[ticker] = error_msg
            screener_logger.error(f"{ticker}: {error_msg}")
            
            if ticker not in screener_store:
                screener_store[ticker] = {
                    "ticker": ticker,
                    "name": symbol.get("name"),
                    "isin": symbol.get("isin"),
                    "observations": []
                }
            
            screener_store[ticker]["observations"].append({
                "fetched_at": now(),
                "raw": {"error": error_msg}
            })
        
        processed += 1
    
    # Save separate provider files
    print()
    print("=" * 70)
    print("SAVING DATA FILES")
    print("=" * 70)
    
    save_json(RAW_YAHOO_FILE, yahoo_store)
    print(f"✓ Yahoo Finance data: {RAW_YAHOO_FILE}")
    
    save_json(RAW_SCREENER_FILE, screener_store)
    print(f"✓ Screener.in data: {RAW_SCREENER_FILE}")
    
    runtime = round(time.time() - start, 2)
    
    # Create detailed summary
    summary_lines = []
    summary_lines.append("")
    summary_lines.append("=" * 70)
    summary_lines.append("DETAILED FETCH SUMMARY")
    summary_lines.append("=" * 70)
    summary_lines.append("")
    
    summary_lines.append("PROCESSING OVERVIEW:")
    summary_lines.append(f"  Total Symbols          : {len(symbols)}")
    summary_lines.append(f"  Successfully Processed : {processed}")
    summary_lines.append(f"  Skipped (Bonds)        : {skipped}")
    summary_lines.append("")
    
    summary_lines.append("YAHOO FINANCE RESULTS:")
    summary_lines.append(f"  Success Rate           : {yahoo_success}/{processed} ({round(yahoo_success/processed*100, 1)}%)")
    summary_lines.append(f"  Errors                 : {yahoo_errors}")
    summary_lines.append(f"  Output File            : {RAW_YAHOO_FILE}")
    
    if yahoo_failures:
        summary_lines.append(f"")
        summary_lines.append(f"  Failed Tickers ({len(yahoo_failures)}):")
        for ticker, error in sorted(yahoo_failures.items()):
            summary_lines.append(f"    - {ticker}: {error[:60]}")
    
    summary_lines.append("")
    
    summary_lines.append("SCREENER.IN RESULTS:")
    summary_lines.append(f"  Success Rate           : {screener_success}/{processed} ({round(screener_success/processed*100, 1)}%)")
    summary_lines.append(f"  Errors                 : {screener_errors}")
    summary_lines.append(f"  Output File            : {RAW_SCREENER_FILE}")
    
    if screener_failures:
        summary_lines.append(f"")
        summary_lines.append(f"  Failed Tickers ({len(screener_failures)}):")
        for ticker, error in sorted(screener_failures.items()):
            summary_lines.append(f"    - {ticker}: {error[:60]}")
    
    summary_lines.append("")
    
    summary_lines.append("LOG FILES:")
    summary_lines.append(f"  Main Log               : {LOG_FILE}")
    summary_lines.append(f"  Yahoo Log              : {YAHOO_LOG_FILE}")
    summary_lines.append(f"  Screener Log           : {SCREENER_LOG_FILE}")
    summary_lines.append("")
    
    summary_lines.append("RUNTIME INFORMATION:")
    summary_lines.append(f"  Duration               : {runtime} seconds")
    summary_lines.append(f"  Completed At           : {now()}")
    summary_lines.append("")
    summary_lines.append("=" * 70)
    
    # Print summary
    summary_text = "\n".join(summary_lines)
    print(summary_text)
    
    # Save summary to log file
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(summary_text)
    
    # Commit and push to GitHub
    files_to_commit = [
        "data/raw_yahoo_fundamentals.json",
        "data/raw_screener_fundamentals.json",
        "data/fetch_runtime.log",
        "data/yahoo_fetch.log",
        "data/screener_fetch.log"
    ]
    
    git_commit_and_push(files_to_commit)


if __name__ == "__main__":
    main()
