import json
import time
import yfinance as yf

from pathlib import Path
from datetime import datetime, UTC


BASE_DIR = Path(__file__).resolve().parent

SYMBOLS_FILE = BASE_DIR / "unified-symbols.json"
SYMBOL_MAP_FILE = BASE_DIR / "symbol_map.json"

RAW_FILE = BASE_DIR / "raw_fundamentals.json"
LOG_FILE = BASE_DIR / "runtime.log"


def now():
    return datetime.now(UTC).isoformat()


def today():
    return datetime.now(UTC).date().isoformat()


def clean_num(value, digits=2):

    if value is None:
        return None

    try:
        return round(float(value), digits)

    except Exception:
        return value


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


def is_bond(symbol):

    ticker = symbol.get(
        "ticker",
        ""
    )

    return (
        ticker.startswith("SGB")
        or "BOND" in ticker.upper()
    )


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

                "sub_industry": None,

                "market_type": "EQUITY",

                "listing_date": None,

                "exchange": "NSE",

                "instrument_type": "STOCK",

                "face_value": None,

                "shares_outstanding": None,

                "index_membership": {

                    "nifty_50": False,

                    "nifty_next_50": False,

                    "nifty_100": False,

                    "nifty_200": False,

                    "nifty_500": False,

                    "sectoral": []
                }
            },

            "price_history": [],

            "quarterly_history": [],

            "guidance_history": [],

            "insights_history": [],

            "orderbook_history": [],

            "segment_history": [],

            "capital_allocation_history": []
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

        "delivery_volume": None,

        "delivery_pct": None,

        "vwap": None,

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
        ),

        "ath": None,

        "atl": None,

        "distance_from_52w_high_pct": None,

        "distance_from_52w_low_pct": None
    }


def build_empty_quarter():

    return {

        "quarter": None,

        "income_statement": {

            "revenue": None,
            "gross_profit": None,
            "ebitda": None,
            "ebit": None,
            "pbt": None,
            "net_profit": None,
            "eps": None,
            "interest": None,
            "depreciation": None,
            "tax": None
        },

        "margins": {

            "gross_margin_pct": None,
            "ebitda_margin_pct": None,
            "ebit_margin_pct": None,
            "net_margin_pct": None
        },

        "balance_sheet": {

            "cash": None,
            "debt": None,
            "net_debt": None,
            "equity": None,
            "book_value": None,
            "inventory": None,
            "receivables": None,
            "payables": None,
            "current_assets": None,
            "current_liabilities": None,
            "total_assets": None
        },

        "cashflow": {

            "operating_cashflow": None,
            "capex": None,
            "free_cashflow": None
        },

        "operations": {

            "employee_count": None,
            "utilization_pct": None,
            "capacity": None,
            "capacity_expansion": None
        },

        "orders": {

            "order_book": None,
            "order_inflow": None,
            "pipeline": None
        },

        "segment_mix": {},

        "geography_mix": {},

        "shareholding": {

            "promoter_pct": None,
            "fii_pct": None,
            "dii_pct": None,
            "public_pct": None
        },

        "derived": {

            "roe_pct": None,
            "roce_pct": None,
            "asset_turnover": None,
            "debt_to_equity": None,
            "working_capital_days": None
        }
    }


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

    processed = 0

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

                snapshot = fetch_price_snapshot(
                    ticker
                )

                append_daily(
                    stock["price_history"],
                    snapshot
                )

            processed += 1

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
FOUNDATION FREEZE SUMMARY
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
