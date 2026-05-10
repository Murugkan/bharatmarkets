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


WARNINGS = 0
ERRORS = 0

YAHOO_SUCCESS = 0
SCREENER_SUCCESS = 0
NSE_SUCCESS = 0


def now():
    return datetime.now(UTC).isoformat()


def today():
    return datetime.now(UTC).date().isoformat()


def reset_log():
    LOG_FILE.write_text("", encoding="utf-8")


def log(level, msg):

    line = f"[{level}] {msg}"

    print(line)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def warn(msg):

    global WARNINGS

    WARNINGS += 1

    log("WARN", msg)


def error(msg):

    global ERRORS

    ERRORS += 1

    log("ERROR", msg)


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


def is_bond(symbol):

    ticker = symbol.get(
        "ticker",
        ""
    )

    return (
        ticker.startswith("SGB")
        or "BOND" in ticker.upper()
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

                "industry": symbol.get("industry")
            },

            "price_history": [],

            "quarterly_history": [],

            "ratio_history": [],

            "ownership_history": []
        }

    return store[ticker]


def append_history(history, row, key):

    if not row:
        return

    if history:

        last_key = history[-1].get(key)

        if last_key == row.get(key):

            history[-1] = row

            return

    history.append(row)


def append_if_changed(history, provider, values):

    if not values:
        return

    clean_values = {
        k: v
        for k, v in values.items()
        if v not in [None, "", [], {}]
    }

    if not clean_values:
        return

    latest = None

    for row in reversed(history):

        if row.get("p") == provider:

            latest = row.get("v", {})

            break

    if latest == clean_values:
        return

    history.append({
        "ts": now(),
        "p": provider,
        "v": clean_values
    })


def fetch_price_snapshot(ticker):

    global YAHOO_SUCCESS

    yahoo_symbol = resolve_yahoo_symbol(
        ticker
    )

    stock = yf.Ticker(
        yahoo_symbol
    )

    info = stock.info

    YAHOO_SUCCESS += 1

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

        "symbol": yahoo_symbol,

        "close": current_price,

        "prev_close": previous_close,

        "change": change,

        "change_pct": change_pct,

        "open": info.get("open"),

        "high": info.get("dayHigh"),

        "low": info.get("dayLow"),

        "volume": info.get("volume"),

        "market_cap": info.get(
            "marketCap"
        ),

        "pe": info.get(
            "trailingPE"
        ),

        "pb": info.get(
            "priceToBook"
        ),

        "dividend_yield": info.get(
            "dividendYield"
        ),

        "beta": info.get(
            "beta"
        )
    }


def extract_percent(text):

    try:

        value = (
            text
            .replace("%", "")
            .split()[-1]
        )

        return float(value)

    except Exception:

        return None


def fetch_screener_ratios(ticker):

    global SCREENER_SUCCESS

    screener_symbol = resolve_screener_symbol(
        ticker
    )

    response = requests.get(
        f"https://www.screener.in/company/{screener_symbol}/",
        headers=HEADERS,
        timeout=20
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    ratios = {}

    for li in soup.select(
        "li.flex.flex-space-between"
    ):

        text = li.get_text(
            " ",
            strip=True
        )

        if "ROCE" in text:
            ratios["roce"] = extract_percent(text)

        elif "ROE" in text:
            ratios["roe"] = extract_percent(text)

    SCREENER_SUCCESS += 1

    return ratios


def fetch_nse_metadata(ticker):

    global NSE_SUCCESS

    session = requests.Session()

    session.get(
        "https://www.nseindia.com",
        headers=HEADERS,
        timeout=20
    )

    response = session.get(
        "https://www.nseindia.com/api/"
        f"quote-equity?symbol={ticker}",
        headers=HEADERS,
        timeout=20
    )

    data = response.json()

    meta = data.get(
        "metadata",
        {}
    )

    industry = data.get(
        "industryInfo",
        {}
    )

    NSE_SUCCESS += 1

    return {

        "symbol": meta.get(
            "symbol"
        ),

        "industry": industry.get(
            "industry"
        ),

        "sector": industry.get(
            "sector"
        ),

        "basic_industry": industry.get(
            "basicIndustry"
        ),

        "listing_date": meta.get(
            "listingDate"
        )
    }


def main():

    reset_log()

    start = time.time()

    master = load_json(
        SYMBOLS_FILE
    )

    symbols = master.get(
        "symbols",
        []
    )

    store = {}

    success = 0
    failed = 0

    for symbol in symbols:

        ticker = symbol["ticker"]

        stock = ensure_stock(
            store,
            symbol
        )

        try:

            if (
                ticker not in DELISTED
                and not is_bond(symbol)
            ):

                try:

                    price_snapshot = fetch_price_snapshot(
                        ticker
                    )

                    append_history(
                        stock["price_history"],
                        price_snapshot,
                        "d"
                    )

                except Exception as e:

                    warn(
                        f"ticker={ticker} "
                        f"provider=yahoo "
                        f"error={str(e)}"
                    )

                try:

                    ratios = fetch_screener_ratios(
                        ticker
                    )

                    append_if_changed(
                        stock["ratio_history"],
                        "screener",
                        ratios
                    )

                except Exception as e:

                    warn(
                        f"ticker={ticker} "
                        f"provider=screener "
                        f"error={str(e)}"
                    )

                try:

                    nse = fetch_nse_metadata(
                        ticker
                    )

                    append_if_changed(
                        stock["ownership_history"],
                        "nse",
                        nse
                    )

                except Exception as e:

                    warn(
                        f"ticker={ticker} "
                        f"provider=nse "
                        f"error={str(e)}"
                    )

            success += 1

        except Exception as e:

            failed += 1

            error(
                f"ticker={ticker} "
                f"fatal={str(e)}"
            )

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

Total Stocks       : {len(symbols)}
Successful         : {success}
Failed             : {failed}
Warnings           : {WARNINGS}

Yahoo Success      : {YAHOO_SUCCESS}
Screener Success   : {SCREENER_SUCCESS}
NSE Success        : {NSE_SUCCESS}

Runtime Seconds    : {runtime}

Output File        : raw_fundamentals.json
Updated At         : {now()}

==================================================
"""

    print(summary)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(summary)


if __name__ == "__main__":

    main()
