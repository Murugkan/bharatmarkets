
# ============================================================
# CLEAN RAW SOURCING BUILD
# ============================================================
# PURPOSE
# -------
# Pure raw ingestion layer.
#
# ONLY DOES:
# - fetch raw provider payloads
# - provider delays
# - retries
# - raw payload persistence
# - field-level extraction
# - forensic runtime logs
# - raw audit csv export
#
# DOES NOT:
# - normalize
# - reconcile
# - derive
# - validate
# - export canonical metrics
#
# OUTPUTS
# -------
# logs/runtime_fetch.log
# raw_payloads/<ticker>_<provider>.json
# raw_fetched_data.csv
# ============================================================

import os
import csv
import json
import time
import random
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# CONFIG
# ============================================================

RAW_DIR = "raw_payloads"
LOG_DIR = "logs"

RAW_CSV = "raw_fetched_data.csv"
RUNTIME_LOG = f"{LOG_DIR}/runtime_fetch.log"

MAX_WORKERS = 2

PROVIDERS = {
    "yahoo": {
        "delay": 2.5,
        "retries": 2
    },
    "screener": {
        "delay": 5.0,
        "retries": 2
    },
    "nse": {
        "delay": 3.0,
        "retries": 2
    }
}

# ============================================================
# SETUP
# ============================================================

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ============================================================
# LOGGING
# ============================================================

def log(msg):

    ts = datetime.utcnow().isoformat()

    line = f"[{ts}] {msg}"

    print(line)

    with open(RUNTIME_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ============================================================
# RAW SAVE
# ============================================================

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

# ============================================================
# PROVIDER FETCHERS
# REPLACE WITH REAL IMPLEMENTATION
# ============================================================

def fetch_yahoo(ticker):

    return {
        "ratios": {
            "roe": 14.44,
            "roce": 19.76
        },
        "income_statement": {
            "ebitda": 869.88
        }
    }


def fetch_screener(ticker):

    return {
        "cashflow": {
            "cfo": 1200,
            "fcf": 950
        },
        "ratios": {
            "cur_ratio": 1.22
        }
    }


def fetch_nse(ticker):

    return {
        "shareholding": {
            "promoter": 74.93
        }
    }

FETCHERS = {
    "yahoo": fetch_yahoo,
    "screener": fetch_screener,
    "nse": fetch_nse
}

# ============================================================
# FORENSIC FIELD LOGGER
# ============================================================

def extract_fields(
    ticker,
    provider,
    node,
    statement,
    quarter,
    rows,
    path=""
):

    if isinstance(node, dict):

        for k, v in node.items():

            next_path = (
                f"{path}.{k}"
                if path else k
            )

            next_quarter = quarter

            if (
                "202" in str(k)
                or "Q" in str(k).upper()
                or "FY" in str(k).upper()
            ):
                next_quarter = k

            extract_fields(
                ticker=ticker,
                provider=provider,
                node=v,
                statement=statement,
                quarter=next_quarter,
                rows=rows,
                path=next_path
            )

    elif isinstance(node, list):

        for item in node:

            extract_fields(
                ticker=ticker,
                provider=provider,
                node=item,
                statement=statement,
                quarter=quarter,
                rows=rows,
                path=path
            )

    else:

        field = path.split(".")[-1]

        rows.append({
            "ticker": ticker,
            "provider": provider,
            "statement": statement,
            "quarter": quarter,
            "field": field,
            "raw_value": node
        })

# ============================================================
# RAW CSV EXPORT
# ============================================================

def append_raw_rows(rows):

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

# ============================================================
# PROVIDER EXECUTION
# ============================================================

def fetch_provider(
    ticker,
    provider
):

    cfg = PROVIDERS[provider]

    retries = cfg["retries"]

    delay = cfg["delay"]

    for attempt in range(1, retries + 2):

        try:

            sleep_time = (
                delay
                + random.uniform(0.5, 1.5)
            )

            time.sleep(sleep_time)

            log(
                f"[FETCH][{ticker}] "
                f"provider={provider} "
                f"attempt={attempt} "
                f"delay={round(sleep_time,2)}"
            )

            payload = FETCHERS[provider](ticker)

            payload_path = save_payload(
                ticker,
                provider,
                payload
            )

            rows = []

            for statement, value in payload.items():

                extract_fields(
                    ticker=ticker,
                    provider=provider,
                    node=value,
                    statement=statement,
                    quarter=None,
                    rows=rows
                )

            append_raw_rows(rows)

            fields = sorted(
                list(set([
                    x["field"]
                    for x in rows
                ]))
            )

            log(
                f"[SUCCESS][{ticker}] "
                f"provider={provider} "
                f"fields={len(fields)} "
                f"payload={payload_path}"
            )

            log(
                f"[FIELDS][{ticker}] "
                f"provider={provider} "
                f"{','.join(fields)}"
            )

            return {
                "provider": provider,
                "success": True,
                "fields": fields,
                "rows": len(rows)
            }

        except Exception as e:

            log(
                f"[ERROR][{ticker}] "
                f"provider={provider} "
                f"attempt={attempt} "
                f"error={str(e)}"
            )

            log(traceback.format_exc())

    return {
        "provider": provider,
        "success": False
    }

# ============================================================
# MAIN TICKER FLOW
# ============================================================

def fetch_ticker(ticker):

    log("=" * 80)
    log(f"[START] ticker={ticker}")

    results = []

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = {

            executor.submit(
                fetch_provider,
                ticker,
                provider
            ): provider

            for provider in PROVIDERS
        }

        for future in as_completed(futures):

            results.append(
                future.result()
            )

    log(f"[END] ticker={ticker}")

    return results

# ============================================================
# ENTRYPOINT
# ============================================================

if __name__ == "__main__":

    tickers = [
        "BDL",
        "GRSE"
    ]

    for ticker in tickers:

        fetch_ticker(ticker)

    log("RAW FETCH INGESTION COMPLETE")
