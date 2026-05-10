
import json

RAW_FUNDAMENTALS_FILE = "raw_fundamentals.json"
FUNDAMENTALS_FILE = "fundamentals.json"


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


def latest_value(history, field):

    for row in reversed(history):

        values = row.get(
            "values",
            {}
        )

        if field in values:

            value = values[field]

            if value not in [
                None,
                ""
            ]:

                return value

    return None


def build_stock(raw_stock):

    result = {}

    result["name"] = raw_stock["metadata"].get("name")
    result["sector"] = raw_stock["metadata"].get("sector")
    result["industry"] = raw_stock["metadata"].get("industry")

    result["ltp"] = latest_value(
        raw_stock.get(
            "market_data_history",
            []
        ),
        "ltp"
    )

    result["market_cap"] = latest_value(
        raw_stock.get(
            "market_data_history",
            []
        ),
        "market_cap"
    )

    result["roe"] = latest_value(
        raw_stock.get(
            "ratio_history",
            []
        ),
        "roe"
    )

    result["roce"] = latest_value(
        raw_stock.get(
            "ratio_history",
            []
        ),
        "roce"
    )

    result["quarterly"] = []

    for row in raw_stock.get(
        "quarterly_history",
        []
    ):

        result["quarterly"].append(
            row["values"]
        )

    return result


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
