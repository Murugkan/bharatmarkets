
import json
import traceback
from datetime import datetime, UTC

MASTER_SYMBOLS_FILE = "unified-symbols.json"
RAW_FUNDAMENTALS_FILE = "raw_fundamentals.json"
RUNTIME_LOG_FILE = "runtime.log"


def now():
    return datetime.now(UTC).isoformat()


def log(level, message):

    line = f"[{now()}] [{level}] {message}"

    print(line)

    with open(
        RUNTIME_LOG_FILE,
        "a",
        encoding="utf-8"
    ) as f:

        f.write(line + "\n")


def load_json(path):

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception:

        return {}


def save_json(path, data):

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


def ensure_stock(raw_store, symbol):

    ticker = symbol["ticker"]

    if ticker not in raw_store:

        raw_store[ticker] = {
            "metadata": {
                "ticker": ticker,
                "name": symbol.get("name"),
                "isin": symbol.get("isin"),
                "sector": symbol.get("sector"),
                "industry": symbol.get("industry"),
                "type": symbol.get("type"),
                "created_at": now(),
                "updated_at": now()
            },
            "market_data_history": [],
            "ratio_history": [],
            "ownership_history": [],
            "quarterly_history": [],
            "fetch_events": []
        }

    return raw_store[ticker]


def append_history(
    stock,
    section,
    provider,
    values,
    timestamp=None
):

    stock[section].append({
        "timestamp": timestamp or now(),
        "provider": provider,
        "values": values
    })


def append_fetch_event(
    stock,
    provider,
    success,
    warning=None,
    error=None
):

    stock["fetch_events"].append({
        "timestamp": now(),
        "provider": provider,
        "success": success,
        "warning": warning,
        "error": error
    })


def ingest_provider_payload(
    stock,
    provider,
    payload
):

    if provider == "yahoo_finance":

        append_history(
            stock,
            "market_data_history",
            provider,
            payload
        )

    elif provider == "nse":

        append_history(
            stock,
            "ownership_history",
            provider,
            payload
        )

    elif provider == "screener":

        ratios = payload.get(
            "top_ratios",
            {}
        )

        if ratios:

            append_history(
                stock,
                "ratio_history",
                provider,
                ratios
            )

        quarterly = payload.get(
            "quarterly",
            []
        )

        for row in quarterly:

            append_history(
                stock,
                "quarterly_history",
                provider,
                row,
                row.get("quarter")
            )


def main():

    master = load_json(
        MASTER_SYMBOLS_FILE
    )

    symbols = master.get(
        "symbols",
        []
    )

    raw_store = load_json(
        RAW_FUNDAMENTALS_FILE
    )

    success_count = 0
    failure_count = 0

    for symbol in symbols:

        ticker = symbol["ticker"]

        log(
            "INFO",
            f"START ticker={ticker}"
        )

        stock = ensure_stock(
            raw_store,
            symbol
        )

        try:

            yahoo_payload = {
                "ltp": None,
                "market_cap": None
            }

            screener_payload = {
                "top_ratios": {},
                "quarterly": []
            }

            nse_payload = {
                "promoter": None
            }

            ingest_provider_payload(
                stock,
                "yahoo_finance",
                yahoo_payload
            )

            ingest_provider_payload(
                stock,
                "screener",
                screener_payload
            )

            ingest_provider_payload(
                stock,
                "nse",
                nse_payload
            )

            append_fetch_event(
                stock,
                "all",
                True
            )

            stock["metadata"]["updated_at"] = now()

            success_count += 1

            log(
                "INFO",
                f"SUCCESS ticker={ticker}"
            )

        except Exception as e:

            append_fetch_event(
                stock,
                "all",
                False,
                error=str(e)
            )

            failure_count += 1

            log(
                "ERROR",
                f"FAILED ticker={ticker} error={str(e)}"
            )

            log(
                "ERROR",
                traceback.format_exc()
            )

    save_json(
        RAW_FUNDAMENTALS_FILE,
        raw_store
    )

    log(
        "INFO",
        f"SUMMARY total={len(symbols)} success={success_count} failed={failure_count}"
    )


if __name__ == "__main__":

    main()
