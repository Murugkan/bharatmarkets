#!/usr/bin/env python3
"""
AMFI Mutual Fund NAV + QSIF NAV Fetcher
==========================================
Single mode: `python fetch_nav_ltp.py` (or `python fetch_nav_ltp.py nav`,
equivalent — kept for explicitness in workflow YAML).

Self-determining, single shared output file (data/nav.json) for BOTH
AMFI mutual funds AND QSIF schemes — no separate seed/delta/eod modes:

  - AMFI: fetch_historical_nav() (mfapi.in) always returns the full
    available series in one call (confirmed via mfapi.in's docs:
    "delivers the complete history... refreshed daily") — so every run
    simply fetches the full series and merges it into nav.json's
    existing periods for that ISIN. No partial-fetch mode exists for
    this API; this is the only way to use it. 1M/3M/6M/1Y/3Y point-to-
    point returns are also computed per fund (see compute_returns()).
  - QSIF: per-ISIN self-determining — no existing data -> full fetch
    (paginates the site until pagination genuinely ends, confirmed ~17
    pages/~170 rows for one scheme in testing). Existing data with a gap
    -> fetches ONLY the gap since the last saved date (via the site's
    FromIds/ToIds date-range filters, confirmed from page source).
    Already current -> no network call for that ISIN.

Output: data/nav.json — {isin: {scheme_name, source, latest: {date,
ltp, change, changePct}, periods: {YYYY-MM-DD: nav}}}, one entry per
    ISIN regardless of source. SGBs are explicitly excluded (tracked as
    regular equity-like tickers via the LTP pipeline instead, not here).
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

NAV_OUTPUT_FILE = DATA_DIR / 'nav.json'

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
    file (data/fetch_nav_ltp_summary.json) — currently just one entry
    ('nav', since that's the only mode now), no accumulated history.

    Re-reads the file fresh right before writing (rather than relying on
    whatever was loaded at script start) to minimize the window for a
    lost update if another fetch_nav_ltp.py invocation is running
    concurrently and also updating its own entry — final safety against
    a true race still comes from git_commit_and_push()'s fetch/rebase
    retry, since each run only ever overwrites its OWN named key.

    This file (not the full fetch_nav_ltp.log) is what gets committed —
    deliberately avoiding the full log, since concurrent runs writing/
    committing the same growing log file caused real, repeated rebase
    conflicts in practice (back when there were multiple separate modes
    that could run alongside each other; kept as a defensive design even
    now that there's only one mode, in case of overlapping manual +
    scheduled triggers).
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
    """Collect ISINs from unified-symbols.json holdings for AMFI mutual
    fund instruments only.

    Uses `instrument_type` (now populated for all entries via the
    wizard's AI-enrichment step), falling back to sector == "Mutual Fund"
    for any older entries that predate that field. Does NOT use an ISIN
    "INF" prefix check — ETFs (e.g. JUNIORBEES, INF200KA1FS3) are also
    INF-prefixed but are not mutual funds and have no AMFI NAV.

    SOVEREIGN BOND (SGB) is explicitly excluded — SGBs are tracked as
    regular equity-like tickers via the LTP pipeline (ltp.json), not
    through this NAV-based flow. They were never actually present in
    AMFI's NAVAll.txt anyway (SGBs aren't AMFI-listed), so this exclusion
    is mostly about being explicit/self-documenting rather than changing
    real matched results.
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

        if itype == 'SOVEREIGN BOND' or sector == 'GOVERNMENT SECURITIES':
            continue

        is_mf_like = (
            itype == 'MUTUAL FUND'
            or sector == 'MUTUAL FUND'
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


def build_nav_history_entry(scheme_name, dated_rows_oldest_first, source):
    """Build the standardized per-ISIN NAV history entry — used for BOTH
    AMFI mutual funds and QSIF schemes (source-agnostic; source name is
    passed in rather than hardcoded, since this now serves both).

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
          "source": "qsif.com" or "AMFI",
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
    # Defensive sort: don't rely on the caller already having sorted
    # oldest-first (every current caller does, but this makes the
    # function correct on its own regardless of future callers) — both
    # periods and latest are derived from this single sorted sequence.
    dated_rows_oldest_first = sorted(dated_rows_oldest_first, key=lambda x: x[0])

    # periods is stored newest-first in nav.json itself, matching the
    # convention used for every other periods dict once it reaches
    # market_data.json (see market_data_flatten.py / market_data.py,
    # both of which explicitly sort periods.items() reverse=True before
    # output) — rather than storing oldest-first here and relying on a
    # downstream re-sort.
    periods = {}
    for d, r in reversed(dated_rows_oldest_first):
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
        'source': source,
        'latest': latest,
        'periods': periods,
    }


def run_nav_update():
    """Update nav.json for BOTH AMFI mutual funds and QSIF schemes —
    self-determining, single shared file, single pass.

    AMFI: fetch_historical_nav() (mfapi.in) already returns the FULL
    available series in one call every time — there's no partial/gap-only
    fetch possible against that API, confirmed via mfapi.in's own docs
    ("delivers the complete history... refreshed daily"). So for AMFI,
    every run simply fetches the full series and merges it into
    nav.json's existing periods for that ISIN (new/changed dates win on
    overlap) — there's no optimization being skipped, this is the only
    mode the API supports.

    QSIF: self-determining per ISIN, unchanged from before —
      - No existing data for that ISIN  -> FULL fetch (paginates until the
        site's pagination genuinely ends; can take a minute+ per scheme).
      - Existing data, but a gap exists -> fetch ONLY that gap (latest
        saved date + 1 day through today) via the site's FromIds/ToIds
        date-range filters, then merge into the existing series.
      - Existing data, already current  -> no network call for that ISIN.

    Reads/writes the SAME nav.json for both sources — AMFI and QSIF
    entries are just different ISINs in the same top-level dict. Returns
    the FULL merged result (existing + newly fetched, for every relevant
    ISIN), ready to be saved as-is.
    """
    existing = load_json(NAV_OUTPUT_FILE)
    # load_json returns {} on missing/invalid file; strip _metadata if present
    existing = {k: v for k, v in existing.items() if k != '_metadata'}

    result = {}

    # ── AMFI mutual funds ────────────────────────────────────────────
    amfi_isins = get_portfolio_isins()
    logger.info(f"Portfolio ISINs to match (AMFI MUTUAL FUND): {len(amfi_isins)}")
    if amfi_isins:
        text = fetch_navall()
        matched = parse_navall(text, amfi_isins)
        missing = amfi_isins - set(matched.keys())
        if missing:
            logger.warning(f"  ⚠ {len(missing)} AMFI ISIN(s) not found in NAVAll.txt: {sorted(missing)}")
        logger.info(f"  ✓ Matched {len(matched)}/{len(amfi_isins)} AMFI ISINs")

        for isin, entry in matched.items():
            scheme_code = entry.get('scheme_code')
            scheme_name = entry.get('scheme_name', isin)
            prior = existing.get(isin, {})
            prior_periods = prior.get('periods', {})

            if not scheme_code:
                # No scheme_code to fetch history with — fall back to
                # just today's single NAVAll.txt value if we have one,
                # merged into whatever periods already existed.
                merged_by_date = dict(prior_periods)
                nav_date = entry.get('date')
                nav_val = entry.get('nav')
                if nav_date and nav_val is not None:
                    try:
                        d = datetime.strptime(nav_date, '%d-%m-%Y')
                        merged_by_date[d.strftime('%Y-%m-%d')] = float(nav_val)
                    except (ValueError, TypeError):
                        pass
            else:
                hist = fetch_historical_nav(scheme_code)  # full series, every call
                merged_by_date = dict(prior_periods)
                for h in hist:
                    try:
                        d = datetime.strptime(h['date'], '%d-%m-%Y')
                        merged_by_date[d.strftime('%Y-%m-%d')] = float(h['nav'])
                    except (ValueError, KeyError, TypeError):
                        continue

            merged_dated = []
            for date_str, nav in merged_by_date.items():
                try:
                    d = datetime.strptime(date_str, '%Y-%m-%d')
                except ValueError:
                    continue
                merged_dated.append((d, {'nav': nav}))

            if not merged_dated:
                logger.warning(f"  ⚠ {isin}: no usable NAV data (AMFI), skipping")
                continue

            new_count = len(merged_by_date) - len(prior_periods)
            result[isin] = build_nav_history_entry(scheme_name, merged_dated, source='AMFI')

            # 1M/3M/6M/1Y/3Y point-to-point returns, computed from the
            # raw mfapi.in history when we fetched it this run (native
            # {date, nav} shape compute_returns() expects). Not
            # recomputed from periods to avoid a redundant date-format
            # round-trip — only available when scheme_code was present.
            if scheme_code and hist:
                returns = compute_returns(hist)
                if returns:
                    result[isin]['returns'] = returns

            logger.info(
                f"  ✓ {isin} ({scheme_name}): {new_count} new/updated row(s), "
                f"total now {len(merged_dated)} dated rows "
                f"(latest: {result[isin]['latest']})"
            )

    # ── QSIF schemes ─────────────────────────────────────────────────
    if not QSIF_SCHEME_KEYWORDS:
        qsif_logger.warning("No QSIF_SCHEME_KEYWORDS configured")
    else:
        session = requests.Session()
        today = datetime.now(UTC).date()

        for isin, keyword in QSIF_SCHEME_KEYWORDS.items():
            prior = existing.get(isin, {})
            prior_periods = prior.get('periods', {})

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
                    f"  ⚠ {isin}: no existing history in {NAV_OUTPUT_FILE.name} — "
                    f"running a full fetch for this scheme"
                )
                matched = fetch_qsif_scheme_history(session, keyword)
                from_date = None
            else:
                last_saved_date = prior_dated[-1][0].date()
                from_date = last_saved_date + timedelta(days=1)
                if from_date > today:
                    qsif_logger.info(f"  {isin}: already up to date (latest saved {last_saved_date}), nothing to fetch")
                    result[isin] = build_nav_history_entry(
                        prior.get('scheme_name', isin), prior_dated, source='qsif.com'
                    )
                    continue
                qsif_logger.info(f"  {isin}: fetching gap {from_date} to {today} (search: '{keyword}')")
                matched = fetch_qsif_scheme_history(session, keyword, from_date=from_date, to_date=today)

            if not matched:
                qsif_logger.info(f"  {isin}: no new rows in gap range — keeping existing history as-is")
                if prior_dated:
                    result[isin] = build_nav_history_entry(
                        prior.get('scheme_name', isin), prior_dated, source='qsif.com'
                    )
                continue

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

            new_count = len(merged_by_date) - len(prior_periods)
            scheme_name = matched[0]['scheme_name'] if matched else prior.get('scheme_name', isin)
            result[isin] = build_nav_history_entry(scheme_name, merged_dated, source='qsif.com')
            qsif_logger.info(
                f"  ✓ {isin}: {new_count} new row(s) merged in, "
                f"total now {len(merged_dated)} dated rows "
                f"(latest: {result[isin]['latest']})"
            )

    # Carry forward any ISIN present in the existing file but not
    # processed above (shouldn't normally happen, but avoids silent
    # data loss for e.g. a scheme temporarily missing from both sources)
    for isin, prior in existing.items():
        if isin not in result:
            result[isin] = prior

    logger.info(f"✓ nav.json update complete: {len(result)} total entries")
    return result

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

def main_nav():
    """NAV update for BOTH AMFI mutual funds and QSIF schemes —
    self-determining, single mode, single shared output file.

    AMFI: fetch_historical_nav() (mfapi.in) always returns the full
    series; each run merges it into nav.json's existing periods.
    QSIF: per-ISIN self-determining — no existing data -> full fetch
    (paginates the site until pagination genuinely ends; minute+ per
    scheme). Existing data with a gap -> fetches only that gap. Already
    current -> no network call for that ISIN. See run_nav_update() for
    full details on both.

    Writes/accumulates data/nav.json — one file, both sources, always up
    to date, regardless of whether this is the very first run ever or
    the hundredth daily run. SGBs are NOT included here — they're tracked
    as regular equity-like tickers via the LTP pipeline instead."""
    try:
        nav_data = run_nav_update()
    except Exception as e:
        logger.warning(f"  ⚠ NAV update run failed: {e}")
        nav_data = {}

    for attempt in range(2):  # one retry if a concurrent job conflicts on SUMMARY_FILE
        output = {
            "_metadata": {
                "generated_at": now(),
                "count": len(nav_data),
                "source": "AMFI + qsif.com",
                "schema": "per-ISIN: {scheme_name, source, latest: {date, ltp, change, changePct}, periods: {YYYY-MM-DD: nav}}"
            }
        }
        output.update(nav_data)
        save_json(NAV_OUTPUT_FILE, output)
        logger.info(f"✓ Wrote {NAV_OUTPUT_FILE} ({len(nav_data)} entries)")

        update_summary('nav', 'success' if nav_data else 'no_data', entries=len(nav_data))

        outcome = git_commit_and_push(
            [NAV_OUTPUT_FILE, SUMMARY_FILE],
            f"Update nav.json ({len(nav_data)} entries) [skip ci]"
        )
        if outcome != "conflict_reset":
            break
        logger.warning("  Retrying nav save+commit once against the now-reset origin/main...")


if __name__ == "__main__":
    # 'nav' is now the only mode (covers both latest snapshot and full
    # history, for AMFI + QSIF) — no CLI arg needed anymore.
    main_nav()
