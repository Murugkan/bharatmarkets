import json
import time
from copy import deepcopy
from datetime import datetime, UTC
from pathlib import Path

# KEEP EXISTING PROVIDER IMPLEMENTATIONS
from fetch_raw_provider import (
    fetch_yahoo_history,
    fetch_screener_history
)

BASE_DIR = Path(__file__).resolve().parent

RAW_DIR = BASE_DIR / "raw"
LOG_DIR = BASE_DIR / "logs"

# =========================================================
# KEEP EXISTING STABLE FUNCTIONS FROM dump VERSION
# =========================================================
#
# DO NOT REMOVE FROM ORIGINAL BASE FILE:
#
# - resolve_yahoo_symbol()
# - resolve_screener_symbol()
# - add_observation()
# - metadata override loading
# - skip/delisted handling
# - provider resilience logic
#
# ONLY NEW ARCHITECTURE IMPLEMENTED BELOW:
# - provider split files
# - delta overwrite model
# - runtime split logs
# - incremental flush
#
# =========================================================


PROVIDERS = {
    "yahoo_finance": {
        "fetcher": fetch_yahoo_history,
        "raw_dir": RAW_DIR / "yahoo_finance",
        "runtime_history": LOG_DIR / "yahoo_runtime_history.json",
        "runtime_delta": LOG_DIR / "yahoo_runtime_delta.json"
    },
    "screener": {
        "fetcher": fetch_screener_history,
        "raw_dir": RAW_DIR / "screener",
        "runtime_history": LOG_DIR / "screener_runtime_history.json",
        "runtime_delta": LOG_DIR / "screener_runtime_delta.json"
    }
}


def now():
    return datetime.now(UTC).isoformat()


def load_json(path, default):

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return deepcopy(default)


def save_json(path, data):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


def has_changed(old, new):

    return json.dumps(
        old,
        sort_keys=True
    ) != json.dumps(
        new,
        sort_keys=True
    )


def build_runtime():

    return {
        "started_at": now(),
        "completed_at": None,
        "runtime_seconds": 0,
        "processed": 0,
        "success": 0,
        "failed": 0,
        "failures": []
    }


def process_provider(
    provider_name,
    provider_config,
    symbols
):

    started = time.time()

    fetcher = provider_config["fetcher"]

    raw_dir = provider_config["raw_dir"]

    history_file = raw_dir / "history.json"
    delta_file = raw_dir / "delta.json"

    runtime_history_file = (
        provider_config["runtime_history"]
    )

    runtime_delta_file = (
        provider_config["runtime_delta"]
    )

    # overwrite snapshot model
    latest_history = {}

    # current run delta only
    delta_store = {}

    # compare against previous snapshot
    previous_history = load_json(
        history_file,
        {}
    )

    runtime = build_runtime()

    for stock in symbols:

        ticker = stock.get("ticker")

        if not ticker:
            continue

        runtime["processed"] += 1

        try:

            # =====================================================
            # KEEP ORIGINAL RESOLUTION FLOW FROM dump VERSION
            # =====================================================
            #
            # Example:
            #
            # resolved_symbol = resolve_yahoo_symbol(ticker)
            #
            # DO NOT regress to:
            # f"{ticker}.NS"
            #
            # =====================================================

            latest = fetcher(ticker)

            latest_history[ticker] = latest

            previous = previous_history.get(ticker)

            if has_changed(previous, latest):

                delta_store[ticker] = latest

            runtime["success"] += 1

        except Exception as e:

            runtime["failed"] += 1

            runtime["failures"].append({
                "ticker": ticker,
                "error": str(e)
            })

            print(
                f"[FAILED] "
                f"{provider_name} :: "
                f"{ticker} :: {e}"
            )

        # =====================================================
        # INCREMENTAL FLUSH
        # =====================================================

        save_json(
            history_file,
            latest_history
        )

        save_json(
            delta_file,
            delta_store
        )

        save_json(
            runtime_delta_file,
            runtime
        )

    runtime["runtime_seconds"] = round(
        time.time() - started,
        2
    )

    runtime["completed_at"] = now()

    runtime_history = load_json(
        runtime_history_file,
        []
    )

    runtime_history.append(runtime)

    save_json(
        runtime_history_file,
        runtime_history
    )

    save_json(
        runtime_delta_file,
        runtime
    )

    print(f"[DONE] {provider_name}")


def main():

    overall_started = time.time()

    symbols_payload = load_json(
        BASE_DIR / "unified-symbols.json",
        {"symbols": []}
    )

    symbols = (
        symbols_payload.get("symbols", [])
        if isinstance(symbols_payload, dict)
        else symbols_payload
    )

    print("=" * 50)
    print("RAW FUNDAMENTALS START")
    print("=" * 50)

    for provider_name, provider_config in PROVIDERS.items():

        process_provider(
            provider_name,
            provider_config,
            symbols
        )

    print()
    print("=" * 50)
    print("RAW FUNDAMENTALS SUMMARY")
    print("=" * 50)
    print()

    print(f"Stocks Processed : {len(symbols)}")
    print()

    print(
        f"Runtime Seconds  : "
        f"{round(time.time() - overall_started, 2)}"
    )

    print()
    print(f"Updated At       : {now()}")
    print()
    print("=" * 50)


if __name__ == "__main__":
    main()
