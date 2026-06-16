#!/usr/bin/env python3
"""
AMFI Mutual Fund NAV + SGB LTP + QSIF NAV Fetcher
===================================================
Part 1 — AMFI NAV:
  Downloads AMFI's daily NAVAll.txt (all mutual fund schemes in India) and
  extracts NAV + date for ISINs present in the portfolio's unified-symbols.json
  holdings (instrumentType == "MUTUAL FUND" or "SOVEREIGN BOND" with an ISIN
  that matches an AMFI-listed scheme — SGBs are not in AMFI; included here in
  case a fund-of-fund SGB wrapper is used).
  Output: data/mf_nav.json

Part 2 — SGB LTP:
  Fetches Last Traded Price (LTP) for Sovereign Gold Bond (SGB) tickers from
  sgbanalyzer.com, for entries in unified-symbols.json where
  instrument_type == "SOVEREIGN BOND".
  Output: data/sgb_ltp.json

Part 3 — QSIF NAV:
  Scrapes latest NAV from qsif.com/NAV/latestnav for entries in
  unified-symbols.json where instrument_type == "SIF". Matches by scheme_name
  keyword (case-insensitive substring). Handles ASP.NET pagination (2 pages).
  Output: data/qsif_nav.json
"""

import json
import logging
import re
import requests
import time
from pathlib import Path
from datetime import datetime, UTC, timedelta

DATA_DIR = Path('data')
SYMBOLS_FILE = DATA_DIR / 'unified-symbols.json'

MF_NAV_OUTPUT_FILE = DATA_DIR / 'mf_nav.json'
SGB_LTP_OUTPUT_FILE = DATA_DIR / 'sgb_ltp.json'
QSIF_NAV_OUTPUT_FILE = DATA_DIR / 'qsif_nav.json'

LOG_FILE = DATA_DIR / 'logs/fetch_amfi_nav.log'

AMFI_URL = 'https://www.amfiindia.com/spages/NAVAll.txt'

SGBANALYZER_URL = 'https://sgbanalyzer.com/sgb/{symbol}'

QSIF_NAV_URL = 'https://www.qsif.com/All-Strategies/funds'

# Fund detail page URLs keyed by ISIN — add new entries as more QSIF funds are held
QSIF_FUND_URLS = {
    'INF966L30027': 'https://www.qsif.com/equity/qsif-logn-short-fund',
}

SCRAPE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

(DATA_DIR / 'logs').mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-10s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='w'), logging.StreamHandler()]
)
logger = logging.getLogger("AMFI-NAV")
sgb_logger = logging.getLogger("SGB-LTP")
qsif_logger = logging.getLogger("QSIF-NAV")


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


# ===========================================================================
# Part 1 — AMFI Mutual Fund NAV
# ===========================================================================

def get_portfolio_isins():
    """Collect ISINs from unified-symbols.json holdings for MF/SGB instruments.

    Uses `instrument_type` (now populated for all entries via the wizard's
    AI-enrichment step), falling back to sector == "Mutual Fund"/"Government
    Securities" for any older entries that predate that field. Does NOT use
    an ISIN "INF" prefix check — ETFs (e.g. JUNIORBEES, INF200KA1FS3) are
    also INF-prefixed but are not mutual funds and have no AMFI NAV.
    """
    us = load_json(SYMBOLS_FILE)
    isins = set()
    for entry in us.get('symbols', []):
        isin = entry.get('isin')
        if not isin:
            continue
        isin = isin.strip().upper()

        itype = (entry.get('instrument_type') or entry.get('instrumentType') or '').upper()
        sector = (entry.get('sector') or '').upper()

        is_mf_like = (
            itype in ('MUTUAL FUND', 'SOVEREIGN BOND')
            or sector in ('MUTUAL FUND', 'GOVERNMENT SECURITIES')
        )

        if is_mf_like:
            # QSIF/SIF schemes are not in AMFI NAVAll.txt — exclude them here;
            # they are handled separately by run_qsif_nav().
            name = (entry.get('name') or '').lower()
            if 'qsif' in name:
                continue
            isins.add(isin)
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
            # anything else is treated as the AMC name. The category line
            # always comes first, immediately followed by the AMC name line —
            # so the AMC line must NOT clear current_category.
            if 'scheme' in line.lower():
                current_category = line
            else:
                current_amc = line
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


