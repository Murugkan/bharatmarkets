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
  Scrapes daily NAV history from qsif.com/nav/historical_nav (a single page
  that lists ALL QSIF schemes' NAV history, paginated, no search/postback
  needed — a plain GET returns the full table). Matches rows by scheme_name
  keyword (case-insensitive substring) for entries in unified-symbols.json
  where instrument_type == "SIF". Change/changePct are computed directly
  from the two most recent rows found on the page itself (not by diffing
  against the previous day's output file), so this no longer depends on
  nav_ltp.json from a prior run.
  Output: data/qsif_nav.json
"""

import json
import logging
import re
import requests
import subprocess
import time
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime, UTC, timedelta

DATA_DIR = Path('data')
SYMBOLS_FILE = DATA_DIR / 'unified-symbols.json'

NAV_LTP_OUTPUT_FILE = DATA_DIR / 'nav_ltp.json'

LOG_FILE = DATA_DIR / 'logs/fetch_nav_ltp.log'

AMFI_URL = 'https://www.amfiindia.com/spages/NAVAll.txt'

QSIF_NAV_URL = 'https://www.qsif.com/nav/historical_nav'

# Scheme name keywords to match against the historical NAV table's
# "Scheme Name" column, keyed by ISIN — add new entries as more QSIF
# funds are held. Matching is case-insensitive substring match.
QSIF_SCHEME_KEYWORDS = {
    'INF966L30027': 'Equity Long-Short Fund',
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


def git_commit_and_push(paths, message):
    """Commit and push the given file paths directly from this script.

    Runs `git add/commit/push` so the workflow YAML no longer needs to own
    committing — this script always commits the file it just wrote, in the
    same process, immediately after writing it. Avoids the checkout/commit
    ordering issue where a separate workflow step could run against a stale
    working directory and make 'previous' data look identical to 'current'.

    Safe to call in CI: if there's nothing to commit (no changes), this is
    a no-op rather than an error. Requires the runner to already have git
    user.name/user.email configured and push credentials available (e.g.
    via actions/checkout with persist-credentials, or GITHUB_TOKEN remote).
    """
    try:
        str_paths = [str(p) for p in paths]
        subprocess.run(["git", "add"] + str_paths, check=True)

        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"] + str_paths
        )
        if diff.returncode == 0:
            logger.info("✓ No changes to commit (data unchanged)")
            return

        subprocess.run(["git", "commit", "-m", message], check=True)
        subprocess.run(["git", "push"], check=True)
        logger.info(f"✓ Committed and pushed: {message}")
    except subprocess.CalledProcessError as e:
        logger.error(f"⚠ Git commit/push failed: {e}")
    except Exception as e:
        logger.error(f"⚠ Unexpected error during git commit/push: {e}")


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

def parse_nav_table(html):
    """Parse a historical_nav page's table into rows.

    Expected columns (per the live site): NAV Date | Scheme Name | NAV(₹)
    Returns list of dicts: {date_str, scheme_name, nav}
    Tries to be resilient to extra whitespace/columns by matching on
    header text rather than assuming a fixed column index.
    """
    soup = BeautifulSoup(html, 'html.parser')
    rows = []

    tables = soup.find_all('table')
    if not tables:
        qsif_logger.warning("  ⚠ No <table> found on historical_nav page")
        return rows

    for table in tables:
        header_cells = table.find('tr')
        if not header_cells:
            continue
        headers = [th.get_text(strip=True).lower() for th in header_cells.find_all(['th', 'td'])]
        if not any('nav date' in h for h in headers) and not any('scheme' in h for h in headers):
            continue  # not the table we want (could be a layout table)

        # Locate column indices by header text
        try:
            date_idx = next(i for i, h in enumerate(headers) if 'date' in h)
            name_idx = next(i for i, h in enumerate(headers) if 'scheme' in h)
            nav_idx = next(i for i, h in enumerate(headers) if 'nav' in h and 'date' not in h)
        except StopIteration:
            qsif_logger.warning(f"  ⚠ Could not identify columns from headers: {headers}")
            continue

        qsif_logger.info(
            f"  Table structure: headers={headers} | "
            f"date_idx={date_idx} name_idx={name_idx} nav_idx={nav_idx}"
        )

        for tr in table.find_all('tr')[1:]:  # skip header row
            cells = tr.find_all(['td', 'th'])
            if len(cells) <= max(date_idx, name_idx, nav_idx):
                continue
            date_str = cells[date_idx].get_text(strip=True)
            scheme_name = cells[name_idx].get_text(strip=True)
            nav_str = cells[nav_idx].get_text(strip=True).replace(',', '')
            try:
                nav = float(nav_str)
            except ValueError:
                continue
            if not date_str or not scheme_name:
                continue
            rows.append({'date_str': date_str, 'scheme_name': scheme_name, 'nav': nav})

    if rows:
        sample = rows[:5]
        qsif_logger.info(f"  Sample parsed rows ({len(rows)} total): " +
                          " | ".join(f"[{r['date_str']} / '{r['scheme_name']}' / {r['nav']}]" for r in sample))
    else:
        qsif_logger.warning("  ⚠ Zero rows parsed from any table on this page")

    return rows


def fetch_qsif_historical_nav(session, max_pages=1):
    """Fetch and parse the historical_nav page across pagination.

    The page returns the full table for ALL QSIF schemes on a plain GET
    (confirmed: no search/postback required).

    Pagination is currently DISABLED (max_pages=1): a live run confirmed
    '?page=2' returns HTTP 500, so that query param guess is wrong for
    this site. Page 1 alone returns 10 rows (confirmed in logs), which is
    enough for a 1D change calc. If more history is ever needed, the real
    pagination mechanism needs to be identified from the page's actual
    pager links/markup before re-enabling max_pages > 1.
    """
    PAGE_PARAM = 'page'  # NOT CONFIRMED WORKING — see docstring above
    all_rows = []

    for page_num in range(1, max_pages + 1):
        url = QSIF_NAV_URL if page_num == 1 else f"{QSIF_NAV_URL}?{PAGE_PARAM}={page_num}"
        try:
            resp = session.get(url, headers=SCRAPE_HEADERS, timeout=15)
            resp.raise_for_status()
            page_rows = parse_nav_table(resp.text)
            if not page_rows:
                qsif_logger.info(f"  Page {page_num}: no rows parsed, stopping pagination")
                break
            all_rows.extend(page_rows)
            qsif_logger.info(f"  Page {page_num}: {len(page_rows)} rows")
        except Exception as e:
            qsif_logger.warning(f"  ⚠ Page {page_num} fetch failed: {e}")
            break
        time.sleep(1)

    qsif_logger.info(f"  ✓ Total rows fetched across pagination: {len(all_rows)}")
    return all_rows


def parse_qsif_date(date_str):
    """Parse 'DD-Mon-YYYY' (e.g. '19-Jun-2026') into a sortable datetime."""
    try:
        return datetime.strptime(date_str.strip(), '%d-%b-%Y')
    except ValueError:
        return None


def run_qsif_nav():
    """Fetch QSIF NAV history and compute LTP + 1D change per held ISIN.

    Unlike before, change/changePct are computed from the two most recent
    dated rows found directly on the historical_nav page — not by diffing
    against nav_ltp.json from a previous run. This removes the dependency
    on prior output being correctly committed/checked-out, which was the
    suspected cause of QSIF's change always showing 0.0.
    """
    if not QSIF_SCHEME_KEYWORDS:
        qsif_logger.warning("No QSIF_SCHEME_KEYWORDS configured")
        return {}

    session = requests.Session()
    all_rows = fetch_qsif_historical_nav(session)
    if not all_rows:
        qsif_logger.warning("  ⚠ No rows parsed from historical_nav page — check page structure")
        return {}

    distinct_names = sorted(set(r['scheme_name'] for r in all_rows))
    qsif_logger.info(f"  Distinct scheme names found on page ({len(distinct_names)}): {distinct_names}")

    result = {}
    for isin, keyword in QSIF_SCHEME_KEYWORDS.items():
        matched = [r for r in all_rows if keyword.lower() in r['scheme_name'].lower()]
        if not matched:
            qsif_logger.warning(f"  ⚠ {isin}: no rows matched keyword '{keyword}' against {distinct_names}")
            continue

        # Sort by parsed date, most recent first; drop unparseable dates
        dated = []
        for r in matched:
            d = parse_qsif_date(r['date_str'])
            if d:
                dated.append((d, r))
        dated.sort(key=lambda x: x[0], reverse=True)

        if not dated:
            qsif_logger.warning(f"  ⚠ {isin}: matched rows but none had parseable dates")
            continue

        curr_date, curr_row = dated[0]
        change = None
        change_pct = None
        if len(dated) >= 2:
            prev_date, prev_row = dated[1]
            curr_nav = curr_row['nav']
            prev_nav = prev_row['nav']
            if prev_nav:
                change = round(curr_nav - prev_nav, 4)
                change_pct = round((curr_nav - prev_nav) / prev_nav * 100, 4)
            qsif_logger.info(
                f"  {isin}: {curr_date.date()} NAV {curr_nav} vs {prev_date.date()} NAV {prev_nav} "
                f"-> change {change}"
            )
        else:
            qsif_logger.warning(f"  ⚠ {isin}: only one dated row found, can't compute change")

        result[isin] = {
            'ltp': curr_row['nav'],
            'date': curr_row['date_str'],
            'scheme_name': curr_row['scheme_name'],
            'source': 'qsif.com',
            'change': change,
            'changePct': change_pct,
        }
        qsif_logger.info(f"  ✓ {isin}: LTP {curr_row['nav']} ({curr_row['date_str']})")

    missing = set(QSIF_SCHEME_KEYWORDS.keys()) - set(result.keys())
    if missing:
        qsif_logger.warning(f"  ⚠ {len(missing)} ISIN(s) not matched: {sorted(missing)}")

    qsif_logger.info(f"  ✓ Matched {len(result)}/{len(QSIF_SCHEME_KEYWORDS)} QSIF entries")
    return result


# ===========================================================================
# Main
# ===========================================================================

def main():
    merged = {}

    try:
        amfi = run_amfi_nav()
        merged.update(amfi)
    except Exception as e:
        logger.warning(f"  ⚠ AMFI NAV run failed: {e}")

    try:
        qsif = run_qsif_nav()
        # change/changePct are already computed inside run_qsif_nav() from
        # the historical NAV table itself — no need to diff against a
        # previously-saved nav_ltp.json here.
        merged.update(qsif)
    except Exception as e:
        qsif_logger.warning(f"  ⚠ QSIF NAV run failed: {e}")

    output = {"_metadata": {"generated_at": now(), "count": len(merged), "source": "AMFI + qsif.com"}}
    output.update(merged)
    save_json(NAV_LTP_OUTPUT_FILE, output)
    logger.info(f"✓ Wrote {NAV_LTP_OUTPUT_FILE} ({len(merged)} entries)")

    git_commit_and_push(
        [NAV_LTP_OUTPUT_FILE],
        f"Update nav_ltp.json ({len(merged)} entries) [skip ci]"
    )


if __name__ == "__main__":
    main()
