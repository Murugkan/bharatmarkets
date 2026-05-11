
# Runtime/Data Architecture
# raw/yahoo_finance/history.json
# raw/yahoo_finance/delta.json
# raw/screener/history.json
# raw/screener/delta.json
#
# logs/yahoo_runtime_history.json
# logs/yahoo_runtime_delta.json
# logs/screener_runtime_history.json
# logs/screener_runtime_delta.json

import json
import time
import requests
import yfinance as yf

from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime, UTC


BASE_DIR = Path(__file__).resolve().parent

RAW_FILE = BASE_DIR / "raw_fundamentals.json"
SYMBOLS_FILE = BASE_DIR / "unified-symbols.json"
SYMBOL_MAP_FILE = BASE_DIR / "symbol_map.json"

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


symbol_map = load_json(
    SYMBOL_MAP_FILE
)

YAHOO_OVERRIDES = symbol_map.get(
    "overrides",
    {}
)

SCREENER_OVERRIDES = symbol_map.get(
    "screener_overrides",
    {}
)

DELISTED = set(
    symbol_map.get(
        "delisted",
        []
    )
)


def is_bond(ticker):

    t = str(ticker).upper().strip()

    return (
        t.startswith("SGB")
        or "BOND" in t
    )


def resolve_yahoo_symbol(ticker):

    return YAHOO_OVERRIDES.get(
        ticker,
        f"{ticker}.NS"
    )


def resolve_screener_symbol(ticker):

    return SCREENER_OVERRIDES.get(
        ticker,
        ticker
    )


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


def fetch_yahoo_payload(ticker):

    payload = {}

    yahoo_symbol = resolve_yahoo_symbol(
        ticker
    )

    stock = yf.Ticker(
        yahoo_symbol
    )

    try:

        payload["info"] = stock.info

    except Exception as e:

        payload["info_error"] = str(e)

    try:

        hist = stock.history(
            period="1y",
            interval="1d"
        )

        payload["history_1y_1d"] = (
            hist
            .reset_index()
            .astype(str)
            .to_dict("records")
        )

    except Exception as e:

        payload["history_error"] = str(e)

    return payload


def extract_table(table):

    rows = []

    for tr in table.select("tr"):

        cols = tr.select("th,td")

        row = []

        for col in cols:

            row.append(
                col.get_text(" ", strip=True)
            )

        if row:
            rows.append(row)

    return rows


def fetch_screener_payload(ticker):

    payload = {}

    screener_symbol = resolve_screener_symbol(
        ticker
    )

    url = (
        f"https://www.screener.in/company/"
        f"{screener_symbol}/"
    )

    payload["url"] = url

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    payload["tables"] = []

    for section in soup.select("section"):

        table = section.select_one("table")

        if not table:
            continue

        heading = section.select_one("h2")

        payload["tables"].append({

            "section": (
                heading.get_text(
                    " ",
                    strip=True
                )
                if heading else None
            ),

            "rows": extract_table(
                table
            )
        })

    return payload


def main():

    start = time.time()

    store = {}

    symbols_master = load_json(
        SYMBOLS_FILE
    )

    symbols = symbols_master.get(
        "symbols",
        []
    )

    processed = 0
    skipped = 0

    for symbol in symbols:

        ticker = str(
            symbol["ticker"]
        ).strip()

        if ticker in DELISTED:
            continue

        if is_bond(ticker):

            skipped += 1
            continue

        stock = ensure_stock(
            store,
            symbol
        )

        try:

            yahoo_payload = fetch_yahoo_payload(
                ticker
            )

            add_observation(
                stock,
                "yahoo_finance",
                yahoo_payload
            )

        except Exception as e:

            add_observation(
                stock,
                "yahoo_finance",
                {
                    "error": str(e)
                }
            )

        try:

            screener_payload = fetch_screener_payload(
                ticker
            )

            add_observation(
                stock,
                "screener",
                screener_payload
            )

        except Exception as e:

            add_observation(
                stock,
                "screener",
                {
                    "error": str(e)
                }
            )

        processed += 1

    save_json(
        RAW_FILE,
        store
    )

    runtime = round(
        time.time() - start,
        2
    )

    print(f"""
==================================================
RAW FUNDAMENTALS SUMMARY
==================================================

Stocks Processed : {processed}
Skipped Bonds    : {skipped}

Runtime Seconds  : {runtime}

Updated At       : {now()}

==================================================
""")


if __name__ == "__main__":

    main()


# GitHub Actions workflow should use:
# continue-on-error: true
