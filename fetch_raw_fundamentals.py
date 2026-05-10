import json
import requests
import yfinance as yf

from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime, UTC


BASE_DIR = Path(__file__).resolve().parent

SYMBOLS_FILE = BASE_DIR / "unified-symbols.json"
RAW_FILE = BASE_DIR / "raw_fundamentals.json"
LOG_FILE = BASE_DIR / "runtime.log"


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def now():
    return datetime.now(UTC).isoformat()


def log(level, msg):

    line = f"[{now()}] [{level}] {msg}"

    print(line)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_json(path):

    try:

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:

        return {}


def save_json(path, data):

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


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
            "market_data_history": [],
            "ratio_history": [],
            "ownership_history": [],
            "quarterly_history": []
        }

    return store[ticker]


def history_row(provider, values):

    return {
        "ts": now(),
        "p": provider,
        "v": values
    }


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

    history.append(
        history_row(
            provider,
            clean_values
        )
    )


def fetch_yahoo(ticker):

    info = yf.Ticker(
        f"{ticker}.NS"
    ).info

    return {
        "ltp": info.get("currentPrice"),
        "market_cap": info.get("marketCap"),
        "pe": info.get("trailingPE"),
        "pb": info.get("priceToBook"),
        "roe": info.get("returnOnEquity"),
        "beta": info.get("beta"),
        "dividend_yield": info.get("dividendYield")
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


def fetch_screener(ticker):

    url = (
        f"https://www.screener.in/company/{ticker}/"
    )

    response = requests.get(
        url,
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

    return ratios


def fetch_nse(ticker):

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

    return {
        "symbol": meta.get("symbol"),
        "industry": industry.get("industry"),
        "sector": industry.get("sector"),
        "basic_industry": industry.get("basicIndustry"),
        "listing_date": meta.get("listingDate")
    }


def cleanup_old_schema(store):

    for ticker, stock in store.items():

        for section in [
            "market_data_history",
            "ratio_history",
            "ownership_history",
            "quarterly_history"
        ]:

            cleaned = []

            for row in stock.get(section, []):

                if "timestamp" in row:
                    row["ts"] = row.pop("timestamp")

                if "provider" in row:
                    row["p"] = row.pop("provider")

                if "values" in row:
                    row["v"] = row.pop("values")

                values = row.get("v", {})

                clean_values = {
                    k: v
                    for k, v in values.items()
                    if v not in [None, "", [], {}]
                }

                if clean_values:
                    row["v"] = clean_values
                    cleaned.append(row)

            stock[section] = cleaned

        stock.pop(
            "fetch_events",
            None
        )


def main():

    master = load_json(
        SYMBOLS_FILE
    )

    symbols = master.get(
        "symbols",
        []
    )

    store = load_json(
        RAW_FILE
    )

    cleanup_old_schema(store)

    success = 0
    failed = 0

    for symbol in symbols:

        ticker = symbol["ticker"]

        log(
            "INFO",
            f"START ticker={ticker}"
        )

        stock = ensure_stock(
            store,
            symbol
        )

        try:

            yahoo = fetch_yahoo(
                ticker
            )

            append_if_changed(
                stock["market_data_history"],
                "yahoo_finance",
                yahoo
            )

            screener = fetch_screener(
                ticker
            )

            append_if_changed(
                stock["ratio_history"],
                "screener",
                screener
            )

            nse = fetch_nse(
                ticker
            )

            append_if_changed(
                stock["ownership_history"],
                "nse",
                nse
            )

            success += 1

            log(
                "INFO",
                f"SUCCESS ticker={ticker}"
            )

        except Exception as e:

            failed += 1

            log(
                "ERROR",
                f"FAILED ticker={ticker} error={str(e)}"
            )

    save_json(
        RAW_FILE,
        store
    )

    log(
        "INFO",
        f"SUMMARY success={success} failed={failed}"
    )


if __name__ == "__main__":

    main()
