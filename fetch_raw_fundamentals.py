import json
import time
import requests
import yfinance as yf

from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime, UTC


import subprocess

REPO_ROOT = Path(
    subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"]
    ).decode().strip()
)

RAW_DIR = REPO_ROOT / "raw"
LOG_DIR = REPO_ROOT / "logs"

YAHOO_HISTORY_FILE = RAW_DIR / "yahoo_finance" / "history.json"
YAHOO_DELTA_FILE = RAW_DIR / "yahoo_finance" / "delta.json"

SCREENER_HISTORY_FILE = RAW_DIR / "screener" / "history.json"
SCREENER_DELTA_FILE = RAW_DIR / "screener" / "delta.json"

YAHOO_RUNTIME_HISTORY = LOG_DIR / "yahoo_runtime_history.json"
YAHOO_RUNTIME_DELTA = LOG_DIR / "yahoo_runtime_delta.json"

SCREENER_RUNTIME_HISTORY = LOG_DIR / "screener_runtime_history.json"
SCREENER_RUNTIME_DELTA = LOG_DIR / "screener_runtime_delta.json"

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

    path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[SAVE] {path.resolve()}")

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




def build_runtime():

    return {
        "started_at": now(),
        "completed_at": None,
        "runtime_seconds": 0,
        "processed": 0,
        "success": 0,
        "failed": 0,
        "failures": []
    }


def append_runtime(path, payload):

    history = load_json(path)

    if not isinstance(history, list):
        history = []

    history.append(payload)

    save_json(path, history)


def main():

    start = time.time()

    print(f"[CWD] {Path.cwd()}")
    print(f"[REPO_ROOT] {REPO_ROOT}")

    previous_yahoo_store = load_json(
        YAHOO_HISTORY_FILE
    )

    previous_screener_store = load_json(
        SCREENER_HISTORY_FILE
    )

    yahoo_store = {}
    yahoo_delta = {}

    screener_store = {}
    screener_delta = {}

    yahoo_runtime = build_runtime()
    screener_runtime = build_runtime()

    symbols_master = load_json(
        SYMBOLS_FILE
    )

    symbols = symbols_master.get(
        "symbols",
        []
    )

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

        # -------------------------------------------------
        # YAHOO
        # -------------------------------------------------

        yahoo_runtime["processed"] += 1

        yahoo_stock = ensure_stock(
            yahoo_store,
            symbol
        )

        try:

            yahoo_payload = fetch_yahoo_payload(
                ticker
            )

            add_observation(
                yahoo_stock,
                "yahoo_finance",
                yahoo_payload
            )

            previous = previous_yahoo_store.get(
                ticker
            )

            if previous != yahoo_stock:
                yahoo_delta[ticker] = yahoo_stock

            yahoo_runtime["success"] += 1

        except Exception as e:

            yahoo_runtime["failed"] += 1

            yahoo_runtime["failures"].append({
                "ticker": ticker,
                "error": str(e)
            })

            add_observation(
                yahoo_stock,
                "yahoo_finance",
                {
                    "error": str(e)
                }
            )

        save_json(
            YAHOO_HISTORY_FILE,
            yahoo_store
        )

        save_json(
            YAHOO_DELTA_FILE,
            yahoo_delta
        )

        save_json(
            YAHOO_RUNTIME_DELTA,
            yahoo_runtime
        )

        # -------------------------------------------------
        # SCREENER
        # -------------------------------------------------

        screener_runtime["processed"] += 1

        screener_stock = ensure_stock(
            screener_store,
            symbol
        )

        try:

            screener_payload = fetch_screener_payload(
                ticker
            )

            add_observation(
                screener_stock,
                "screener",
                screener_payload
            )

            previous = previous_screener_store.get(
                ticker
            )

            if previous != screener_stock:
                screener_delta[ticker] = screener_stock

            screener_runtime["success"] += 1

        except Exception as e:

            screener_runtime["failed"] += 1

            screener_runtime["failures"].append({
                "ticker": ticker,
                "error": str(e)
            })

            add_observation(
                screener_stock,
                "screener",
                {
                    "error": str(e)
                }
            )

        save_json(
            SCREENER_HISTORY_FILE,
            screener_store
        )

        save_json(
            SCREENER_DELTA_FILE,
            screener_delta
        )

        save_json(
            SCREENER_RUNTIME_DELTA,
            screener_runtime
        )

    runtime = round(
        time.time() - start,
        2
    )

    yahoo_runtime["runtime_seconds"] = runtime
    yahoo_runtime["completed_at"] = now()

    screener_runtime["runtime_seconds"] = runtime
    screener_runtime["completed_at"] = now()

    append_runtime(
        YAHOO_RUNTIME_HISTORY,
        yahoo_runtime
    )

    append_runtime(
        SCREENER_RUNTIME_HISTORY,
        screener_runtime
    )

    save_json(
        YAHOO_RUNTIME_DELTA,
        yahoo_runtime
    )

    save_json(
        SCREENER_RUNTIME_DELTA,
        screener_runtime
    )

    print(f"""
==================================================
RAW FUNDAMENTALS SUMMARY
==================================================

Stocks Processed : {len(symbols)}
Skipped Bonds    : {skipped}

Runtime Seconds  : {runtime}

Updated At       : {now()}

==================================================
""")


if __name__ == "__main__":

    main()


# ==================================================
# GitHub Actions Requirement
# ==================================================
#
# continue-on-error: true
#
# ==================================================
