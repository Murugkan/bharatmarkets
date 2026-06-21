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

Part 2 — QSIF NAV — two modes (run via CLI arg):

  `python fetch_nav_ltp.py` or `python fetch_nav_ltp.py eod` (default):
    FAST daily path. Uses the site's search box (txtschname + BtnGo
    postback, confirmed from page source) to fetch just the latest page
    (10 rows) per held scheme — always enough for latest NAV + 1D change.
    Output: data/nav_ltp.json (AMFI + QSIF EOD combined, original schema).

  `python fetch_nav_ltp.py qsif-nav`:
    Self-determining — no separate seed/delta flags needed. Per held
    ISIN: no existing data in qsif_nav.json -> full fetch (paginates
    until pagination genuinely ends, confirmed ~17 pages/~170 rows for
    one scheme in testing). Existing data with a gap -> fetches ONLY the
    gap since the last saved date (via the site's FromIds/ToIds
    date-range filters, confirmed from page source). Already current ->
    no network call for that ISIN. One file (data/qsif_nav.json) keeps
    accumulating — same command works whether it's the very first run
    ever or a routine daily run.
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
QSIF_NAV_OUTPUT_FILE = DATA_DIR / 'qsif_nav.json'

LOG_FILE = DATA_DIR / 'logs/fetch_nav_ltp.log'
SUMMARY_FILE = DATA_DIR / 'fetch_nav_ltp_summary.json'

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


def update_summary(mode, status, **fields):
    """Update this job's entry in the small, overwritten-per-run summary
    file (data/fetch_nav_ltp_summary.json) — one line per mode (eod/seed/
    delta), no accumulated history.

    Re-reads the file fresh right before writing (rather than relying on
    whatever was loaded at script start) to minimize the window for a
    lost update if another fetch_nav_ltp.py job is running concurrently
    and also updating its own entry — final safety against a true race
    still comes from git_commit_and_push()'s fetch/rebase retry, since
    each job only ever overwrites its OWN named key, never another job's.

    This file (not the full fetch_nav_ltp.log) is what gets committed —
    deliberately avoiding the full log, since 3 jobs (eod/seed/delta) can
    run concurrently and all writing/committing the same growing log file
    caused real, repeated rebase conflicts in practice.
    """
    summary = load_json(SUMMARY_FILE)
    summary = {k: v for k, v in summary.items() if k != '_comment'}
    summary['_comment'] = "Latest outcome per fetch_nav_ltp.py mode — overwritten each run, no history"
    summary[mode] = {
        'status': status,
        'last_run_at': now(),
        **fields,
    }
    save_json(SUMMARY_FILE, summary)


