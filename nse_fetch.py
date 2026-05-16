import requests
import time
import random
import json
from pathlib import Path
from datetime import datetime

BASE_HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "accept": "application/json,text/plain,*/*",
    "accept-language": "en-US,en;q=0.9",
    "referer": "https://www.nseindia.com/",
    "origin": "https://www.nseindia.com",
    "connection": "keep-alive",
}

RAW_DIR = Path("raw")
LOG_DIR = Path("logs")

RAW_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

session = requests.Session()


def log_message(message):

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"[{timestamp}] {message}")

    with open(LOG_DIR / "runtime_history.json", "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": timestamp,
            "message": message
        }) + "\\n")


def init_nse():

    url = "https://www.nseindia.com/"

    response = session.get(
        url,
        headers=BASE_HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    log_message("NSE session initialized")


def fetch_json(url, retries=5):

    for attempt in range(1, retries + 1):

        try:

            response = session.get(
                url,
                headers=BASE_HEADERS,
                timeout=30,
            )

            content_type = response.headers.get("content-type", "")

            if "application/json" not in content_type:
                raise Exception(
                    f"Unexpected content type: {content_type}"
                )

            response.raise_for_status()

            log_message(f"SUCCESS: {url}")

            return response.json()

        except Exception as e:

            log_message(f"FAILED Attempt {attempt}: {url} | {e}")

            if attempt == retries:
                raise

            sleep_time = random.uniform(3, 8)

            time.sleep(sleep_time)

            init_nse()


def fetch_financial_results(symbol):

    url = (
        "https://www.nseindia.com/api/"
        f"corporates-financial-results?"
        f"index=equities&symbol={symbol}"
    )

    return fetch_json(url)


def fetch_announcements(symbol):

    url = (
        "https://www.nseindia.com/api/"
        f"corporate-announcements?"
        f"index=equities&symbol={symbol}"
    )

    return fetch_json(url)


def fetch_annual_reports(symbol):

    url = (
        "https://www.nseindia.com/api/"
        f"annual-reports?"
        f"index=equities&symbol={symbol}"
    )

    return fetch_json(url)


def save_raw(symbol, data_type, data):

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

    try:

        financials = fetch_financial_results(symbol)

        save_raw(
            symbol,
            "financial_results",
            financials
        )

        time.sleep(random.uniform(2, 5))

        announcements = fetch_announcements(symbol)

        save_raw(
            symbol,
            "announcements",
            announcements
        )

        time.sleep(random.uniform(2, 5))

        annual_reports = fetch_annual_reports(symbol)

        save_raw(
            symbol,
            "annual_reports",
            annual_reports
        )

        log_message(f"COMPLETED: {symbol}")

    except Exception as e:

        log_message(f"ERROR: {symbol} | {e}")


if __name__ == "__main__":

    symbols = [
        "BLACKBUCK",
        "RELIANCE",
        "INFY"
    ]

    init_nse()

    for symbol in symbols:

        process_symbol(symbol)

        time.sleep(random.uniform(3, 7))

    log_message("ALL DONE")
