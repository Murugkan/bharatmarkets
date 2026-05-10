
# ============================================================
# REAL RAW FETCH INGESTION
# ============================================================

import os
import csv
import json
import time
import random
import traceback
import requests
from bs4 import BeautifulSoup
from datetime import datetime, UTC
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.getcwd()

RAW_DIR = os.path.join(
    BASE_DIR,
    "raw_payloads"
)

LOG_DIR = os.path.join(
    BASE_DIR,
    "logs"
)

RAW_CSV = os.path.join(
    BASE_DIR,
    "raw_fetched_data.csv"
)

RUNTIME_LOG = os.path.join(
    LOG_DIR,
    "runtime_fetch.log"
)

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

PROVIDERS = {
    "screener": {
        "delay": 5,
        "retries": 2
    }
}


def now():

    return datetime.now(UTC).isoformat()


def log(msg):

    line = f"[{now()}] {msg}"

    print(line)

    with open(RUNTIME_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def write_csv_rows(rows):

    file_exists = os.path.exists(RAW_CSV)

    with open(
        RAW_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "ticker",
                "provider",
                "statement",
                "quarter",
                "field",
                "raw_value"
            ]
        )

        if not file_exists:
            writer.writeheader()

        writer.writerows(rows)

    size = os.path.getsize(RAW_CSV)

    log(
        f"[CSV_WRITE] "
        f"rows={len(rows)} "
        f"file={RAW_CSV} "
        f"size={size}"
    )


def save_payload(
    ticker,
    provider,
    payload
):

    path = (
        f"{RAW_DIR}/"
        f"{ticker}_{provider}.json"
    )

    with open(path, "w", encoding="utf-8") as f:

        json.dump(
            payload,
            f,
            indent=2,
            default=str
        )

    return path


def flatten(
    ticker,
    provider,
    statement,
    quarter,
    obj,
    rows
):

    if isinstance(obj, dict):

        for k, v in obj.items():

            next_quarter = quarter

            if (
                "202" in str(k)
                or "Q" in str(k).upper()
                or "FY" in str(k).upper()
            ):
                next_quarter = k

            flatten(
                ticker=ticker,
                provider=provider,
                statement=k,
                quarter=next_quarter,
                obj=v,
                rows=rows
            )

    elif isinstance(obj, list):

        for item in obj:

            flatten(
                ticker=ticker,
                provider=provider,
                statement=statement,
                quarter=quarter,
                obj=item,
                rows=rows
            )

    else:

        rows.append({
            "ticker": ticker,
            "provider": provider,
            "statement": statement,
            "quarter": quarter,
            "field": statement,
            "raw_value": obj
        })


# ============================================================
# REAL SCREENER FETCH
# ============================================================

def fetch_screener(ticker):

    url = f"https://www.screener.in/company/{ticker}/"

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    payload = {
        "meta": {
            "ticker": ticker,
            "url": url,
            "fetched_at": now(),
            "status_code": response.status_code
        },
        "ratios": {},
        "top_ratios": {}
    }

    # --------------------------------------------------------
    # TOP RATIOS
    # --------------------------------------------------------

    ratios = soup.select("li.flex.flex-space-between")

    for row in ratios:

        try:

            name = (
                row.select_one("span.name")
                .get_text(" ", strip=True)
                .lower()
                .replace(" ", "_")
            )

            value = (
                row.select_one("span.number")
                .get_text(" ", strip=True)
            )

            payload["top_ratios"][name] = value

        except:
            pass

    # --------------------------------------------------------
    # QUICK EXTRACTIONS
    # --------------------------------------------------------

    text = soup.get_text(" ", strip=True)

    if "ROE" in text:
        payload["ratios"]["roe_detected"] = True

    if "ROCE" in text:
        payload["ratios"]["roce_detected"] = True

    if "Cash Flow" in text:
        payload["ratios"]["cashflow_detected"] = True

    return payload


FETCHERS = {
    "screener": fetch_screener
}


def fetch_provider(
    ticker,
    provider
):

    cfg = PROVIDERS[provider]

    for attempt in range(1, cfg["retries"] + 2):

        try:

            delay = (
                cfg["delay"]
                + random.uniform(1, 3)
            )

            log(
                f"[FETCH_START] "
                f"ticker={ticker} "
                f"provider={provider} "
                f"attempt={attempt} "
                f"delay={round(delay,2)}"
            )

            time.sleep(delay)

            started = time.time()

            payload = FETCHERS[provider](ticker)

            latency = round(
                time.time() - started,
                2
            )

            path = save_payload(
                ticker,
                provider,
                payload
            )

            rows = []

            flatten(
                ticker=ticker,
                provider=provider,
                statement="root",
                quarter=None,
                obj=payload,
                rows=rows
            )

            write_csv_rows(rows)

            fields = sorted(
                list(set([
                    x["field"]
                    for x in rows
                ]))
            )

            log(
                f"[FETCH_SUCCESS] "
                f"ticker={ticker} "
                f"provider={provider} "
                f"latency={latency}s "
                f"fields={len(fields)} "
                f"rows={len(rows)} "
                f"path={path}"
            )

            log(
                f"[FIELDS] "
                f"ticker={ticker} "
                f"provider={provider} "
                f"{','.join(fields[:50])}"
            )

            return

        except Exception as e:

            log(
                f"[FETCH_ERROR] "
                f"ticker={ticker} "
                f"provider={provider} "
                f"attempt={attempt} "
                f"error={str(e)}"
            )

            log(traceback.format_exc())

    log(
        f"[FETCH_FAILED] "
        f"ticker={ticker} "
        f"provider={provider}"
    )


def fetch_ticker(ticker):

    log("=" * 80)
    log(f"[START] ticker={ticker}")

    with ThreadPoolExecutor(max_workers=1) as executor:

        futures = [
            executor.submit(
                fetch_provider,
                ticker,
                provider
            )
            for provider in FETCHERS
        ]

        for future in as_completed(futures):
            future.result()

    log(f"[END] ticker={ticker}")


if __name__ == "__main__":

    tickers = [
        "BDL",
        "GRSE",
        "HAL"
    ]

    for ticker in tickers:

        fetch_ticker(ticker)

    log("RAW FETCH COMPLETE")




# ============================================================
# FILESYSTEM PERSISTENCE VERIFICATION
# ============================================================

def verify_file(path, label):

    exists = os.path.exists(path)

    size = (
        os.path.getsize(path)
        if exists else 0
    )

    abs_path = os.path.abspath(path)

    log(
        f"[{label}_VERIFY] "
        f"exists={exists} "
        f"size={size} "
        f"path={abs_path}"
    )

    return exists


# ------------------------------------------------------------
# PATCH CSV WRITER
# ------------------------------------------------------------

_original_write_csv_rows = write_csv_rows

def write_csv_rows(rows):

    _original_write_csv_rows(rows)

    verify_file(
        RAW_CSV,
        "CSV"
    )


# ------------------------------------------------------------
# PATCH PAYLOAD SAVE
# ------------------------------------------------------------

_original_save_payload = save_payload

def save_payload(
    ticker,
    provider,
    payload
):

    path = _original_save_payload(
        ticker,
        provider,
        payload
    )

    verify_file(
        path,
        "PAYLOAD"
    )

    return path

