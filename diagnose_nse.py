import requests
import time
import random
import json
import gzip
import brotli  # ✅ NEW: Import brotli for br compression
from pathlib import Path
from datetime import datetime

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.nseindia.com/",
    "Origin": "https://www.nseindia.com",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

RAW_DIR = Path("raw")
LOG_DIR = Path("logs")
DEBUG_DIR = Path("debug")

RAW_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
DEBUG_DIR.mkdir(exist_ok=True)

session = requests.Session()


def log_message(message):

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"[{timestamp}] {message}")

    with open(LOG_DIR / "runtime_history.json", "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": timestamp,
            "message": message
        }) + "\n")


def save_debug_response(symbol, endpoint, content):

    filename = f"{symbol}_{endpoint}.txt"

    file_path = DEBUG_DIR / filename

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)


def decompress_response(response):
    """Handle gzip/deflate/brotli decompression"""
    
    content_encoding = response.headers.get('content-encoding', '').lower()
    
    try:
        if 'br' in content_encoding:
            # ✅ NEW: Handle Brotli compression
            return brotli.decompress(response.content).decode('utf-8')
        elif 'gzip' in content_encoding:
            return gzip.decompress(response.content).decode('utf-8')
        elif 'deflate' in content_encoding:
            return gzip.decompress(response.content).decode('utf-8')
        else:
            return response.text
    except Exception as e:
        log_message(f"DECOMPRESSION ERROR: {e}")
        return response.text


def init_nse():

    warmup_urls = [
        "https://www.nseindia.com/api/marketStatus",
        "https://www.nseindia.com/api/allIndices"
    ]

    for url in warmup_urls:

        try:

            response = session.get(
                url,
                headers=BASE_HEADERS,
                timeout=30,
            )

            if response.status_code == 200:

                log_message(f"WARMUP SUCCESS: {url}")

                return

            else:

                log_message(
                    f"WARMUP NON-200: {url} | "
                    f"{response.status_code}"
                )

        except Exception as e:

            log_message(
                f"WARMUP FAILED: {url} | {e}"
            )

    log_message("Proceeding without NSE homepage init")


def fetch_json(url, symbol, endpoint, retries=5):

    for attempt in range(1, retries + 1):

        try:

            response = session.get(
                url,
                headers=BASE_HEADERS,
                timeout=30,
            )

            if response.status_code != 200:

                log_message(
                    f"NON-200 RESPONSE: "
                    f"{response.status_code} | {url}"
                )

                time.sleep(random.uniform(3, 8))

                continue

            # ✅ DECOMPRESS (now includes Brotli)
            content = decompress_response(response)
            content = content.strip()

            if not content:

                log_message(
                    f"EMPTY RESPONSE BODY: {url}"
                )

                time.sleep(random.uniform(3, 8))

                continue

            save_debug_response(
                symbol,
                endpoint,
                content
            )

            try:

                data = json.loads(content)

                log_message(f"SUCCESS: {url}")

                return data

            except Exception as json_error:

                log_message(
                    f"JSON PARSE FAILED: {url} | "
                    f"{json_error}"
                )

                time.sleep(random.uniform(3, 8))

                continue

        except Exception as e:

            log_message(
                f"FAILED Attempt {attempt}: "
                f"{url} | {e}"
            )

            time.sleep(random.uniform(3, 8))

            init_nse()

    log_message(f"ALL RETRIES FAILED: {url}")

    return {}


def fetch_quote_equity(symbol):
    """Fetch quote/equity data"""

    url = (
        "https://www.nseindia.com/api/"
        f"quote-equity?symbol={symbol}"
    )

    return fetch_json(
        url,
        symbol,
        "quote_equity"
    )


def fetch_financial_results(symbol):

    url = (
        "https://www.nseindia.com/api/"
        f"corporates-financial-results?"
        f"index=equities&symbol={symbol}"
    )

    return fetch_json(
        url,
        symbol,
        "financial_results"
    )


def fetch_announcements(symbol):

    url = (
        "https://www.nseindia.com/api/"
        f"corporate-announcements?"
        f"index=equities&symbol={symbol}"
    )

    return fetch_json(
        url,
        symbol,
        "announcements"
    )


def fetch_annual_reports(symbol):

    url = (
        "https://www.nseindia.com/api/"
        f"annual-reports?"
        f"index=equities&symbol={symbol}"
    )

    return fetch_json(
        url,
        symbol,
        "annual_reports"
    )


def save_raw(symbol, data_type, data):

    if not data:

        log_message(
            f"EMPTY DATA SKIPPED: "
            f"{symbol} | {data_type}"
        )

        return

    file_path = RAW_DIR / f"{symbol}_{data_type}.json"

    with open(file_path, "w", encoding="utf-8") as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
        )

    log_message(f"SAVED: {file_path}")


def process_symbol(symbol):

    log_message(f"STARTED: {symbol}")

    # Fetch quote/equity data
    quote = fetch_quote_equity(symbol)
    save_raw(symbol, "quote_equity", quote)
    time.sleep(random.uniform(2, 5))

    # Fetch financial results
    financials = fetch_financial_results(symbol)
    save_raw(symbol, "financial_results", financials)
    time.sleep(random.uniform(2, 5))

    # Fetch announcements
    announcements = fetch_announcements(symbol)
    save_raw(symbol, "announcements", announcements)
    time.sleep(random.uniform(2, 5))

    # Fetch annual reports
    annual_reports = fetch_annual_reports(symbol)
    save_raw(symbol, "annual_reports", annual_reports)

    log_message(f"COMPLETED: {symbol}")


if __name__ == "__main__":

    symbols = [
        "BLACKBUCK",
        "RELIANCE",
        "INFY",
        "TCS",
        "WIPRO"
    ]

    init_nse()

    for symbol in symbols:

        process_symbol(symbol)

        time.sleep(random.uniform(3, 7))

    log_message("ALL DONE")
