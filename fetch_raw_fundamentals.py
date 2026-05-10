import json
import traceback
from pathlib import Path
from datetime import datetime, UTC

BASE_DIR = Path(__file__).resolve().parent

MASTER_SYMBOLS_FILE = BASE_DIR / "unified-symbols.json"
RAW_FUNDAMENTALS_FILE = BASE_DIR / "raw_fundamentals.json"
FUNDAMENTALS_FILE = BASE_DIR / "fundamentals.json"
GUIDANCE_FILE = BASE_DIR / "guidance.json"
RUNTIME_LOG_FILE = BASE_DIR / "runtime.log"
RAW_PAYLOADS_DIR = BASE_DIR / "raw_payloads"

RAW_PAYLOADS_DIR.mkdir(exist_ok=True)


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


def save_payload(
    ticker,
    provider,
    payload
):

    path = (
        RAW_PAYLOADS_DIR /
        f"{ticker}_{provider}.json"
    )

    save_json(path, payload)

    log(
        "INFO",
        f"PAYLOAD_SAVED "
        f"ticker={ticker} "
        f"provider={provider} "
        f"path={path}"
    )


def ensure_stock(
    raw_store,
    symbol
):

    ticker = symbol["ticker"]

    if ticker not in raw_store:

        raw_store[ticker] = {
            "metadata": {
                "ticker": ticker,
                "name": symbol.get("name"),
                "isin": symbol.get("isin"),
                "sector": symbol.get("sector"),
                "industry": symbol.get("industry"),
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
    error=None
):

    stock["fetch_events"].append({
        "timestamp": now(),
        "provider": provider,
        "success": success,
        "error": error
    })


def ingest_screener(
    stock,
    payload
):

    top_ratios = payload.get(
        "top_ratios",
        {}
    )

    if top_ratios:

        append_history(
            stock,
            "ratio_history",
            "screener",
            top_ratios
        )

    quarterly = payload.get(
        "quarterly",
        []
    )

    for row in quarterly:

        append_history(
            stock,
            "quarterly_history",
            "screener",
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
    failed_count = 0

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

            save_payload(
                ticker,
                "yahoo_finance",
                yahoo_payload
            )

            save_payload(
                ticker,
                "screener",
                screener_payload
            )

            save_payload(
                ticker,
                "nse",
                nse_payload
            )

            append_history(
                stock,
                "market_data_history",
                "yahoo_finance",
                yahoo_payload
            )

            ingest_screener(
                stock,
                screener_payload
            )

            append_history(
                stock,
                "ownership_history",
                "nse",
                nse_payload
            )

            append_fetch_event(
                stock,
                "all",
                True
            )

            stock["metadata"][
                "updated_at"
            ] = now()

            success_count += 1

            log(
                "INFO",
                f"SUCCESS ticker={ticker}"
            )

        except Exception as e:

            failed_count += 1

            append_fetch_event(
                stock,
                "all",
                False,
                str(e)
            )

            log(
                "ERROR",
                f"FAILED ticker={ticker} "
                f"error={str(e)}"
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
        f"SUMMARY total={len(symbols)} "
        f"success={success_count} "
        f"failed={failed_count}"
    )


if __name__ == "__main__":

    main()