def run_amfi_nav():
    wanted_isins = get_portfolio_isins()
    logger.info(f"Portfolio ISINs to match (MUTUAL FUND / SOVEREIGN BOND): {len(wanted_isins)}")

    if not wanted_isins:
        logger.warning("No MUTUAL FUND / SOVEREIGN BOND ISINs found in unified-symbols.json — writing empty output")
        output = {"_metadata": {"generated_at": now(), "count": 0, "source": "AMFI NAVAll.txt"}}
        save_json(MF_NAV_OUTPUT_FILE, output)
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
            logger.info(f"  ✓ {entry.get('scheme_name', isin)}: returns computed")

    output = {"_metadata": {"generated_at": now(), "count": len(matched), "source": "AMFI NAVAll.txt + mfapi.in"}}
    output.update(matched)
    save_json(MF_NAV_OUTPUT_FILE, output)
    logger.info(f"✓ Wrote {MF_NAV_OUTPUT_FILE}")


# ===========================================================================
# Part 2 — SGB LTP (NSE)
# ===========================================================================

def get_portfolio_sgb_symbols():
    """Collect ticker symbols for instrument_type == 'SOVEREIGN BOND'."""
    us = load_json(SYMBOLS_FILE)
    symbols = set()
    for entry in us.get('symbols', []):
        itype = (entry.get('instrument_type') or entry.get('instrumentType') or '').upper()
        if itype == 'SOVEREIGN BOND':
            symbol = (entry.get('symbol') or entry.get('ticker') or '').strip().upper()
            if symbol:
                symbols.add(symbol)
    return symbols


def fetch_sgb_ltp(session, symbol):
    """Scrape current market price for an SGB symbol from sgbanalyzer.com.

    The page embeds the price in plain text as e.g. "₹15,501.85" near
    "Current Price" / "Market price". Extract via regex; tolerant of minor
    markup changes since this is a third-party page, not an API.
    """
    url = SGBANALYZER_URL.format(symbol=symbol.lower())
    resp = session.get(url, headers=SCRAPE_HEADERS, timeout=15)
    resp.raise_for_status()
    html = resp.text

    # Match "₹15,501.85" style price anywhere on the page
    match = re.search(r'₹\s*([\d,]+\.\d{2})', html)
    if not match:
        raise ValueError("price pattern not found on page")

    ltp_str = match.group(1).replace(',', '')
    ltp = float(ltp_str)

    return {
        'ltp': ltp,
        'source': 'sgbanalyzer.com',
        'date': now(),
    }


def run_sgb_ltp():
    symbols = get_portfolio_sgb_symbols()
    sgb_logger.info(f"Portfolio SGB symbols to fetch: {len(symbols)}")

    if not symbols:
        sgb_logger.warning("No SOVEREIGN BOND symbols found in unified-symbols.json — writing empty output")
        output = {"_metadata": {"generated_at": now(), "count": 0, "source": "sgbanalyzer.com"}}
        save_json(SGB_LTP_OUTPUT_FILE, output)
        return

    session = requests.Session()

    result = {}
    for symbol in sorted(symbols):
        try:
            entry = fetch_sgb_ltp(session, symbol)
            if entry.get('ltp') is None:
                sgb_logger.warning(f"  ⚠ {symbol}: no LTP in response")
                continue
            result[symbol] = entry
            sgb_logger.info(f"  ✓ {symbol}: LTP {entry['ltp']}")
        except Exception as e:
            sgb_logger.warning(f"  ⚠ {symbol}: fetch failed: {e}")
        time.sleep(1)  # be polite to sgbanalyzer.com

    missing = symbols - set(result.keys())
    if missing:
        sgb_logger.warning(f"  ⚠ {len(missing)} symbol(s) not fetched: {sorted(missing)}")

    sgb_logger.info(f"  ✓ Fetched {len(result)}/{len(symbols)} SGB symbols")

    output = {"_metadata": {"generated_at": now(), "count": len(result), "source": "sgbanalyzer.com"}}
    output.update(result)
    save_json(SGB_LTP_OUTPUT_FILE, output)
    sgb_logger.info(f"✓ Wrote {SGB_LTP_OUTPUT_FILE}")


# ===========================================================================
# Part 3 — QSIF NAV (qsif.com)
# ===========================================================================

def get_portfolio_qsif_entries():
    """Collect symbol + scheme_name keyword for QSIF/SIF entries.

    Matches on name containing 'qsif' (case-insensitive) since these schemes
    are filed as instrument_type == 'MUTUAL FUND' in unified-symbols.json but
    are SIF schemes not present in AMFI NAVAll.txt.
    """
    us = load_json(SYMBOLS_FILE)
    entries = []
    for entry in us.get('symbols', []):
        name = (entry.get('name') or entry.get('scheme_name') or '').strip()
        if 'qsif' not in name.lower():
            continue
        symbol = (entry.get('isin') or entry.get('symbol') or entry.get('ticker') or '').strip().upper()
        if symbol and name:
            entries.append({'symbol': symbol, 'scheme_name': name})
    return entries


