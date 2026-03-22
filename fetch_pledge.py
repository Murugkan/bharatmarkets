#!/usr/bin/env python3
"""
BharatMarkets Pro - Pledge% Fetcher
=====================================
Uses Playwright headless browser to render Screener.in JS-rendered pages
and extract promoter pledge% for each portfolio stock.

Reads:  portfolio_symbols.txt
Writes: pledge.json  { "PVRINOX": 10.89, "ABFRL": 0.0, ... }

Run:    python fetch_pledge.py
Install: pip install playwright && playwright install chromium
"""

import json, time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    raise SystemExit("pip install playwright && playwright install chromium")

PORTFOLIO_FILE = "portfolio_symbols.txt"
PLEDGE_FILE    = "pledge.json"
DELAY          = 2.0   # seconds between page loads

SKIP = {"NIFTY","BANKNIFTY","NIFTY50","SENSEX","NIFTYIT","MIDCAP","SMALLCAP","NIFTYBANK"}

# Map CDSL/NSE symbols to the correct Screener.in URL slug
# Screener uses NSE symbol for most stocks, but some differ
SCREENER_MAP = {
    "HBLPOWER":      "HBLENGINE",
    "HBLPOWERSYS":   "HBLENGINE",
    "HIGHENERGYB":   "HIGHENE",
    "HINDRECTIF":    "HIRECT",
    "ZINKA":         "BLACKBUCK",
    "CIGNITI":       "CIGNITITEC",
    "GRAUERWEIL":    "GRAUWEIL",
    "ROSSELLTECH":   "ROSSTECH",
    "INDOTECHTR":    "INDOTECH",
    "SHILCHAR":      "SHILCTECH",
    "KPENERGI":      "KPEL",
    "MBENGINEERING": "MBEL",
    "SSPOWERSWIT":   "SSPOWERSWIT",   # try as-is
    "AZADINDIA":     "AZADIND",
    "KWALITYPHARM":  "KPL",
    "CAPITALNUMB":   "CNINFOTECH",
    "TITANBIOTE":    "TITANBIO",
    "SIKAINTERP":    "SIKA",
    "SKMEPEX":       "SKMEGGPROD",
    "REVATHI":       "RVTH",
    "IGI":           "IGIL",
    "SUYOGTELE":     "SUYOG",
    "QUALPOWER":     "QPOWER",
    "CELLOWORLD":    "CELLO",
    "MCDOWELL-N":    "UNITDSPR",
}


def load_symbols():
    syms = []
    seen = set()
    if Path(PORTFOLIO_FILE).exists():
        for line in Path(PORTFOLIO_FILE).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            sym = line.split("|")[0].strip().upper()
            if sym and sym not in SKIP and sym not in seen:
                syms.append(sym)
                seen.add(sym)
    print(f"Loaded {len(syms)} symbols from {PORTFOLIO_FILE}")
    return syms


def safe_float(s):
    try:
        return float(str(s).replace("%", "").replace(",", "").strip())
    except Exception:
        return None


def get_screener_slug(sym):
    return SCREENER_MAP.get(sym, sym)


