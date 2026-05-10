import json
import time
import requests
import yfinance as yf

from bs4 import BeautifulSoup
from datetime import datetime, UTC
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

RAW_FILE = BASE_DIR / "raw_fundamentals.json"
SYMBOLS_FILE = BASE_DIR / "unified-symbols.json"
SYMBOL_MAP_FILE = BASE_DIR / "symbol_map.json"
LOG_FILE = BASE_DIR / "runtime.log"

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


def clean(value):

    if value in [None, "", "-"]:
        return None

    try:

        value = (
            str(value)
            .replace(",", "")
            .replace("%", "")
            .strip()
        )

        return float(value)

    except Exception:

        return value


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

    ticker = ticker.upper()

    return (
        ticker.startswith("SGB")
        or "BOND" in ticker
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


def append_observation(stock, observation):

    stock["observations"].append(
        observation
    )


def fetch_yahoo(ticker):

    observations = []

    try:

        yahoo_symbol = resolve_yahoo_symbol(
            ticker
        )

        stock = yf.Ticker(
            yahoo_symbol
        )

        info = stock.info

        observations.append({

            "provider": "yahoo_finance",

            "fetched_at": now(),

            "raw": {

                "symbol": yahoo_symbol,

                "info": info
            }
        })

        try:

            hist = stock.history(
                period="1y",
                interval="1d"
            )

            if not hist.empty:

                rows = []

                for idx, row in hist.iterrows():

                    rows.append({

                        "date": str(idx.date()),

                        "open": clean(
                            row.get("Open")
                        ),

                        "high": clean(
                            row.get("High")
                        ),

                        "low": clean(
                            row.get("Low")
                        ),

                        "close": clean(
                            row.get("Close")
                        ),

                        "volume": clean(
                            row.get("Volume")
                        )
                    })

                observations.append({

                    "provider": "yahoo_finance",

                    "fetched_at": now(),

                    "raw": {

                        "price_history": rows
                    }
                })

        except Exception:
            pass

    except Exception as e:

        observations.append({

            "provider": "yahoo_finance",

            "fetched_at": now(),

            "raw": {

                "error": str(e)
            }
        })

    return observations


def parse_table(table):

    rows = table.select("tr")

    if len(rows) < 2:
        return []

    columns = []

    for col in rows[0].select("th,td")[1:]:

        columns.append(
            col.get_text(strip=True)
        )

    parsed = []

    for period in columns:

        parsed.append({
            "period": period
        })

    for row in rows[1:]:

        cols = row.select("th,td")

        if len(cols) < 2:
            continue

        label = (
            cols[0]
            .get_text(" ", strip=True)
            .lower()
        )

        values = cols[1:]

        for idx, value_col in enumerate(values):

            if idx >= len(parsed):
                continue

            parsed[idx][label] = clean(
                value_col.get_text(strip=True)
            )

    return parsed


def fetch_screener(ticker):

    observations = []

    try:

        screener_symbol = resolve_screener_symbol(
            ticker
        )

        url = (
            f"https://www.screener.in/company/"
            f"{screener_symbol}/"
        )

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        tables_dump = {}

        for section in soup.select("section"):

            heading = section.select_one("h2")

            if not heading:
                continue

            section_name = (
                heading
                .get_text(" ", strip=True)
                .lower()
            )

            table = section.select_one(
                "table.data-table"
            )

            if not table:
                continue

            parsed = parse_table(
                table
            )

            if parsed:

                tables_dump[
                    section_name
                ] = parsed

        observations.append({

            "provider": "screener",

            "fetched_at": now(),

            "raw": tables_dump
        })

    except Exception as e:

        observations.append({

            "provider": "screener",

            "fetched_at": now(),

            "raw": {

                "error": str(e)
            }
        })

    return observations


def main():

    Path(LOG_FILE).write_text(
        "",
        encoding="utf-8"
    )

    start = time.time()

    store = load_json(
        RAW_FILE
    )

    master = load_json(
        SYMBOLS_FILE
    )

    symbols = master.get(
        "symbols",
        []
    )

    processed = 0

    for symbol in symbols:

        ticker = symbol["ticker"]

        if ticker in DELISTED:
            continue

        if is_bond(ticker):
            continue

        stock = ensure_stock(
            store,
            symbol
        )

        yahoo_observations = fetch_yahoo(
            ticker
        )

        for observation in yahoo_observations:

            append_observation(
                stock,
                observation
            )

        screener_observations = fetch_screener(
            ticker
        )

        for observation in screener_observations:

            append_observation(
                stock,
                observation
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

    summary = f"""
==================================================
RAW FUNDAMENTALS SUMMARY
==================================================

Stocks Processed : {processed}

Runtime Seconds  : {runtime}

Updated At       : {now()}

==================================================
"""

    print(summary)

    with open(LOG_FILE, "a", encoding="utf-8") as f:

        f.write(summary)


if __name__ == "__main__":

    main()
