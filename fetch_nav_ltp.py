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

Part 2 — QSIF NAV:
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

NAV_LTP_OUTPUT_FILE = DATA_DIR / 'nav_ltp.json'

LOG_FILE = DATA_DIR / 'logs/fetch_nav_ltp.log'

AMFI_URL = 'https://www.amfiindia.com/spages/NAVAll.txt'

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
        logger.warning("No MUTUAL FUND / SOVEREIGN BOND ISINs found in unified-symbols.json")
        return {}

    text = fetch_navall()
    matched = parse_navall(text, wanted_isins)

    missing = wanted_isins - set(matched.keys())
    if missing:
        logger.warning(f"  ⚠ {len(missing)} ISIN(s) not found in AMFI NAVAll.txt: {sorted(missing)}")

    logger.info(f"  ✓ Matched {len(matched)}/{len(wanted_isins)} ISINs")

    for isin, entry in matched.items():
        scheme_code = entry.get('scheme_code')
        if not scheme_code:
            continue
        history = fetch_historical_nav(scheme_code)
        entry['_history'] = history
        returns = compute_returns(history)
        if returns:
            entry['returns'] = returns
            logger.info(f"  ✓ {entry.get('scheme_name', isin)}: returns computed")

    # Normalise to ltp key for consistency
    result = {}
    for isin, entry in matched.items():
        change = None
        change_pct = None
        hist = entry.get('_history', [])
        if len(hist) >= 2:
            try:
                curr_nav = float(hist[0]['nav'])
                prev_nav = float(hist[1]['nav'])
                if prev_nav > 0:
                    change = round(curr_nav - prev_nav, 4)
                    change_pct = round((curr_nav - prev_nav) / prev_nav * 100, 4)
            except (ValueError, KeyError, TypeError):
                pass

        result[isin] = {
            'ltp': entry.get('nav'),
            'date': entry.get('date'),
            'scheme_name': entry.get('scheme_name'),
            'source': 'AMFI',
            'change': change,
            'changePct': change_pct,
        }
        if 'returns' in entry:
            result[isin]['returns'] = entry['returns']

    return result


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

            # HTML structure around NAV:
            # ...>10.33</..><span class="paddl"><img green_icon /></span></div>
            # <span>As of\n    15-Jun-2026</span>
            # Strategy: find "As of" block, grab the date, then search backwards for the NAV number
            as_of_match = re.search(
                r'As\s+of\s*[\s\S]{0,20}?([\d]{1,2}-[A-Za-z]{3}-\d{4})',
                html
            )
            # NAV: a decimal number appearing just before the green_icon img tag
            # Actual HTML: <span><b>\n  10.33</b></span><span class="paddl"><img green_icon/>
            nav_val_match = re.search(
                r'<b>\s*([\d]{1,3}\.[\d]+)\s*</b>\s*</span>\s*<span[^>]*paddl',
                html
            )
            if not as_of_match or not nav_val_match:
                # Log 300 chars around green_icon for diagnosis
                pos = html.find('green_icon')
                qsif_logger.warning(f"  ⚠ {isin}: parse failed | context={html[max(0,pos-200):pos+100].replace(chr(10),' ')}")
                continue

            nav = float(nav_val_match.group(1))
            date_str = as_of_match.group(1).strip()

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
        qsif_logger.warning("No SIF entries found in unified-symbols.json")
        return {}

    session = requests.Session()
    all_rows = fetch_and_parse_qsif_homepage(session)
    qsif_logger.info(f"  Fetched {len(all_rows)} QSIF fund NAVs")

    rows_by_isin = {r['isin']: r for r in all_rows}

    result = {}
    for entry in entries:
        symbol = entry['symbol']
        row = rows_by_isin.get(symbol)
        if not row:
            qsif_logger.warning(f"  ⚠ {symbol}: no data fetched (add URL to QSIF_FUND_URLS)")
            continue
        result[symbol] = {
            'ltp': row['nav'],
            'date': row['date'],
            'scheme_name': row['scheme_name'],
            'source': 'qsif.com',
        }
        qsif_logger.info(f"  ✓ {symbol}: LTP {row['nav']} ({row['date']})")

    missing = {e['symbol'] for e in entries} - set(result.keys())
    if missing:
        qsif_logger.warning(f"  ⚠ {len(missing)} symbol(s) not matched: {sorted(missing)}")

    qsif_logger.info(f"  ✓ Matched {len(result)}/{len(entries)} SIF entries")
    return result


# ===========================================================================
# Main
# ===========================================================================

def main():
    merged = {}

    # Load existing nav_ltp.json to get previous QSIF prices for 1D change computation
    prev_nav_ltp = {}
    if NAV_LTP_OUTPUT_FILE.exists():
        try:
            with open(NAV_LTP_OUTPUT_FILE, 'r', encoding='utf-8') as f:
                prev_nav_ltp = json.load(f)
        except Exception as e:
            logger.warning(f"  ⚠ Could not load previous nav_ltp.json: {e}")

    try:
        amfi = run_amfi_nav()
        merged.update(amfi)
    except Exception as e:
        logger.warning(f"  ⚠ AMFI NAV run failed: {e}")



    try:
        qsif = run_qsif_nav()
        for symbol, entry in qsif.items():
            prev = prev_nav_ltp.get(symbol, {})
            prev_ltp = prev.get('ltp')
            curr_ltp = entry.get('ltp')
            if prev_ltp and curr_ltp:
                entry['change'] = round(curr_ltp - prev_ltp, 4)
                entry['changePct'] = round((curr_ltp - prev_ltp) / prev_ltp * 100, 4)
            else:
                entry['change'] = None
                entry['changePct'] = None
        merged.update(qsif)
    except Exception as e:
        qsif_logger.warning(f"  ⚠ QSIF NAV run failed: {e}")

    output = {"_metadata": {"generated_at": now(), "count": len(merged), "source": "AMFI + qsif.com"}}
    output.update(merged)
    save_json(NAV_LTP_OUTPUT_FILE, output)
    logger.info(f"✓ Wrote {NAV_LTP_OUTPUT_FILE} ({len(merged)} entries)")


if __name__ == "__main__":
    main()