def fetch_pledge_for_sym(page, sym):
    """
    Load Screener.in page, expand the Promoters row via JS click,
    then read the Pledged sub-row value.
    Returns float pledge% or None if page failed to load.
    """
    slug = get_screener_slug(sym)

    urls = [
        f"https://www.screener.in/company/{slug}/consolidated/",
        f"https://www.screener.in/company/{slug}/",
    ]
    # If slug differs from sym, also try original sym
    if slug != sym:
        urls += [
            f"https://www.screener.in/company/{sym}/consolidated/",
            f"https://www.screener.in/company/{sym}/",
        ]

    for url in urls:
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=25000)
            if resp and resp.status == 404:
                continue

            # Wait for shareholding table
            try:
                page.wait_for_selector("section#shareholding", timeout=10000)
            except PWTimeout:
                continue

            # Screener expands pledge sub-row via clicking the row's toggle button
            # The expand button is inside the Promoters row — it's an anchor with class "button-plain"
            # Try multiple selector strategies
            expanded = False
            for selector in [
                "section#shareholding table tr:has-text('Promoters') a.button-plain",
                "section#shareholding table tr:has-text('Promoters') button",
                "section#shareholding table tr:has-text('Promoters') a",
            ]:
                try:
                    btn = page.locator(selector).first
                    if btn.count() > 0 and btn.is_visible():
                        btn.click()
                        page.wait_for_timeout(800)  # wait for sub-row animation
                        expanded = True
                        break
                except Exception:
                    continue

            # Also try clicking via JS as fallback
            if not expanded:
                try:
                    page.evaluate("""
                        const rows = document.querySelectorAll('#shareholding table tr');
                        for (const row of rows) {
                            if (row.textContent.includes('Promoters')) {
                                const btn = row.querySelector('a, button');
                                if (btn) { btn.click(); break; }
                            }
                        }
                    """)
                    page.wait_for_timeout(800)
                except Exception:
                    pass

            # Read ALL table rows now (including newly visible sub-rows)
            rows_data = page.evaluate("""
                () => {
                    const table = document.querySelector('#shareholding table');
                    if (!table) return [];
                    const rows = [];
                    for (const tr of table.querySelectorAll('tr')) {
                        const cells = [];
                        for (const td of tr.querySelectorAll('td, th')) {
                            cells.push(td.innerText.trim());
                        }
                        if (cells.length > 0) rows.push(cells);
                    }
                    return rows;
                }
            """)

            # Debug: print all rows for first symbol
            if not getattr(fetch_pledge_for_sym, "_debug_done", False):
                fetch_pledge_for_sym._debug_done = True
                print(f"\n  DEBUG {sym} shareholding rows ({url}):")
                for r in rows_data[:12]:
                    print(f"    {r}")

            # Find pledge row
            for cells in rows_data:
                lbl = cells[0].strip().rstrip("+").strip().lower() if cells else ""
                if "pledge" not in lbl:
                    continue

                # Collect numeric values
                nums = []
                for c in cells[1:]:
                    v = safe_float(c)
                    if v is not None:
                        nums.append(v)

                if not nums:
                    return 0.0

                # Second-to-last = latest quarter; last = QoQ change
                val = nums[-2] if len(nums) >= 2 else nums[0]
                if 0 <= val <= 100:
                    return val
                last = nums[-1]
                if 0 <= last <= 100:
                    return last
                return 0.0

            # No pledge row found = 0% pledge (clean promoters)
            return 0.0

        except PWTimeout:
            print(f"  TIMEOUT on {url}")
            continue
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

    return None  # All URLs failed


def main():
    syms = load_symbols()
    if not syms:
        print("No symbols found.")
        return

    # Load existing to preserve values for failed fetches
    existing = {}
    if Path(PLEDGE_FILE).exists():
        try:
            existing = json.loads(Path(PLEDGE_FILE).read_text())
            print(f"Existing: {len(existing)} pledge values loaded")
        except Exception:
            pass

    result  = dict(existing)
    success = 0
    failed  = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        page = context.new_page()

        # Block images/fonts to speed up loads
        page.route("**/*.{png,jpg,jpeg,gif,webp,woff,woff2,ttf,eot,svg,ico}",
                   lambda r: r.abort())

        for i, sym in enumerate(syms):
            print(f"[{i+1}/{len(syms)}] {sym}", end=" ... ", flush=True)
            pledge = fetch_pledge_for_sym(page, sym)

            if pledge is not None:
                result[sym] = pledge
                success += 1
                print(f"pledge={pledge}%")
            else:
                failed.append(sym)
                print("FAILED (kept existing)" if sym in existing else "FAILED")

            time.sleep(DELAY)

        page.close()
        context.close()
        browser.close()

    Path(PLEDGE_FILE).write_text(
        json.dumps(result, indent=2, sort_keys=True)
    )

    print("\n" + "=" * 50)
    print(f"Done: {success}/{len(syms)} fetched | {len(failed)} failed")
    if failed:
        print(f"Failed symbols: {failed}")
    print(f"pledge.json: {len(result)} entries written")


if __name__ == "__main__":
    main()
