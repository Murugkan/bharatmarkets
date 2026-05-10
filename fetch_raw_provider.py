import requests
import yfinance as yf

from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def fetch_yahoo_payload(ticker, yahoo_symbol):

    payload = {}

    stock = yf.Ticker(
        yahoo_symbol
    )

    try:

        payload["info"] = stock.info

    except Exception as e:

        payload["info_error"] = str(e)

    try:

        hist = stock.history(
            period="1y",
            interval="1d"
        )

        payload["history_1y_1d"] = (
            hist
            .reset_index()
            .astype(str)
            .to_dict("records")
        )

    except Exception as e:

        payload["history_error"] = str(e)

    return payload


def extract_table(table):

    rows = []

    for tr in table.select("tr"):

        cols = tr.select("th,td")

        row = []

        for col in cols:

            row.append(
                col.get_text(" ", strip=True)
            )

        if row:
            rows.append(row)

    return rows


def fetch_screener_payload(ticker, screener_symbol):

    payload = {}

    url = (
        f"https://www.screener.in/company/"
        f"{screener_symbol}/"
    )

    payload["url"] = url

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    payload["tables"] = []

    for section in soup.select("section"):

        table = section.select_one("table")

        if not table:
            continue

        heading = section.select_one("h2")

        payload["tables"].append({

            "section": (
                heading.get_text(
                    " ",
                    strip=True
                )
                if heading else None
            ),

            "rows": extract_table(
                table
            )
        })

    return payload