def git_commit_and_push(paths, message, max_attempts=5):
    """Commit and push the given file paths directly from this script.

    Runs `git add/commit/push` so the workflow YAML no longer needs to own
    committing — this script always commits the file it just wrote, in the
    same process, immediately after writing it. Avoids the checkout/commit
    ordering issue where a separate workflow step could run against a stale
    working directory and make 'previous' data look identical to 'current'.

    Retries on push rejection (e.g. another concurrent job in the same
    workflow run pushed first) via fetch + stash + rebase + stash-pop,
    matching the pattern already used by every other commit step in
    e2e-parallel.yml. The stash step is necessary here specifically
    because the log file handler stays open and keeps writing to LOG_FILE
    for the remainder of this script's execution — meaning by the time a
    retry's rebase runs, git sees the log as unstaged-modified again
    relative to the commit just made, and a plain rebase refuses to run
    with a dirty tree. Confirmed in practice: a real push rejection
    correctly triggered the retry, but the bare rebase then failed with
    "You have unstaged changes" because of this.

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
            logger.warning(f"  Push rejected (attempt {attempt}/{max_attempts}) — fetching, stashing, and rebasing, then retrying...")
            time.sleep(random.uniform(1, 5))
            subprocess.run(["git", "fetch", "origin", "main"], check=True)
            # Stash first: LOG_FILE is still being actively written by this
            # process's own logging handler, so it's almost always dirty
            # again here even though it was just committed.
            stash = subprocess.run(
                ["git", "stash", "--include-untracked"],
                capture_output=True, text=True
            )
            stashed = stash.returncode == 0 and "No local changes" not in (stash.stdout or "")

            rebase = subprocess.run(
                ["git", "rebase", "origin/main"],
                capture_output=True, text=True
            )
            if rebase.returncode != 0:
                # A genuine content conflict (not just "behind") — e.g. two
                # concurrent fetch_nav_ltp.py jobs both created/edited
                # SUMMARY_FILE before either saw the other's commit, so git
                # can't auto-merge two independent versions of the same
                # JSON file. Confirmed in practice: "CONFLICT (add/add)".
                #
                # Resolution: abort the conflicted rebase, discard this
                # job's stale local commit, reset onto the latest
                # origin/main, then re-run THIS job's own write logic
                # against that fresh base — which naturally produces a
                # correct merge for SUMMARY_FILE specifically (each job
                # only ever updates its own named key in that file; see
                # update_summary()) and a correct overwrite for the JSON
                # output files (which are wholesale per-run snapshots,
                # not something meant to be merged anyway).
                logger.warning(
                    f"  ⚠ Rebase hit a real conflict (attempt {attempt}/{max_attempts}) — "
                    f"likely a concurrent fetch_nav_ltp.py job also wrote SUMMARY_FILE. "
                    f"Aborting rebase, resetting onto latest origin/main, and retrying "
                    f"with a fresh write rather than merging stale local state."
                )
                subprocess.run(["git", "rebase", "--abort"], check=False)
                if stashed:
                    subprocess.run(["git", "stash", "pop"], check=False)
                subprocess.run(["git", "reset", "--hard", "origin/main"], check=True)
                return "conflict_reset"

            if stashed:
                subprocess.run(["git", "stash", "pop"])
                # Fold whatever the stash restored (e.g. further log writes
                # since the last commit) into the existing commit via
                # amend, rather than creating a new commit each retry.
                subprocess.run(["git", "add"] + str_paths)
                subprocess.run(["git", "commit", "--amend", "--no-edit"], check=False)

    except subprocess.CalledProcessError as e:
        logger.error(f"⚠ Git commit/push failed: {e}")
    except Exception as e:
        logger.error(f"⚠ Unexpected error during git commit/push: {e}")
    return None


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

        qsif_logger.debug(
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
        qsif_logger.debug(f"  Parsed {len(rows)} rows from this page")
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
                    qsif_logger.debug(f"  'Next' pagination is __doPostBack with eventTarget='{next_event_target}'")
                else:
                    qsif_logger.warning(f"  'Next' link found but is JS-only postback (could not parse eventTarget): {href[:120]}")
            else:
                from urllib.parse import urljoin
                next_url = urljoin(base_url, href)
                qsif_logger.debug(f"  Real 'Next' href found: {next_url}")
            break

    if next_url is None and next_event_target is None:
        qsif_logger.debug("  No 'Next' pagination link (real or postback) found on this page — "
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
    qsif_logger.debug(f"  Searched for scheme name: '{scheme_name_query}'{date_range_str}")
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
    pages_fetched = 0

    page_rows, next_url, event_target, hidden_fields = search_qsif_scheme(
        session, scheme_name_query, from_date=from_date, to_date=to_date
    )
    if not page_rows:
        qsif_logger.warning(f"  ⚠ Search for '{scheme_name_query}' returned zero rows")
        return all_rows
    all_rows.extend(page_rows)
    pages_fetched = 1
    qsif_logger.debug(f"  Search page 1: {len(page_rows)} rows")

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
            qsif_logger.debug(f"  Search pagination ended after page {page_num - 1} "
                               f"(no further 'Next' link)")
            break

        page_rows, next_url, event_target, hidden_fields = parse_nav_table(resp.text, base_url=request_url)
        if not page_rows:
            qsif_logger.debug(f"  Search page {page_num}: no rows parsed, stopping")
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
        pages_fetched += 1
        qsif_logger.debug(f"  Search page {page_num}: {len(page_rows)} rows")
        time.sleep(1)

    qsif_logger.info(f"  ✓ Total rows for '{scheme_name_query}': {len(all_rows)} (across {pages_fetched} page(s))")
    return all_rows



def parse_qsif_date(date_str):
    """Parse 'DD-Mon-YYYY' (e.g. '19-Jun-2026') into a sortable datetime."""
    try:
        return datetime.strptime(date_str.strip(), '%d-%b-%Y')
    except ValueError:
        return None


def build_qsif_history_entry(scheme_name, dated_rows_oldest_first):
    """Build the standardized per-ISIN history entry.

    dated_rows_oldest_first: list of (datetime, {'nav': float, ...}) tuples,
    sorted oldest to newest (one entry per distinct date — caller must
    already have deduped).

    history is stored as `periods: {date: nav}` — ISO date (YYYY-MM-DD)
    keys mapping straight to the raw NAV value, with NO per-row change/
    changePct. This intentionally matches how every other financial KPI
    time series in this pipeline is stored (e.g. yahoofin_raw's OHLCV
    history in market_data_flatten.py, which is also a flat date->value
    dict, not a list of rows with computed deltas) — so it can flow
    through the SAME flatten transform path rather than a bespoke one.

    Output shape:

        {
          "scheme_name": "...",
          "source": "qsif.com",
          "latest": {
            "date": "18-Jun-2026", "ltp": 10.4574,
            "change": 0.0006, "changePct": 0.0057
          },
          "periods": {
            "2026-06-16": 10.3906,
            "2026-06-17": 10.4568,
            "2026-06-18": 10.4574
          }
        }

    'latest' is the one place change/changePct still live — it's a
    snapshot field (today vs yesterday), not a series, so computing it
    once here is correct and unrelated to the periods/series convention
    above.
    """
    periods = {}
    for d, r in dated_rows_oldest_first:
        periods[d.strftime('%Y-%m-%d')] = r['nav']

    latest = None
    if dated_rows_oldest_first:
        last_date, last_row = dated_rows_oldest_first[-1]
        last_nav = last_row['nav']
        change = None
        change_pct = None
        if len(dated_rows_oldest_first) >= 2:
            prev_date, prev_row = dated_rows_oldest_first[-2]
            prev_nav = prev_row['nav']
            if prev_nav:
                change = round(last_nav - prev_nav, 4)
                change_pct = round((last_nav - prev_nav) / prev_nav * 100, 4)
        latest = {
            'date': last_date.strftime('%d-%b-%Y'),
            'ltp': last_nav,
            'change': change,
            'changePct': change_pct,
        }

    return {
        'scheme_name': scheme_name,
        'source': 'qsif.com',
        'latest': latest,
        'periods': periods,
    }


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


def run_qsif_nav_update():
    """Fill the GAP in qsif_history.json since the last saved date — SCHEDULED.

    Self-determining per ISIN — no separate "seed" vs "delta" mode needed:
      - No existing data for that ISIN  -> FULL fetch (paginates until the
        site's pagination genuinely ends; can take a minute+ per scheme).
      - Existing data, but a gap exists -> fetch ONLY that gap (latest
        saved date + 1 day through today) via the site's FromIds/ToIds
        date-range filters, then merge into the existing series.
      - Existing data, already current  -> no network call for that ISIN;
        existing entry is reused as-is (just normalized through
        build_qsif_history_entry() in case it was written under an older
        schema).

    Reads/writes qsif_nav.json. Returns the FULL merged result dict
    (existing + newly fetched rows, or untouched where already current)
    for every ISIN in QSIF_SCHEME_KEYWORDS, ready to be saved as-is.
    """
    if not QSIF_SCHEME_KEYWORDS:
        qsif_logger.warning("No QSIF_SCHEME_KEYWORDS configured")
        return {}

    existing = load_json(QSIF_NAV_OUTPUT_FILE)
    # load_json returns {} on missing/invalid file; strip _metadata if present
    existing = {k: v for k, v in existing.items() if k != '_metadata'}

    session = requests.Session()
    result = {}
    today = datetime.now(UTC).date()

    for isin, keyword in QSIF_SCHEME_KEYWORDS.items():
        prior = existing.get(isin, {})
        prior_periods = prior.get('periods', {})

        # Find the latest saved date for this scheme (periods keys are
        # ISO 'YYYY-MM-DD' strings, so this also covers any file written
        # under the older list-of-rows schema gracefully — prior_periods
        # would just be empty for those, falling through to a full fetch).
        prior_dated = []
        for date_str, nav in prior_periods.items():
            try:
                d = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                continue
            prior_dated.append((d, {'nav': nav}))
        prior_dated.sort(key=lambda x: x[0])

        if not prior_dated:
            qsif_logger.warning(
                f"  ⚠ {isin}: no existing history in {QSIF_NAV_OUTPUT_FILE.name} — "
                f"running a full fetch for this scheme"
            )
            matched = fetch_qsif_scheme_history(session, keyword)
            from_date = None
        else:
            last_saved_date = prior_dated[-1][0].date()
            from_date = last_saved_date + timedelta(days=1)
            if from_date > today:
                qsif_logger.info(f"  {isin}: already up to date (latest saved {last_saved_date}), nothing to fetch")
                # Rebuild through the helper even with no new data, so a
                # file written under an older schema self-heals to the
                # current format (e.g. no 'latest', list-shaped history).
                result[isin] = build_qsif_history_entry(
                    prior.get('scheme_name', isin), prior_dated
                )
                continue
            qsif_logger.info(f"  {isin}: fetching gap {from_date} to {today} (search: '{keyword}')")
            matched = fetch_qsif_scheme_history(session, keyword, from_date=from_date, to_date=today)

        if not matched:
            qsif_logger.info(f"  {isin}: no new rows in gap range — keeping existing history as-is")
            if prior_dated:
                result[isin] = build_qsif_history_entry(
                    prior.get('scheme_name', isin), prior_dated
                )
            continue

        # Merge prior + newly fetched rows by ISO date (newly fetched nav
        # wins on overlap, in case a date was re-published with a
        # corrected value — unlikely but safer than silently keeping a
        # stale nav).
        merged_by_date = dict(prior_periods)
        for r in matched:
            d = parse_qsif_date(r['date_str'])
            if d:
                merged_by_date[d.strftime('%Y-%m-%d')] = r['nav']

        merged_dated = []
        for date_str, nav in merged_by_date.items():
            try:
                d = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                continue
            merged_dated.append((d, {'nav': nav}))
        merged_dated.sort(key=lambda x: x[0])  # oldest first

        new_count = len(merged_by_date) - len(prior_periods)

        scheme_name = matched[0]['scheme_name'] if matched else prior.get('scheme_name', isin)
        # Rebuild through the standard helper so 'latest' reflects the
        # true most recent date after merging.
        result[isin] = build_qsif_history_entry(scheme_name, merged_dated)
        qsif_logger.info(
            f"  ✓ {isin}: {new_count} new row(s) merged in, "
            f"total now {len(merged_dated)} dated rows "
            f"(latest: {result[isin]['latest']})"
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

    for attempt in range(2):  # one retry if a concurrent job conflicts on SUMMARY_FILE
        output = {"_metadata": {"generated_at": now(), "count": len(merged), "source": "AMFI + qsif.com"}}
        output.update(merged)
        save_json(NAV_LTP_OUTPUT_FILE, output)
        logger.info(f"✓ Wrote {NAV_LTP_OUTPUT_FILE} ({len(merged)} entries)")

        update_summary('eod', 'success' if merged else 'no_data', entries=len(merged))

        outcome = git_commit_and_push(
            [NAV_LTP_OUTPUT_FILE, SUMMARY_FILE],
            f"Update nav_ltp.json ({len(merged)} entries) [skip ci]"
        )
        if outcome != "conflict_reset":
            break
        logger.warning("  Retrying eod save+commit once against the now-reset origin/main...")


def main_qsif_nav():
    """QSIF NAV update — self-determining, single mode (no separate seed/
    delta CLI flags needed).

    For each held ISIN: no existing data -> full fetch (paginates the
    site until pagination genuinely ends; minute+ per scheme). Existing
    data with a gap -> fetches only that gap. Already current -> no
    network call for that ISIN. See run_qsif_nav_update() for details.

    Writes/accumulates data/qsif_nav.json — one file, always up to date,
    regardless of whether this is the very first run ever or the
    hundredth daily run."""
    try:
        qsif_hist = run_qsif_nav_update()
    except Exception as e:
        qsif_logger.warning(f"  ⚠ QSIF NAV update run failed: {e}")
        qsif_hist = {}

    for attempt in range(2):  # one retry if a concurrent job conflicts on SUMMARY_FILE
        output = {
            "_metadata": {
                "generated_at": now(),
                "count": len(qsif_hist),
                "source": "qsif.com",
                "schema": "per-ISIN: {scheme_name, source, latest: {date, ltp, change, changePct}, periods: {YYYY-MM-DD: nav}}"
            }
        }
        output.update(qsif_hist)
        save_json(QSIF_NAV_OUTPUT_FILE, output)
        qsif_logger.info(f"✓ Wrote {QSIF_NAV_OUTPUT_FILE} ({len(qsif_hist)} entries)")

        update_summary('qsif-nav', 'success' if qsif_hist else 'no_data', entries=len(qsif_hist))

        outcome = git_commit_and_push(
            [QSIF_NAV_OUTPUT_FILE, SUMMARY_FILE],
            f"Update qsif_nav.json ({len(qsif_hist)} entries) [skip ci]"
        )
        if outcome != "conflict_reset":
            break
        qsif_logger.warning("  Retrying qsif_nav save+commit once against the now-reset origin/main...")


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "eod"
    if mode == "qsif-nav":
        main_qsif_nav()
    else:
        main_eod()
