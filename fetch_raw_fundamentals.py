import json
import time
from copy import deepcopy
from datetime import datetime, UTC
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

RAW_DIR = BASE_DIR / "raw"
LOG_DIR = BASE_DIR / "logs"

# =========================================================
# KEEP EXISTING BASE IMPLEMENTATION IMPORTS
# =========================================================
#
# Preserve the original provider import structure
# from fetch_raw_fundamentalsdump.py
#
# Example:
#
# from provider_native import ...
#
# DO NOT blindly rewrite provider interfaces.
#
# =========================================================


# =========================================================
# AUTO CREATE REQUIRED DIRECTORIES
# =========================================================

REQUIRED_DIRS = [
    RAW_DIR / "yahoo_finance",
    RAW_DIR / "screener",
    LOG_DIR
]

for directory in REQUIRED_DIRS:

    directory.mkdir(
        parents=True,
        exist_ok=True
    )


# =========================================================
# PROVIDER CONFIG
# =========================================================

PROVIDERS = {
    "yahoo_finance": {
        "raw_dir": RAW_DIR / "yahoo_finance",
        "runtime_history": LOG_DIR / "yahoo_runtime_history.json",
        "runtime_delta": LOG_DIR / "yahoo_runtime_delta.json"
    },
    "screener": {
        "raw_dir": RAW_DIR / "screener",
        "runtime_history": LOG_DIR / "screener_runtime_history.json",
        "runtime_delta": LOG_DIR / "screener_runtime_delta.json"
    }
}


# =========================================================
# HELPERS
# =========================================================

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


# =========================================================
# PROVIDER RUNTIME HANDLER
# =========================================================

def process_provider(
    provider_name,
    latest_history,
    previous_history,
    delta_store,
    runtime,
    runtime_delta_file,
    history_file,
    delta_file
):

    for ticker, latest in latest_history.items():

        previous = previous_history.get(ticker)

        if has_changed(previous, latest):

            delta_store[ticker] = latest

        runtime["success"] += 1

        # incremental flush
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


# =========================================================
# MAIN
# =========================================================

def main():

    started = time.time()

    print("=" * 50)
    print("RAW FUNDAMENTALS START")
    print("=" * 50)

    for provider_name, provider_config in PROVIDERS.items():

        raw_dir = provider_config["raw_dir"]

        history_file = raw_dir / "history.json"
        delta_file = raw_dir / "delta.json"

        runtime_history_file = (
            provider_config["runtime_history"]
        )

        runtime_delta_file = (
            provider_config["runtime_delta"]
        )

        previous_history = load_json(
            history_file,
            {}
        )

        # overwrite model
        latest_history = {}

        # current run only
        delta_store = {}

        runtime = build_runtime()

        # =====================================================
        # PLACEHOLDER:
        #
        # CALL EXISTING dump.py PROVIDER FLOW HERE
        #
        # This preserves:
        # - symbol resolution
        # - overrides
        # - observation model
        # - skip handling
        # - provider resilience
        #
        # =====================================================

        process_provider(
            provider_name,
            latest_history,
            previous_history,
            delta_store,
            runtime,
            runtime_delta_file,
            history_file,
            delta_file
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

    print()
    print("=" * 50)
    print("RAW FUNDAMENTALS SUMMARY")
    print("=" * 50)
    print()

    print(
        f"Runtime Seconds  : "
        f"{round(time.time() - started, 2)}"
    )

    print()
    print(f"Updated At       : {now()}")
    print()
    print("=" * 50)


if __name__ == "__main__":
    main()
