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
from bs4 import BeautifulSoup
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

QSIF_NAV_URL = 'https://www.qsif.com/NAV/latestnav'

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


def fetch_qsif_nav_page(session, page_num=1, viewstate=None, eventvalidation=None):
    """Fetch one page of qsif.com/NAV/latestnav.

    Page 1: plain GET. Subsequent pages: POST with ASP.NET hidden fields
    (__VIEWSTATE, __EVENTVALIDATION) extracted from the previous response,
    plus the __doPostBack target for the next-page link.
    """
    if page_num == 1:
        resp = session.get(QSIF_NAV_URL, headers=SCRAPE_HEADERS, timeout=15)
    else:
        # ASP.NET pagination — POST with __doPostBack event for page N
        event_target = f"ctl00$ContentPlaceHolder1$nav_sch$ctl01$ctl{page_num - 1:02d}"
        data = {
            '__EVENTTARGET': event_target,
            '__EVENTARGUMENT': '',
            '__VIEWSTATE': viewstate or '',
            '__EVENTVALIDATION': eventvalidation or '',
        }
        resp = session.post(QSIF_NAV_URL, headers=SCRAPE_HEADERS, data=data, timeout=15)

    resp.raise_for_status()
    return resp.text


def parse_qsif_nav_table(html):
    """Parse the NAV table from qsif.com HTML using BeautifulSoup.

    Returns list of row dicts and ASP.NET hidden field values for pagination.
    """
    soup = BeautifulSoup(html, 'html.parser')
    rows = []

    # Extract ASP.NET hidden fields for pagination
    vs = soup.find('input', {'id': '__VIEWSTATE'})
    ev = soup.find('input', {'id': '__EVENTVALIDATION'})
    viewstate = vs['value'] if vs else ''
    eventvalidation = ev['value'] if ev else ''

    # Find the NAV table — locate by header row content
    for table in soup.find_all('table'):
        headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
        if not any('scheme' in h or 'nav' in h for h in headers):
            continue
        for tr in table.find_all('tr')[1:]:  # skip header row
            tds = [td.get_text(strip=True) for td in tr.find_all('td')]
            if len(tds) < 4:
                continue
            # Columns: Date | Scheme Name | Option | NAV | %Chg
            try:
                nav = float(tds[3])
            except (ValueError, IndexError):
                continue
            rows.append({
                'date': tds[0],
                'scheme_name': tds[1],
                'option': tds[2],
                'nav': nav,
                'pchange': tds[4] if len(tds) > 4 else '',
            })
        break  # only parse first matching table

    # Check if a "Next" page link exists
    has_next = bool(soup.find(string=re.compile(r'Next', re.IGNORECASE),
                               attrs={'href': re.compile(r'__doPostBack', re.IGNORECASE)})
                    or 'Next' in html)

    return rows, viewstate, eventvalidation, has_next


def run_qsif_nav():
    entries = get_portfolio_qsif_entries()
    qsif_logger.info(f"Portfolio SIF entries to match: {len(entries)}")

    if not entries:
        qsif_logger.warning("No SIF entries found in unified-symbols.json — writing empty output")
        output = {"_metadata": {"generated_at": now(), "count": 0, "source": "qsif.com"}}
        save_json(QSIF_NAV_OUTPUT_FILE, output)
        return

    session = requests.Session()
    all_rows = []

    # Fetch page 1
    html = fetch_qsif_nav_page(session, page_num=1)
    rows, viewstate, eventvalidation, has_next = parse_qsif_nav_table(html)
    all_rows.extend(rows)
    qsif_logger.info(f"  Page 1: {len(rows)} rows")

    # Fetch page 2 if present
    if has_next:
        time.sleep(1)
        html2 = fetch_qsif_nav_page(session, page_num=2, viewstate=viewstate, eventvalidation=eventvalidation)
        rows2, _, _, _ = parse_qsif_nav_table(html2)
        all_rows.extend(rows2)
        qsif_logger.info(f"  Page 2: {len(rows2)} rows")

    qsif_logger.info(f"  Total rows fetched: {len(all_rows)}")

    # Match portfolio entries to scraped rows by scheme_name keyword (case-insensitive)
    result = {}
    for entry in entries:
        symbol = entry['symbol']
        # Build a shorter keyword from the name for fuzzy matching against qsif.com table rows.
        # e.g. "QSIF EQUITY LONG-SHORT FUND-REGULAR PLAN-GROWTH" → "equity long-short"
        name_lower = entry['scheme_name'].lower().replace('qsif', '').replace('fund', '').strip(' -')
        # Take first meaningful segment before plan/option qualifiers
        keyword = re.split(r'[-–]\s*(regular|direct|growth|idcw|plan|option)', name_lower)[0].strip(' -')
        if not keyword:
            keyword = name_lower

        matched_rows = [r for r in all_rows if keyword in r['scheme_name'].lower()]

        if not matched_rows:
            qsif_logger.warning(f"  ⚠ {symbol}: no match for scheme_name '{entry['scheme_name']}'")
            continue

        # Prefer matching plan type (regular/direct) from entry name
        prefer_direct = 'direct' in entry['scheme_name'].lower()
        if prefer_direct:
            best = next(
                (r for r in matched_rows if 'direct' in r['scheme_name'].lower() and 'growth' in r['option'].lower()),
                matched_rows[0]
            )
        else:
            best = next(
                (r for r in matched_rows if 'regular' in r['scheme_name'].lower() and 'growth' in r['option'].lower()),
                matched_rows[0]
            )
        result[symbol] = {
            'scheme_name': best['scheme_name'],
            'nav': best['nav'],
            'pchange': best['pchange'],
            'date': best['date'],
            'source': 'qsif.com',
        }
        qsif_logger.info(f"  ✓ {symbol}: NAV {best['nav']} ({best['date']})")

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
