import json
import time
import requests
import yfinance as yf

from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime, UTC


BASE_DIR = Path(__file__).resolve().parent

SYMBOLS_FILE = BASE_DIR / "unified-symbols.json"
SYMBOL_MAP_FILE = BASE_DIR / "symbol_map.json"

RAW_FILE = BASE_DIR / "raw_fundamentals.json"
LOG_FILE = BASE_DIR / "runtime.log"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def now():
    return datetime.now(UTC).isoformat()


def today():
    return datetime.now(UTC).date().isoformat()


def clean_num(value, digits=2):

    if value in [None, "", "-"]:
        return None

    try:

        value = (
            str(value)
            .replace(",", "")
            .replace("%", "")
            .strip()
        )

        return round(float(value), digits)

    except Exception:

        return None


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

OVERRIDES = symbol_map.get(
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


def resolve_yahoo_symbol(ticker):

    mapped = OVERRIDES.get(
        ticker
    )

    if mapped:
        return mapped

    return f"{ticker}.NS"


def resolve_screener_symbol(ticker):

    mapped = SCREENER_OVERRIDES.get(
        ticker
    )

    if mapped:
        return mapped

    return ticker


def ensure_stock(store, symbol):

    ticker = symbol["ticker"]

    if ticker not in store:

        store[ticker] = {

            "metadata": {

                "ticker": ticker,
                "name": symbol.get("name"),
                "isin": symbol.get("isin"),
                "sector": symbol.get("sector"),
                "industry": symbol.get("industry"),
                "updated_at": now()
            },

            "price_history": [],

            "quarterly_history": [],

            "guidance_history": [],

            "insights_history": [],

            "orderbook_history": [],

            "segment_history": [],

            "capital_allocation_history": [],

            "provider_raw": {

                "yahoo_finance": {},
                "screener": {},
                "nse": {}
            }
        }

    return store[ticker]


def append_daily(history, row):

    if not row:
        return

    if history and history[-1].get("d") == row.get("d"):

        history[-1] = row
        return

    history.append(row)


def fetch_price_snapshot(ticker):

    yahoo_symbol = resolve_yahoo_symbol(
        ticker
    )

    stock = yf.Ticker(
        yahoo_symbol
    )

    info = stock.info

    current_price = info.get(
        "currentPrice"
    )

    previous_close = info.get(
        "previousClose"
    )

    change = None
    change_pct = None

    if (
        current_price is not None
        and previous_close not in [None, 0]
    ):

        change = (
            current_price
            - previous_close
        )

        change_pct = (
            change
            / previous_close
            * 100
        )

    return {

        "d": today(),

        "open": clean_num(
            info.get("open")
        ),

        "high": clean_num(
            info.get("dayHigh")
        ),

        "low": clean_num(
            info.get("dayLow")
        ),

        "close": clean_num(
            current_price
        ),

        "prev_close": clean_num(
            previous_close
        ),

        "change": clean_num(
            change
        ),

        "change_pct": clean_num(
            change_pct
        ),

        "volume": info.get(
            "volume"
        ),

        "market_cap": info.get(
            "marketCap"
        ),

        "pe": clean_num(
            info.get("trailingPE")
        ),

        "pb": clean_num(
            info.get("priceToBook")
        ),

        "dividend_yield": clean_num(
            info.get("dividendYield")
        ),

        "beta": clean_num(
            info.get("beta")
        ),

        "w52_high": clean_num(
            info.get("fiftyTwoWeekHigh")
        ),

        "w52_low": clean_num(
            info.get("fiftyTwoWeekLow")
        )
    }


def parse_table(table):

    rows = table.select("tr")

    if len(rows) < 2:
        return []

    headers = []

    for th in rows[0].select("th,td")[1:]:

        headers.append(
            th.get_text(strip=True)
        )

    parsed = []

    for i in range(len(headers)):

        parsed.append({
            "quarter": headers[i]
        })

    for row in rows[1:]:

        cols = row.select("th,td")

        if len(cols) < 2:
            continue

        label = cols[0].get_text(
            " ",
            strip=True
        )

        values = cols[1:]

        for i, col in enumerate(values):

            if i >= len(parsed):
                continue

            parsed[i][label] = clean_num(
                col.get_text(strip=True)
            )

    return parsed


def fetch_screener_quarterly(ticker):

    screener_symbol = resolve_screener_symbol(
        ticker
    )

    response = requests.get(
        f"https://www.screener.in/company/{screener_symbol}/",
        headers=HEADERS,
        timeout=30
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    result = []

    sections = soup.select("section")

    for section in sections:

        title_el = section.select_one("h2")

        if not title_el:
            continue

        title = title_el.get_text(
            " ",
            strip=True
        ).lower()

        if "quarterly results" not in title:
            continue

        table = section.select_one(
            "table.data-table"
        )

        if not table:
            continue

        parsed = parse_table(table)

        for q in parsed:

            row = {

                "quarter": q.get(
                    "quarter"
                ),

                "income_statement": {

                    "revenue": q.get("Sales"),

                    "ebitda": q.get(
                        "Operating Profit"
                    ),

                    "net_profit": q.get(
                        "Net Profit"
                    ),

                    "eps": q.get("EPS in Rs")
                },

                "margins": {

                    "ebitda_margin_pct": q.get(
                        "OPM %"
                    ),

                    "net_margin_pct": q.get(
                        "NPM %"
                    )
                },

                "balance_sheet": {},

                "cashflow": {},

                "operations": {},

                "orders": {},

                "segment_mix": {},

                "geography_mix": {},

                "shareholding": {},

                "derived": {}
            }

            result.append(row)

    return result


def main():

    Path(LOG_FILE).write_text(
        "",
        encoding="utf-8"
    )

    start = time.time()

    master = load_json(
        SYMBOLS_FILE
    )

    symbols = master.get(
        "symbols",
        []
    )

    store = {}

    for symbol in symbols:

        ticker = symbol["ticker"]

        if ticker in DELISTED:
            continue

        stock = ensure_stock(
            store,
            symbol
        )

        try:

            price = fetch_price_snapshot(
                ticker
            )

            append_daily(
                stock["price_history"],
                price
            )

            stock["provider_raw"][
                "yahoo_finance"
            ] = price

        except Exception:
            pass

        try:

            quarterly = fetch_screener_quarterly(
                ticker
            )

            stock[
                "quarterly_history"
            ] = quarterly

            stock["provider_raw"][
                "screener"
            ] = {
                "quarterly_count": len(
                    quarterly
                )
            }

        except Exception:
            pass

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

Stocks Processed : {len(symbols)}

Runtime Seconds  : {runtime}

Updated At       : {now()}

==================================================
"""

    print(summary)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(summary)


if __name__ == "__main__":

    main()
