import json
import time
from pathlib import Path
from datetime import datetime, UTC

from fetch_raw_provider import (
    fetch_yahoo_history,
    fetch_screener_history
)

BASE_DIR = Path(__file__).resolve().parent

RAW_DIR = BASE_DIR / "raw"
LOG_DIR = BASE_DIR / "logs"

YAHOO_HISTORY = RAW_DIR / "yahoo_finance" / "history.json"
SCREENER_HISTORY = RAW_DIR / "screener" / "history.json"

RUNTIME_HISTORY = LOG_DIR / "runtime_history.json"
RUNTIME_DELTA = LOG_DIR / "runtime_delta.json"
FAILED_SYMBOLS = LOG_DIR / "failed_symbols.json"


def now():
    return datetime.now(UTC).isoformat()


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def append_runtime(payload):
    history = load_json(RUNTIME_HISTORY, [])
    history.append(payload)
    save_json(RUNTIME_HISTORY, history)


def main():

    started = time.time()

    symbols = load_json(
        BASE_DIR / "unified-symbols.json",
        {}
    ).get("symbols", [])

    yahoo_store = {}
    screener_store = {}
    failed_symbols = []

    yahoo_log = {
        "processed": 0,
        "success": 0,
        "failed": 0
    }

    screener_log = {
        "processed": 0,
        "success": 0,
        "failed": 0
    }

    for symbol in symbols:

        ticker = symbol["ticker"]

        print(f"[YAHOO] Processing {ticker}")

        try:
            yahoo_store[ticker] = fetch_yahoo_history(ticker)
            yahoo_log["success"] += 1

        except Exception as e:

            yahoo_log["failed"] += 1

            failed_symbols.append({
                "provider": "yahoo_finance",
                "ticker": ticker,
                "error": str(e)
            })

            print(f"[YAHOO FAILED] {ticker}: {e}")

        yahoo_log["processed"] += 1

        # incremental save
        save_json(YAHOO_HISTORY, yahoo_store)
        save_json(FAILED_SYMBOLS, failed_symbols)

    for symbol in symbols:

        ticker = symbol["ticker"]

        print(f"[SCREENER] Processing {ticker}")

        try:
            screener_store[ticker] = fetch_screener_history(ticker)
            screener_log["success"] += 1

        except Exception as e:

            screener_log["failed"] += 1

            failed_symbols.append({
                "provider": "screener",
                "ticker": ticker,
                "error": str(e)
            })

            print(f"[SCREENER FAILED] {ticker}: {e}")

        screener_log["processed"] += 1

        # incremental save
        save_json(SCREENER_HISTORY, screener_store)
        save_json(FAILED_SYMBOLS, failed_symbols)

    runtime_payload = {
        "run_at": now(),
        "runtime_seconds": round(time.time() - started, 2),
        "providers": {
            "yahoo_finance": yahoo_log,
            "screener": screener_log
        }
    }

    append_runtime(runtime_payload)
    save_json(RUNTIME_DELTA, runtime_payload)

    print("[DONE] Runtime logs saved")


if __name__ == "__main__":
    main()
