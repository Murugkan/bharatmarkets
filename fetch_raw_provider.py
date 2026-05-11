import requests
import yfinance as yf

from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def fetch_yahoo_payload(
    ticker,
    yahoo_symbol
):

    stock = yf.Ticker(
        yahoo_symbol
    )

    hist = stock.history(
        period="1y",
        interval="1d"
    )

    return {
        "provider": "yahoo_finance",
        "provider_symbol": yahoo_symbol,
        "raw": {
            "info": stock.info,
            "history_1y_1d": (
                hist.reset_index()
                .astype(str)
                .to_dict("records")
            )
        }
    }


def extract_table(table):

    rows = []

    for tr in table.select("tr"):

        cols = tr.select("th,td")

        row = [
            col.get_text(" ", strip=True)
            for col in cols
        ]

        if row:
            rows.append(row)

    return rows


def fetch_screener_payload(
    ticker,
    screener_symbol
):

    url = (
        f"https://www.screener.in/company/"
        f"{screener_symbol}/"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    tables = []

    for section in soup.select("section"):

        table = section.select_one("table")

        if not table:
            continue

        heading = section.select_one("h2")

        tables.append({
            "section": (
                heading.get_text(
                    " ",
                    strip=True
                )
                if heading else None
            ),
            "rows": extract_table(table)
        })

    return {
        "provider": "screener",
        "provider_symbol": screener_symbol,
        "raw": {
            "url": url,
            "tables": tables
        }
    }
