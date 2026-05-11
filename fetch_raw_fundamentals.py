import json
import requests
import yfinance as yf

from bs4 import BeautifulSoup
from pathlib import Path


# =========================================================
# FILES
# =========================================================

SYMBOLS_FILE = Path(
    "unified-symbols.json"
)

YAHOO_HISTORY_FILE = Path(
    "yahoo_finance_history.json"
)

SCREENER_HISTORY_FILE = Path(
    "screener_history.json"
)


# =========================================================
# HELPERS
# =========================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def load_json(path):

    if not path.exists():
        return {}

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):

    with open(path, "w", encoding="utf-8") as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


def ensure_stock(store, symbol):

    ticker = symbol["ticker"]

    if ticker not in store:

        store[ticker] = {
            "ticker": ticker,
            "company_name": symbol.get(
                "company_name"
            ),
            "observations": {}
        }

    return store[ticker]


def add_observation(
    stock,
    provider,
    payload
):

    stock["observations"][provider] = payload


# =========================================================
# YAHOO
# =========================================================

def fetch_yahoo_payload(
    ticker,
    yahoo_symbol
):

    stock = yf.Ticker(
        yahoo_symbol
    )

    hist = stock.history(
        period="1y",
        interval="1d"
    )

    return {
        "provider": "yahoo_finance",
        "provider_symbol": yahoo_symbol,
        "raw": {
            "info": stock.info,
            "history_1y_1d": (
                hist.reset_index()
                .astype(str)
                .to_dict("records")
            )
        }
    }


# =========================================================
# SCREENER
# =========================================================

def extract_table(table):

    rows = []

    for tr in table.select("tr"):

        cols = tr.select("th,td")

        row = [
            col.get_text(" ", strip=True)
            for col in cols
        ]

        if row:
            rows.append(row)

    return rows


def fetch_screener_payload(
    ticker,
    screener_symbol
):

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

    tables = []

    for section in soup.select("section"):

        table = section.select_one("table")

        if not table:
            continue

        heading = section.select_one("h2")

        tables.append({
            "section": (
                heading.get_text(
                    " ",
                    strip=True
                )
                if heading else None
            ),
            "rows": extract_table(table)
        })

    return {
        "provider": "screener",
        "provider_symbol": screener_symbol,
        "raw": {
            "url": url,
            "tables": tables
        }
    }


# =========================================================
# MAIN
# =========================================================

def main():

    yahoo_store = {}
    screener_store = {}

    symbols_master = load_json(
        SYMBOLS_FILE
    )

    symbols = symbols_master.get(
        "symbols",
        []
    )

    for symbol in symbols:

        ticker = str(
            symbol["ticker"]
        ).strip()

        # -------------------------------------------------
        # YAHOO
        # -------------------------------------------------

        try:

            yahoo_symbol = (
                ticker
                if "." in ticker
                else f"{ticker}.NS"
            )

            yahoo_payload = (
                fetch_yahoo_payload(
                    ticker,
                    yahoo_symbol
                )
            )

            yahoo_stock = ensure_stock(
                yahoo_store,
                symbol
            )

            add_observation(
                yahoo_stock,
                "yahoo_finance",
                yahoo_payload
            )

        except Exception as e:

            print(
                f"[YAHOO FAILED] "
                f"{ticker} :: {e}"
            )

        save_json(
            YAHOO_HISTORY_FILE,
            yahoo_store
        )

        # -------------------------------------------------
        # SCREENER
        # -------------------------------------------------

        try:

            screener_payload = (
                fetch_screener_payload(
                    ticker,
                    ticker
                )
            )

            screener_stock = ensure_stock(
                screener_store,
                symbol
            )

            add_observation(
                screener_stock,
                "screener",
                screener_payload
            )

        except Exception as e:

            print(
                f"[SCREENER FAILED] "
                f"{ticker} :: {e}"
            )

        save_json(
            SCREENER_HISTORY_FILE,
            screener_store
        )

    print()
    print("=" * 50)
    print("RAW FUNDAMENTALS SUMMARY")
    print("=" * 50)
    print()

    print(
        f"Stocks Processed : "
        f"{len(symbols)}"
    )

    print()
    print("=" * 50)


if __name__ == "__main__":
    main()
