import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

RAW_FUNDAMENTALS_FILE = (
    BASE_DIR / "raw_fundamentals.json"
)

FUNDAMENTALS_FILE = (
    BASE_DIR / "fundamentals.json"
)


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


def latest_value(
    history,
    field
):

    for row in reversed(history):

        values = row.get(
            "values",
            {}
        )

        value = values.get(field)

        if value not in [
            None,
            ""
        ]:

            return value

    return None


def build_stock(raw_stock):

    output = {}

    metadata = raw_stock.get(
        "metadata",
        {}
    )

    output["name"] = metadata.get("name")
    output["sector"] = metadata.get("sector")
    output["industry"] = metadata.get("industry")

    output["ltp"] = latest_value(
        raw_stock.get(
            "market_data_history",
            []
        ),
        "ltp"
    )

    output["market_cap"] = latest_value(
        raw_stock.get(
            "market_data_history",
            []
        ),
        "market_cap"
    )

    output["roe"] = latest_value(
        raw_stock.get(
            "ratio_history",
            []
        ),
        "roe"
    )

    output["roce"] = latest_value(
        raw_stock.get(
            "ratio_history",
            []
        ),
        "roce"
    )

    output["quarterly"] = []

    for row in raw_stock.get(
        "quarterly_history",
        []
    ):

        output["quarterly"].append(
            row.get(
                "values",
                {}
            )
        )

    return output


def main():

    raw_store = load_json(
        RAW_FUNDAMENTALS_FILE
    )

    fundamentals = {}

    for ticker, raw_stock in raw_store.items():

        fundamentals[ticker] = build_stock(
            raw_stock
        )

    save_json(
        FUNDAMENTALS_FILE,
        fundamentals
    )


if __name__ == "__main__":

    main()
