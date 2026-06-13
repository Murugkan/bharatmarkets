#!/usr/bin/env python3
"""
AMFI Mutual Fund NAV Fetcher
============================
Downloads AMFI's daily NAVAll.txt (all mutual fund schemes in India) and
extracts NAV + date for ISINs present in the portfolio's unified-symbols.json
holdings (instrumentType == "MUTUAL FUND" or "SOVEREIGN BOND" with an ISIN
that matches an AMFI-listed scheme — SGBs are not in AMFI; included here in
case a fund-of-fund SGB wrapper is used).

Output: data/mf_nav.json
{
  "_metadata": {"generated_at": ..., "count": N, "source": "AMFI NAVAll.txt"},
  "<ISIN>": {"scheme_name": "...", "nav": 123.4567, "date": "DD-MMM-YYYY"}
}
"""

import json
import logging
import requests
from pathlib import Path
from datetime import datetime, UTC, timedelta

DATA_DIR = Path('data')
SYMBOLS_FILE = DATA_DIR / 'unified-symbols.json'
OUTPUT_FILE = DATA_DIR / 'mf_nav.json'
LOG_FILE = DATA_DIR / 'logs/fetch_amfi_nav.log'

AMFI_URL = 'https://www.amfiindia.com/spages/NAVAll.txt'

(DATA_DIR / 'logs').mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-10s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
logger = logging.getLogger("AMFI-NAV")


def now():
    return datetime.now(UTC).isoformat()


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Cannot load {path.name}: {e}")
        return {}


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def get_portfolio_isins():
    """Collect ISINs from unified-symbols.json holdings for MF/SGB instruments."""
    us = load_json(SYMBOLS_FILE)
    isins = set()
    for entry in us.get('symbols', []):
        itype = (entry.get('instrument_type') or entry.get('instrumentType') or '').upper()
        isin = entry.get('isin')
        if isin and itype in ('MUTUAL FUND', 'SOVEREIGN BOND'):
            isins.add(isin.strip().upper())
    return isins


def fetch_navall():
    logger.info(f"Fetching {AMFI_URL} ...")
    resp = requests.get(AMFI_URL, timeout=60)
    resp.raise_for_status()
    return resp.text


def parse_navall(text, wanted_isins):
    """
    NAVAll.txt format (semicolon-delimited), header row + scheme rows:
    Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;
    Scheme Name;Net Asset Value;Date

    Some schemes have two ISIN columns (growth/reinvestment) — check both.

    The file also contains section header lines with no ';' that mark the
    current AMC (e.g. "Aditya Birla Sun Life Mutual Fund") and scheme
    category (e.g. "Open Ended Schemes (Equity Scheme - Large Cap Fund)").
    These are tracked and attached to each matched scheme.
    """
    result = {}
    current_amc = None
    current_category = None

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        if ';' not in line:
            # Section header line: either an AMC name or a scheme category.
            # Category headers contain "Schemes" (e.g. "Open Ended Schemes...");
            # anything else is treated as the AMC name.
            if 'scheme' in line.lower():
                current_category = line
            else:
                current_amc = line
                current_category = None
            continue

        parts = line.split(';')
        if len(parts) < 6:
            continue

        scheme_code, isin_growth, isin_div, scheme_name, nav_str, date_str = (
            parts[0].strip(), parts[1].strip(), parts[2].strip(),
            parts[3].strip(), parts[4].strip(), parts[5].strip()
        )

        if scheme_code.lower() == 'scheme code':
            continue  # header row

        try:
            nav = float(nav_str)
        except ValueError:
            continue  # NAV may be "N.A." for some entries

        for isin in (isin_growth, isin_div):
            isin = isin.strip().upper()
            if isin and isin in wanted_isins:
                result[isin] = {
                    'scheme_code': scheme_code,
                    'scheme_name': scheme_name,
                    'nav': nav,
                    'date': date_str,
                    'amc_name': current_amc,
                    'category': current_category,
                }

    return result


def compute_returns(nav_history):
    """
    nav_history: list of {"date": "DD-MM-YYYY", "nav": "123.45"} from mfapi.in,
    newest first. Computes simple point-to-point returns (%) for common
    horizons by finding the closest available NAV on/before the target date.
    """
    if not nav_history:
        return {}

    parsed = []
    for entry in nav_history:
        try:
            d = datetime.strptime(entry['date'], '%d-%m-%Y')
            v = float(entry['nav'])
            parsed.append((d, v))
        except (ValueError, KeyError, TypeError):
            continue
    if not parsed:
        return {}

    parsed.sort(key=lambda x: x[0], reverse=True)  # newest first
    latest_date, latest_nav = parsed[0]

    def nav_on_or_before(target_date):
        for d, v in parsed:
            if d <= target_date:
                return v
        return None

    horizons = {'1m': 30, '3m': 91, '6m': 182, '1y': 365, '3y': 365 * 3}
    returns = {}
    for label, days in horizons.items():
        target = latest_date - timedelta(days=days)
        past_nav = nav_on_or_before(target)
        if past_nav and past_nav > 0:
            pct = (latest_nav - past_nav) / past_nav * 100
            if days >= 365:
                years = days / 365
                cagr = ((latest_nav / past_nav) ** (1 / years) - 1) * 100
                returns[label] = round(cagr, 2)
            else:
                returns[label] = round(pct, 2)

    return returns


def fetch_historical_nav(scheme_code):
    """Fetch full NAV history for a scheme from mfapi.in (free wrapper around AMFI data)."""
    url = f'https://api.mfapi.in/mf/{scheme_code}'
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get('data', [])
    except Exception as e:
        logger.warning(f"  ⚠ mfapi.in fetch failed for scheme {scheme_code}: {e}")
        return []


def main():
    wanted_isins = get_portfolio_isins()
    logger.info(f"Portfolio ISINs to match (MUTUAL FUND / SOVEREIGN BOND): {len(wanted_isins)}")

    if not wanted_isins:
        logger.warning("No MUTUAL FUND / SOVEREIGN BOND ISINs found in unified-symbols.json — writing empty output")
        output = {"_metadata": {"generated_at": now(), "count": 0, "source": "AMFI NAVAll.txt"}}
        save_json(OUTPUT_FILE, output)
        return

    text = fetch_navall()
    matched = parse_navall(text, wanted_isins)

    missing = wanted_isins - set(matched.keys())
    if missing:
        logger.warning(f"  ⚠ {len(missing)} ISIN(s) not found in AMFI NAVAll.txt: {sorted(missing)}")

    logger.info(f"  ✓ Matched {len(matched)}/{len(wanted_isins)} ISINs")

    # Fetch historical NAV + compute returns for each matched scheme (mfapi.in)
    for isin, entry in matched.items():
        scheme_code = entry.get('scheme_code')
        if not scheme_code:
            continue
        history = fetch_historical_nav(scheme_code)
        returns = compute_returns(history)
        if returns:
            entry['returns'] = returns
            logger.info(f"  ✓ {entry.get('scheme_name', isin)}: returns {returns}")

    output = {"_metadata": {"generated_at": now(), "count": len(matched), "source": "AMFI NAVAll.txt + mfapi.in"}}
    output.update(matched)
    save_json(OUTPUT_FILE, output)
    logger.info(f"✓ Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
