# fetch_fundamentals.py

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

RAW_DIR = os.path.join(BASE_DIR, "raw_payloads")
LOG_DIR = os.path.join(BASE_DIR, "logs")

RAW_CSV = os.path.join(BASE_DIR, "raw_fetched_data.csv")
RUNTIME_LOG = os.path.join(LOG_DIR, "runtime_fetch.log")

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

def verify_file(path, label):

    exists = os.path.exists(path)

    size = os.path.getsize(path) if exists else 0

    log(
        f"[{label}_VERIFY] "
        f"exists={exists} "
        f"size={size} "
        f"path={os.path.abspath(path)}"
    )

def save_payload(ticker, provider, payload):

    path = os.path.join(
        RAW_DIR,
        f"{ticker}_{provider}.json"
    )

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    verify_file(path, "PAYLOAD")

    return path

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

    verify_file(RAW_CSV, "CSV")

    log(
        f"[CSV_WRITE] "
        f"rows={len(rows)} "
        f"file={RAW_CSV}"
    )

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
        "meta": {},
        "top_ratios": {},
        "quarterly": []
    }

    payload["meta"] = {
        "ticker": ticker,
        "url": url,
        "status_code": response.status_code,
        "fetched_at": now()
    }

    ratio_blocks = soup.select("ul#top-ratios li")

    for row in ratio_blocks:

        try:

            name_el = row.select_one("span.name")
            value_el = row.select_one("span.number")

            if not name_el or not value_el:
                continue

            key = (
                name_el
                .get_text(" ", strip=True)
                .lower()
                .replace(" ", "_")
                .replace("%", "pct")
                .replace("/", "_")
            )

            value = value_el.get_text(" ", strip=True)

            payload["top_ratios"][key] = value

        except Exception:
            pass

    quarterly_tables = soup.select("section#quarters table")

    if quarterly_tables:

        table = quarterly_tables[0]

        headers = []

        header_row = table.select("tr")[0]

        for th in header_row.select("th"):
            headers.append(
                th.get_text(" ", strip=True)
            )

        rows = table.select("tr")[1:]

        quarterly_data = {}

        for row in rows:

            cols = row.select("td")

            if len(cols) < 2:
                continue

            metric = (
                cols[0]
                .get_text(" ", strip=True)
                .lower()
                .replace(" ", "_")
                .replace("%", "pct")
            )

            for idx in range(1, len(cols)):

                if idx >= len(headers):
                    continue

                quarter = headers[idx]

                value = cols[idx].get_text(
                    " ",
                    strip=True
                )

                quarterly_data.setdefault(
                    quarter,
                    {}
                )

                quarterly_data[
                    quarter
                ][metric] = value

        for quarter, values in quarterly_data.items():

            q = {
                "quarter": quarter
            }

            q.update(values)

            payload["quarterly"].append(q)

    return payload

FETCHERS = {
    "screener": fetch_screener
}

def fetch_provider(ticker, provider):

    cfg = PROVIDERS[provider]

    retries = cfg["retries"]
    delay = cfg["delay"]

    for attempt in range(1, retries + 2):

        try:

            sleep_time = (
                delay
                + random.uniform(1, 3)
            )

            log(
                f"[FETCH_START] "
                f"ticker={ticker} "
                f"provider={provider} "
                f"attempt={attempt} "
                f"delay={round(sleep_time,2)}"
            )

            time.sleep(sleep_time)

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
                f"{','.join(fields[:100])}"
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
