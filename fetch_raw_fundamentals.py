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
            "name": symbol.get("name"),
            "sector": symbol.get("sector"),
            "market_data_history": [],
            "ratio_history": [],
            "ownership_history": [],
            "quarterly_history": []
        }

    return store[ticker]


def append_history(section, provider, values, ts=None):

    return {
        "ts": ts or now(),
        "p": provider,
        "v": values
    }


def fetch_yahoo(ticker):

    yf_ticker = yf.Ticker(f"{ticker}.NS")

    info = yf_ticker.info

    return {
        "ltp": info.get("currentPrice"),
        "market_cap": info.get("marketCap"),
        "pe": info.get("trailingPE"),
        "pb": info.get("priceToBook"),
        "roe": info.get("returnOnEquity"),
        "beta": info.get("beta")
    }


def fetch_screener(ticker):

    url = f"https://www.screener.in/company/{ticker}/"

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

    for li in soup.select("li.flex.flex-space-between"):

        text = li.get_text(" ", strip=True)

        if "ROCE" in text:
            ratios["roce_raw"] = text

        if "ROE" in text:
            ratios["roe_raw"] = text

    return {
        "top_ratios": ratios,
        "raw_html_size": len(response.text)
    }


def fetch_nse(ticker):

    url = (
        "https://www.nseindia.com/api/"
        f"quote-equity?symbol={ticker}"
    )

    session = requests.Session()

    session.get(
        "https://www.nseindia.com",
        headers=HEADERS,
        timeout=20
    )

    response = session.get(
        url,
        headers=HEADERS,
        timeout=20
    )

    data = response.json()

    return {
        "industry": data.get("industryInfo", {}),
        "metadata": data.get("metadata", {})
    }


def main():

    master = load_json(SYMBOLS_FILE)

    symbols = master.get("symbols", [])

    store = load_json(RAW_FILE)

    success = 0
    failed = 0

    for symbol in symbols:

        ticker = symbol["ticker"]

        log("INFO", f"START ticker={ticker}")

        stock = ensure_stock(store, symbol)

        try:

            yahoo = fetch_yahoo(ticker)

            stock["market_data_history"].append(
                append_history(
                    "market",
                    "yahoo_finance",
                    yahoo
                )
            )

            screener = fetch_screener(ticker)

            stock["ratio_history"].append(
                append_history(
                    "ratio",
                    "screener",
                    screener
                )
            )

            nse = fetch_nse(ticker)

            stock["ownership_history"].append(
                append_history(
                    "ownership",
                    "nse",
                    nse
                )
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

    save_json(RAW_FILE, store)

    log(
        "INFO",
        f"SUMMARY success={success} failed={failed}"
    )


if __name__ == "__main__":

    main()
