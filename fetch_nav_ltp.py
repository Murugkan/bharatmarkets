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

Part 2 — QSIF NAV — three modes (run via CLI arg):

  `python fetch_nav_ltp.py` or `python fetch_nav_ltp.py eod` (default):
    FAST daily path. Uses the site's search box (txtschname + BtnGo
    postback, confirmed from page source) to fetch just the latest page
    (10 rows) per held scheme — always enough for latest NAV + 1D change.
    Output: data/nav_ltp.json (AMFI + QSIF EOD combined, original schema).

  `python fetch_nav_ltp.py history-seed`:
    ONE-OFF MANUAL run. Paginates each scheme's full result until
    pagination genuinely ends (can be a minute+ per scheme — confirmed
    ~17 pages/~170 rows for one scheme in testing). OVERWRITES
    data/qsif_history.json. Run this once to seed the file.

  `python fetch_nav_ltp.py history-delta`:
    SCHEDULED run. Reads the existing qsif_history.json, finds the latest
    saved date per scheme, and fetches ONLY the gap since then (using the
    site's FromIds/ToIds date-range filters, confirmed from page source)
    — then appends to the existing history rather than re-fetching
    everything. One file keeps accumulating over time. Falls back to a
    full fetch for any scheme with no prior saved data (e.g. newly added
    to QSIF_SCHEME_KEYWORDS).
"""

import json
import logging
import random
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
QSIF_HISTORY_OUTPUT_FILE = DATA_DIR / 'qsif_history.json'

LOG_FILE = DATA_DIR / 'logs/fetch_nav_ltp.log'

AMFI_URL = 'https://www.amfiindia.com/spages/NAVAll.txt'

QSIF_NAV_URL = 'https://www.qsif.com/nav/historical_nav'

# Scheme name keywords to match against the historical NAV table's
# "Scheme Name" column, keyed by ISIN — add new entries as more QSIF
# funds are held. Matching is case-insensitive substring match.
# IMPORTANT: must be specific enough to match only ONE share class —
# 'qsif Equity Long-Short Fund' has 4 variants on this page (Regular/
# Direct x Growth/IDCW); a keyword too generic will mix NAV rows from
# different plans into one ISIN's history.
QSIF_SCHEME_KEYWORDS = {
    'INF966L30027': 'Equity Long-Short Fund - Regular - Growth',
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
    if not path.exists():
        logger.info(f"{path.name} does not exist yet (this may be expected, e.g. before a seed run)")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Cannot load {path.name}: {e}")
        return {}


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def git_commit_and_push(paths, message, max_attempts=5):
    """Commit and push the given file paths directly from this script.

    Runs `git add/commit/push` so the workflow YAML no longer needs to own
    committing — this script always commits the file it just wrote, in the
    same process, immediately after writing it. Avoids the checkout/commit
    ordering issue where a separate workflow step could run against a stale
    working directory and make 'previous' data look identical to 'current'.

    Retries on push rejection (e.g. another concurrent job in the same
    workflow run pushed first) via fetch + rebase, matching the pattern
    already used by every other commit step in e2e-parallel.yml. Without
    this, a rejected push would silently drop this run's data entirely —
    confirmed in practice when a same-run QSIF history fetch (a slow,
    ~17-page job) was lost to exactly this race.

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

        for attempt in range(1, max_attempts + 1):
            push = subprocess.run(["git", "push"])
            if push.returncode == 0:
                logger.info(f"✓ Committed and pushed: {message} (attempt {attempt})")
                return
            if attempt >= max_attempts:
                logger.error(f"⚠ Push failed after {max_attempts} attempts: {message}")
                return
            logger.warning(f"  Push rejected (attempt {attempt}/{max_attempts}) — fetching and rebasing, then retrying...")
            time.sleep(random.uniform(1, 5))
            subprocess.run(["git", "fetch", "origin", "main"], check=True)
            subprocess.run(["git", "rebase", "origin/main"], check=True)

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

def parse_nav_table(html, base_url=QSIF_NAV_URL):
    """Parse a historical_nav page's table into rows, and look for a real
    'next page' <a href=...> link.

    Expected columns (per the live site): NAV Date | Scheme Name | NAV(₹)
    Returns (rows, next_url) where next_url is None if no real anchor link
    was found (e.g. if pagination is JS-only via __doPostBack, in which
    case it cannot be followed with plain requests).
    """
    soup = BeautifulSoup(html, 'html.parser')
    rows = []

    tables = soup.find_all('table')
    if not tables:
        qsif_logger.warning("  ⚠ No <table> found on historical_nav page")
        return rows, None, None, {}

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

    # Look for a 'Next' pagination control specifically — NOT a numbered
    # page link like '2', since that's a fixed "go to page 2" button, not
    # a relative "next page" control. Using '2' caused the pager to cycle
    # between two ASP.NET ViewState states instead of advancing forward
    # (confirmed via live log: pages 3 and 5 returned identical duplicate
    # rows to page 1's neighbors). 'Next' style text/symbols are far more
    # likely to mean "go forward from wherever I currently am".
    #
    # User independently confirmed via page inspection the exact control
    # IDs: nav_sch$ctl01$ctl01 = page 2 (numbered link, do NOT use),
    # nav_sch$ctl02$ctl01 = page 3 (numbered link, do NOT use),
    # nav_sch$ctl02$ctl00 = Next (correct — this is what we want).
    # This matches what was already being detected/used in prior runs.
    next_url = None
    next_event_target = None
    candidates = soup.find_all('a', href=True)
    next_texts = ('next', '»', '>', 'next page', 'next >')
    for a in candidates:
        text = a.get_text(strip=True).lower()
        href = a['href'].strip()
        if text in next_texts or 'next' in (a.get('rel') or []):
            if href.lower().startswith('javascript:'):
                m = re.search(r"__doPostBack\('([^']+)'\s*,\s*'([^']*)'\)", href)
                if m:
                    next_event_target = m.group(1)
                    qsif_logger.info(f"  'Next' pagination is __doPostBack with eventTarget='{next_event_target}'")
                else:
                    qsif_logger.info(f"  'Next' link found but is JS-only postback (could not parse eventTarget): {href[:120]}")
            else:
                from urllib.parse import urljoin
                next_url = urljoin(base_url, href)
                qsif_logger.info(f"  Real 'Next' href found: {next_url}")
            break

    if next_url is None and next_event_target is None:
        qsif_logger.info("  No 'Next' pagination link (real or postback) found on this page — "
                          "may be on the last page, or site uses a different 'Next' label/symbol")


    # Hidden ASP.NET form fields needed to replicate a postback via POST
    hidden_fields = {}
    for inp in soup.find_all('input', type='hidden'):
        name = inp.get('name')
        if name:
            hidden_fields[name] = inp.get('value', '')

    return rows, next_url, next_event_target, hidden_fields


def search_qsif_scheme(session, scheme_name_query, from_date=None, to_date=None):
    """Search the historical_nav page for a specific scheme name, using
    the site's own search box — confirmed from actual page source:

    - Search input field name: ctl00$ContentPlaceHolder1$txtschname
    - Date range fields (type="date", standard HTML date input, so POST
      value format is YYYY-MM-DD regardless of display format):
        ctl00$ContentPlaceHolder1$FromIds
        ctl00$ContentPlaceHolder1$ToIds
    - 'Go' button is itself a __doPostBack (not a real submit):
      __doPostBack('ctl00$ContentPlaceHolder1$BtnGo','')

    from_date/to_date are optional datetime.date objects. If omitted, the
    search runs with scheme name only (returns full available history,
    newest first, as already confirmed working). If given, only NAV rows
    within that date range are returned — used for incremental/delta
    fetches (e.g. "everything since the last saved date").

    Returns (rows, next_url, event_target, hidden_fields) — same shape as
    parse_nav_table — so the result can be fed into the same pagination
    loop that walks subsequent pages of the search result if it spans
    multiple pages.
    """
    try:
        resp = session.get(QSIF_NAV_URL, headers=SCRAPE_HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        qsif_logger.warning(f"  ⚠ Initial page fetch (before search) failed: {e}")
        return [], None, None, {}

    soup = BeautifulSoup(resp.text, 'html.parser')
    hidden_fields = {}
    for inp in soup.find_all('input', type='hidden'):
        name = inp.get('name')
        if name:
            hidden_fields[name] = inp.get('value', '')

    post_data = dict(hidden_fields)
    post_data['ctl00$ContentPlaceHolder1$txtschname'] = scheme_name_query
    if from_date:
        post_data['ctl00$ContentPlaceHolder1$FromIds'] = from_date.strftime('%Y-%m-%d')
    if to_date:
        post_data['ctl00$ContentPlaceHolder1$ToIds'] = to_date.strftime('%Y-%m-%d')
    post_data['__EVENTTARGET'] = 'ctl00$ContentPlaceHolder1$BtnGo'
    post_data['__EVENTARGUMENT'] = ''

    try:
        resp = session.post(QSIF_NAV_URL, data=post_data, headers=SCRAPE_HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        qsif_logger.warning(f"  ⚠ Search POST for '{scheme_name_query}' failed: {e}")
        return [], None, None, {}

    date_range_str = f" [{from_date} to {to_date}]" if (from_date or to_date) else ""
    qsif_logger.info(f"  Searched for scheme name: '{scheme_name_query}'{date_range_str}")
    return parse_nav_table(resp.text, base_url=QSIF_NAV_URL)


def fetch_qsif_scheme_history(session, scheme_name_query, from_date=None, to_date=None, max_pages=200):
    """Get NAV history for one specific scheme, using the site's real
    search box (txtschname + FromIds/ToIds + BtnGo) so the server itself
    filters to just that scheme (and date range, if given) — no need to
    wade through ~20 unrelated schemes' interleaved rows.

    If from_date/to_date are omitted: returns the scheme's FULL available
    history (used for the one-off manual seed run).
    If given: returns only rows in that date range (used for the
    scheduled delta run — fetch only the gap since the last saved date).

    Since every page of a search result is, by definition, only rows for
    the searched scheme (and date range), this simply paginates (via the
    confirmed 'Next' __doPostBack mechanism) until pagination genuinely
    ends.
    """
    all_rows = []

    page_rows, next_url, event_target, hidden_fields = search_qsif_scheme(
        session, scheme_name_query, from_date=from_date, to_date=to_date
    )
    if not page_rows:
        qsif_logger.warning(f"  ⚠ Search for '{scheme_name_query}' returned zero rows")
        return all_rows
    all_rows.extend(page_rows)
    qsif_logger.info(f"  Search page 1: {len(page_rows)} rows")

    url = QSIF_NAV_URL
    for page_num in range(2, max_pages + 1):
        if next_url:
            try:
                resp = session.get(next_url, headers=SCRAPE_HEADERS, timeout=15)
                resp.raise_for_status()
            except Exception as e:
                qsif_logger.warning(f"  ⚠ Search page {page_num} GET failed: {e}")
                break
            request_url = next_url
        elif event_target:
            post_data = dict(hidden_fields)
            # txtschname/FromIds/ToIds are regular (non-hidden) inputs, so
            # they're never captured by parse_nav_table()'s hidden-input
            # scan. Without re-sending them explicitly here, the server
            # resets the filter from page 2 onward — confirmed via live
            # log for txtschname: page 1 correctly filtered, pages 2+
            # returned everything. Same risk applies to the date fields.
            post_data['ctl00$ContentPlaceHolder1$txtschname'] = scheme_name_query
            if from_date:
                post_data['ctl00$ContentPlaceHolder1$FromIds'] = from_date.strftime('%Y-%m-%d')
            if to_date:
                post_data['ctl00$ContentPlaceHolder1$ToIds'] = to_date.strftime('%Y-%m-%d')
            post_data['__EVENTTARGET'] = event_target
            post_data['__EVENTARGUMENT'] = ''
            try:
                resp = session.post(url, data=post_data, headers=SCRAPE_HEADERS, timeout=15)
                resp.raise_for_status()
            except Exception as e:
                qsif_logger.warning(f"  ⚠ Search page {page_num} POST (eventTarget='{event_target}') failed: {e}")
                break
            request_url = url
        else:
            qsif_logger.info(f"  Search pagination ended after page {page_num - 1} "
                              f"(no further 'Next' link)")
            break

        page_rows, next_url, event_target, hidden_fields = parse_nav_table(resp.text, base_url=request_url)
        if not page_rows:
            qsif_logger.info(f"  Search page {page_num}: no rows parsed, stopping")
            break

        # Defensive check: if the filter was somehow lost again (e.g. site
        # behavior changes), rows won't match the query — catch it loudly
        # here rather than silently mixing in wrong-scheme data.
        off_topic = [r for r in page_rows if scheme_name_query.lower() not in r['scheme_name'].lower()]
        if off_topic:
            qsif_logger.warning(
                f"  ⚠ Search page {page_num}: {len(off_topic)}/{len(page_rows)} rows do NOT match "
                f"'{scheme_name_query}' — filter may have been lost on this page. "
                f"Sample off-topic name: '{off_topic[0]['scheme_name']}'. Stopping pagination here."
            )
            break

        all_rows.extend(page_rows)
        qsif_logger.info(f"  Search page {page_num}: {len(page_rows)} rows")
        time.sleep(1)

    qsif_logger.info(f"  ✓ Total rows for '{scheme_name_query}': {len(all_rows)}")
    return all_rows



def parse_qsif_date(date_str):
    """Parse 'DD-Mon-YYYY' (e.g. '19-Jun-2026') into a sortable datetime."""
    try:
        return datetime.strptime(date_str.strip(), '%d-%b-%Y')
    except ValueError:
        return None


def run_qsif_nav_eod():
    """Fetch QSIF EOD NAV (latest + 1D change) per held ISIN — FAST path.

    Uses the site's search box to fetch just the first page (10 rows) per
    scheme, which is always enough for the latest date + previous date
    needed to compute a 1D change. Does NOT paginate further — for full
    multi-year history, see run_qsif_nav_history() / qsif_history.json,
    which is a separate, much slower job.

    Output schema matches the original nav_ltp.json structure (no
    'history' field) so this stays a drop-in daily EOD source alongside
    AMFI MF/SGB data.
    """
    if not QSIF_SCHEME_KEYWORDS:
        qsif_logger.warning("No QSIF_SCHEME_KEYWORDS configured")
        return {}

    session = requests.Session()
    result = {}

    for isin, keyword in QSIF_SCHEME_KEYWORDS.items():
        qsif_logger.info(f"  Fetching EOD NAV for {isin} (search: '{keyword}')")
        matched, _next_url, _event_target, _hidden = search_qsif_scheme(session, keyword)

        if not matched:
            qsif_logger.warning(f"  ⚠ {isin}: search for '{keyword}' returned no rows")
            continue

        seen = set()
        deduped = []
        for r in matched:
            if r['date_str'] in seen:
                continue
            seen.add(r['date_str'])
            deduped.append(r)
        matched = deduped

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
            if prev_date == curr_date:
                qsif_logger.warning(
                    f"  ⚠ {isin}: two most recent rows share the same date ({curr_date.date()}). "
                    f"Leaving change as None rather than reporting a false 0.0."
                )
            else:
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

    qsif_logger.info(f"  ✓ Matched {len(result)}/{len(QSIF_SCHEME_KEYWORDS)} QSIF entries (EOD)")
    return result


def run_qsif_history_seed():
    """Fetch FULL available QSIF NAV history per held ISIN — ONE-OFF SEED.

    Paginates the search result for each scheme until pagination genuinely
    ends, which can take a minute or more per scheme (confirmed: ~17 pages
    / ~170 rows for one scheme in testing). Run this manually once to seed
    qsif_history.json; after that, run_qsif_history_delta() takes over to
    fill only the gap on a schedule.

    Output: {isin: {scheme_name, history: [{date, nav}, ...]}}, written to
    qsif_history.json, oldest-to-newest per scheme. OVERWRITES the file.
    """
    if not QSIF_SCHEME_KEYWORDS:
        qsif_logger.warning("No QSIF_SCHEME_KEYWORDS configured")
        return {}

    session = requests.Session()
    result = {}

    for isin, keyword in QSIF_SCHEME_KEYWORDS.items():
        qsif_logger.info(f"  [SEED] Fetching full history for {isin} (search: '{keyword}')")
        matched = fetch_qsif_scheme_history(session, keyword)  # no date range = full history

        if not matched:
            qsif_logger.warning(f"  ⚠ {isin}: search for '{keyword}' returned no rows")
            continue

        seen = set()
        deduped = []
        for r in matched:
            if r['date_str'] in seen:
                continue
            seen.add(r['date_str'])
            deduped.append(r)
        if len(deduped) < len(matched):
            qsif_logger.warning(
                f"  ⚠ {isin}: removed {len(matched) - len(deduped)} duplicate date row(s)"
            )
        matched = deduped

        dated = []
        for r in matched:
            d = parse_qsif_date(r['date_str'])
            if d:
                dated.append((d, r))
        dated.sort(key=lambda x: x[0])  # oldest first for storage

        if not dated:
            qsif_logger.warning(f"  ⚠ {isin}: matched rows but none had parseable dates")
            continue

        scheme_name = matched[0]['scheme_name']
        result[isin] = {
            'scheme_name': scheme_name,
            'source': 'qsif.com',
            'history': [
                {'date': d.strftime('%d-%b-%Y'), 'nav': r['nav']}
                for d, r in dated
            ],
        }
        qsif_logger.info(f"  ✓ {isin}: {len(dated)} dated rows in full history")

    missing = set(QSIF_SCHEME_KEYWORDS.keys()) - set(result.keys())
    if missing:
        qsif_logger.warning(f"  ⚠ {len(missing)} ISIN(s) not matched: {sorted(missing)}")

    qsif_logger.info(f"  ✓ Matched {len(result)}/{len(QSIF_SCHEME_KEYWORDS)} QSIF entries (seed)")
    return result


def run_qsif_history_delta():
    """Fill the GAP in qsif_history.json since the last saved date — SCHEDULED.

    For each held ISIN: reads the existing qsif_history.json, finds the
    latest saved date for that scheme, and fetches only NAV rows from
    (latest_saved_date + 1 day) through today using the site's FromIds/
    ToIds date filters — not the full history again. Appends new rows to
    the existing history and re-saves, so the file keeps accumulating
    rather than being re-fetched from scratch each run.

    If a scheme has no existing history yet (seed never run, or a new
    ISIN was just added to QSIF_SCHEME_KEYWORDS), falls back to fetching
    full history for that scheme only, with a warning.

    Returns the FULL merged result dict (existing + newly appended rows)
    for every ISIN in QSIF_SCHEME_KEYWORDS, ready to be saved as-is.
    """
    if not QSIF_SCHEME_KEYWORDS:
        qsif_logger.warning("No QSIF_SCHEME_KEYWORDS configured")
        return {}

    existing = load_json(QSIF_HISTORY_OUTPUT_FILE)
    # load_json returns {} on missing/invalid file; strip _metadata if present
    existing = {k: v for k, v in existing.items() if k != '_metadata'}

    session = requests.Session()
    result = {}
    today = datetime.now(UTC).date()

    for isin, keyword in QSIF_SCHEME_KEYWORDS.items():
        prior = existing.get(isin, {})
        prior_history = prior.get('history', [])

        # Find the latest saved date for this scheme
        prior_dated = []
        for h in prior_history:
            d = parse_qsif_date(h.get('date', ''))
            if d:
                prior_dated.append((d, h))
        prior_dated.sort(key=lambda x: x[0])

        if not prior_dated:
            qsif_logger.warning(
                f"  ⚠ {isin}: no existing history found in {QSIF_HISTORY_OUTPUT_FILE.name} — "
                f"fetching FULL history for this scheme as a fallback (run the seed job if "
                f"this wasn't expected)"
            )
            matched = fetch_qsif_scheme_history(session, keyword)
            from_date = None
        else:
            last_saved_date = prior_dated[-1][0].date()
            from_date = last_saved_date + timedelta(days=1)
            if from_date > today:
                qsif_logger.info(f"  {isin}: already up to date (latest saved {last_saved_date}), nothing to fetch")
                result[isin] = prior
                continue
            qsif_logger.info(f"  [DELTA] {isin}: fetching gap {from_date} to {today} (search: '{keyword}')")
            matched = fetch_qsif_scheme_history(session, keyword, from_date=from_date, to_date=today)

        if not matched:
            qsif_logger.info(f"  {isin}: no new rows in gap range — keeping existing history as-is")
            if prior_dated:
                result[isin] = prior
            continue

        seen_dates = {h.get('date') for h in prior_history}
        new_dated = []
        for r in matched:
            d = parse_qsif_date(r['date_str'])
            if d and d.strftime('%d-%b-%Y') not in seen_dates:
                new_dated.append((d, r))

        if not new_dated:
            qsif_logger.info(f"  {isin}: fetched rows were all already in saved history (no actual gap)")
            result[isin] = prior if prior_dated else {
                'scheme_name': matched[0]['scheme_name'],
                'source': 'qsif.com',
                'history': [],
            }
            continue

        new_dated.sort(key=lambda x: x[0])
        new_entries = [{'date': d.strftime('%d-%b-%Y'), 'nav': r['nav']} for d, r in new_dated]

        merged_history = list(prior_history) + new_entries
        # Final sort + dedup safety net, oldest first
        merged_sorted = sorted(
            {h['date']: h for h in merged_history}.values(),
            key=lambda h: parse_qsif_date(h['date']) or datetime.min
        )

        scheme_name = matched[0]['scheme_name'] if matched else prior.get('scheme_name', isin)
        result[isin] = {
            'scheme_name': scheme_name,
            'source': 'qsif.com',
            'history': merged_sorted,
        }
        qsif_logger.info(
            f"  ✓ {isin}: appended {len(new_entries)} new row(s), "
            f"total now {len(merged_sorted)} dated rows"
        )

    # Carry forward any ISIN that's in the existing file but somehow wasn't
    # processed above (shouldn't normally happen, but avoids silent data loss)
    for isin, prior in existing.items():
        if isin not in result and isin in QSIF_SCHEME_KEYWORDS:
            result[isin] = prior

    qsif_logger.info(f"  ✓ Processed {len(result)}/{len(QSIF_SCHEME_KEYWORDS)} QSIF entries (delta)")
    return result


# ===========================================================================
# Main
# ===========================================================================

def main_eod():
    """Daily EOD fetch: AMFI (MF/SGB) + QSIF latest NAV/change. FAST.
    Writes data/nav_ltp.json (existing structure, unchanged)."""
    merged = {}

    try:
        amfi = run_amfi_nav()
        merged.update(amfi)
    except Exception as e:
        logger.warning(f"  ⚠ AMFI NAV run failed: {e}")

    try:
        qsif = run_qsif_nav_eod()
        merged.update(qsif)
    except Exception as e:
        qsif_logger.warning(f"  ⚠ QSIF EOD NAV run failed: {e}")

    output = {"_metadata": {"generated_at": now(), "count": len(merged), "source": "AMFI + qsif.com"}}
    output.update(merged)
    save_json(NAV_LTP_OUTPUT_FILE, output)
    logger.info(f"✓ Wrote {NAV_LTP_OUTPUT_FILE} ({len(merged)} entries)")

    git_commit_and_push(
        [NAV_LTP_OUTPUT_FILE, LOG_FILE],
        f"Update nav_ltp.json ({len(merged)} entries) [skip ci]"
    )


def main_history_seed():
    """ONE-OFF manual run: full QSIF history fetch, OVERWRITES qsif_history.json.
    SLOW (minutes, multiple pages per scheme). Run this once to seed the
    file; after that, use 'history-delta' on a schedule to keep it
    up to date by fetching only the gap."""
    try:
        qsif_hist = run_qsif_history_seed()
    except Exception as e:
        qsif_logger.warning(f"  ⚠ QSIF history seed run failed: {e}")
        qsif_hist = {}

    output = {
        "_metadata": {
            "generated_at": now(),
            "count": len(qsif_hist),
            "source": "qsif.com",
            "mode": "seed (full history)"
        }
    }
    output.update(qsif_hist)
    save_json(QSIF_HISTORY_OUTPUT_FILE, output)
    qsif_logger.info(f"✓ Wrote {QSIF_HISTORY_OUTPUT_FILE} ({len(qsif_hist)} entries) [SEED]")

    git_commit_and_push(
        [QSIF_HISTORY_OUTPUT_FILE, LOG_FILE],
        f"Seed qsif_history.json ({len(qsif_hist)} entries) [skip ci]"
    )


def main_history_delta():
    """SCHEDULED run: fetch only the gap since the last saved date per
    scheme, and append to the existing qsif_history.json (one file keeps
    accumulating). FAST when little/no gap exists; proportional to gap
    size otherwise. Requires qsif_history.json to already exist (run
    'history-seed' once first) — falls back to full history per-scheme
    if a scheme has no prior saved data."""
    try:
        qsif_hist = run_qsif_history_delta()
    except Exception as e:
        qsif_logger.warning(f"  ⚠ QSIF history delta run failed: {e}")
        qsif_hist = {}

    output = {
        "_metadata": {
            "generated_at": now(),
            "count": len(qsif_hist),
            "source": "qsif.com",
            "mode": "delta (gap-fill)"
        }
    }
    output.update(qsif_hist)
    save_json(QSIF_HISTORY_OUTPUT_FILE, output)
    qsif_logger.info(f"✓ Wrote {QSIF_HISTORY_OUTPUT_FILE} ({len(qsif_hist)} entries) [DELTA]")

    git_commit_and_push(
        [QSIF_HISTORY_OUTPUT_FILE, LOG_FILE],
        f"Update qsif_history.json via delta ({len(qsif_hist)} entries) [skip ci]"
    )


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "eod"
    if mode == "history-seed":
        main_history_seed()
    elif mode == "history-delta":
        main_history_delta()
    else:
        main_eod()
