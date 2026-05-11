import json
from pathlib import Path

from fetch_raw_provider import (
    fetch_yahoo_payload,
    fetch_screener_payload
)

# =========================================================
# ROOT FILES
# =========================================================

YAHOO_HISTORY_FILE = Path(
    "yahoo_finance_history.json"
)

SCREENER_HISTORY_FILE = Path(
    "screener_history.json"
)

SYMBOLS_FILE = Path(
    "unified-symbols.json"
)

# =========================================================
# HELPERS
# =========================================================

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

        ticker = symbol["ticker"]

        # -------------------------------------------------
        # YAHOO
        # -------------------------------------------------

        try:

            yahoo_payload = (
                fetch_yahoo_payload(
                    ticker,
                    ticker
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