def fetch_and_parse_qsif_homepage(session):
    """Scrape NAV from individual QSIF fund detail pages (server-rendered).

    Fund detail pages contain NAV in the pattern:
      **10.20** ... As of\n DD-Mon-YYYY

    Falls back to /All-Strategies/funds listing page if no detail URL is known.
    Returns list of dicts: {isin, scheme_name, nav, date}
    """
    rows = []
    for isin, url in QSIF_FUND_URLS.items():
        try:
            resp = session.get(url, headers=SCRAPE_HEADERS, timeout=15)
            resp.raise_for_status()
            html = resp.text

            # NAV is in a <strong> tag followed by an img and "As of" date text
            # Raw HTML pattern: <strong>10.20</strong><img...>...\nAs of\n DD-Mon-YYYY
            nav_match = re.search(
                r'<strong>\s*([\d.]+)\s*</strong>.*?As\s+of\s*\n?\s*([\d\w\-]+)',
                html, re.DOTALL | re.IGNORECASE
            )
            if not nav_match:
                # Fallback: look for NAV value near "As of" anywhere on page
                nav_match = re.search(
                    r'([\d]{2,3}\.\d{2})\s*(?:<[^>]+>)*\s*As\s+of\s*\n?\s*([\d\w\-]+)',
                    html, re.DOTALL | re.IGNORECASE
                )
            if not nav_match:
                qsif_logger.warning(f"  ⚠ {isin}: NAV pattern not found on {url}")
                continue

            nav = float(nav_match.group(1).strip())
            date_str = nav_match.group(2).strip()

            # Scheme name from <h2>
            name_match = re.search(r'<h2[^>]*>\s*(qsif[^<]+?)\s*</h2>', html, re.IGNORECASE)
            scheme_name = re.sub(r'\s+', ' ', name_match.group(1)).strip() if name_match else isin

            rows.append({'isin': isin, 'scheme_name': scheme_name, 'nav': nav, 'date': date_str})
            qsif_logger.info(f"  Fetched {scheme_name}: NAV {nav} as of {date_str}")

        except Exception as e:
            qsif_logger.warning(f"  ⚠ {isin}: fetch failed: {e}")
        time.sleep(1)

    return rows


def run_qsif_nav():
    entries = get_portfolio_qsif_entries()
    qsif_logger.info(f"Portfolio SIF entries to match: {len(entries)}")

    if not entries:
        qsif_logger.warning("No SIF entries found in unified-symbols.json — writing empty output")
        output = {"_metadata": {"generated_at": now(), "count": 0, "source": "qsif.com"}}
        save_json(QSIF_NAV_OUTPUT_FILE, output)
        return

    session = requests.Session()
    all_rows = fetch_and_parse_qsif_homepage(session)
    qsif_logger.info(f"  Fetched {len(all_rows)} QSIF fund NAVs")

    # Index rows by ISIN for direct lookup
    rows_by_isin = {r['isin']: r for r in all_rows}

    result = {}
    for entry in entries:
        symbol = entry['symbol']  # ISIN
        row = rows_by_isin.get(symbol)
        if not row:
            qsif_logger.warning(f"  ⚠ {symbol}: no data fetched (add URL to QSIF_FUND_URLS)")
            continue
        result[symbol] = {
            'scheme_name': row['scheme_name'],
            'nav': row['nav'],
            'date': row['date'],
            'source': 'qsif.com',
        }
        qsif_logger.info(f"  ✓ {symbol}: NAV {row['nav']} ({row['date']})")

    missing = {e['symbol'] for e in entries} - set(result.keys())
    if missing:
        qsif_logger.warning(f"  ⚠ {len(missing)} symbol(s) not matched: {sorted(missing)}")

    qsif_logger.info(f"  ✓ Matched {len(result)}/{len(entries)} SIF entries")

    output = {"_metadata": {"generated_at": now(), "count": len(result), "source": "qsif.com"}}
    output.update(result)
    save_json(QSIF_NAV_OUTPUT_FILE, output)
    qsif_logger.info(f"✓ Wrote {QSIF_NAV_OUTPUT_FILE}")


# ===========================================================================
# Main
# ===========================================================================

def main():
    try:
        run_amfi_nav()
    except Exception as e:
        logger.warning(f"  ⚠ AMFI NAV run failed: {e}")

    try:
        run_sgb_ltp()
    except Exception as e:
        sgb_logger.warning(f"  ⚠ SGB LTP run failed: {e}")

    try:
        run_qsif_nav()
    except Exception as e:
        qsif_logger.warning(f"  ⚠ QSIF NAV run failed: {e}")


if __name__ == "__main__":
    main()
