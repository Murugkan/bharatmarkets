#!/usr/bin/env python3
"""
BharatMarkets Pro - Pledge% Fetcher
=====================================
Uses Playwright headless browser to render Screener.in JS-rendered pages
and extract promoter pledge% for each portfolio stock.

Screener renders pledge sub-rows only after JS execution — requests/BS4 cannot see them.
Playwright runs a real Chromium browser, so it sees the fully rendered DOM.

Reads:  portfolio_symbols.txt
Writes: pledge.json  { "PVRINOX": 10.89, "ABFRL": 0.0, ... }

Run:    python fetch_pledge.py
Install: pip install playwright && playwright install chromium
"""

import json, time, re, sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    raise SystemExit("pip install playwright && playwright install chromium")

PORTFOLIO_FILE = "portfolio_symbols.txt"
PLEDGE_FILE    = "pledge.json"
DELAY          = 1.5   # seconds between page loads (be polite to Screener)

SKIP = {"NIFTY","BANKNIFTY","NIFTY50","SENSEX","NIFTYIT","MIDCAP","SMALLCAP","NIFTYBANK"}


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
        return float(str(s).replace("%","").replace(",","").strip())
    except Exception:
        return None


def fetch_pledge_screener(page, sym):
    """
    Load Screener.in page for sym, wait for JS to render shareholding section,
    then extract the Pledged row value.
    Returns float pledge% or None.
    """
    # Try consolidated first, fall back to standalone
    for url in [
        f"https://www.screener.in/company/{sym}/consolidated/",
        f"https://www.screener.in/company/{sym}/",
    ]:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)

            # Wait for shareholding section to be present
            try:
                page.wait_for_selector("section#shareholding table", timeout=8000)
            except PWTimeout:
                continue

            # Click the "+" expand button on Promoters row to reveal Pledged sub-row
            # Screener uses a button/link with "+" to expand promoter details
            try:
                expand_btn = page.locator("section#shareholding table tr").filter(
                    has_text="Promoters"
                ).locator("a, button").first
                if expand_btn.count() > 0:
                    expand_btn.click()
                    time.sleep(0.5)   # wait for sub-row to render
            except Exception:
                pass

            # Now read all rows in shareholding table
            rows = page.locator("section#shareholding table tr").all()
            for row in rows:
                cells = row.locator("td, th").all_text_contents()
                if not cells:
                    continue
                lbl = cells[0].strip().rstrip("+").strip().lower()
                if "pledge" not in lbl:
                    continue

                # Found pledge row — get latest quarter value
                # Columns: Label | Q(old) ... Q(latest) | Change
                nums = []
                for c in cells[1:]:
                    v = safe_float(c)
                    if v is not None:
                        nums.append(v)

                if not nums:
                    return 0.0   # pledge row exists but all zeros

                # Second-to-last = latest quarter (last = change col)
                val = nums[-2] if len(nums) >= 2 else nums[0]
                if 0 <= val <= 100:
                    return val
                # Try last as fallback
                if len(nums) >= 1 and 0 <= nums[-1] <= 100:
                    return nums[-1]
                return 0.0

            # Pledge row not found after expansion = 0% pledge
            return 0.0

        except PWTimeout:
            print(f"  TIMEOUT {sym} on {url}")
            continue
        except Exception as e:
            print(f"  ERROR {sym}: {e}")
            continue

    return None   # Could not load page


def main():
    syms = load_symbols()
    if not syms:
        print("No symbols found. Exiting.")
        return

    # Load existing pledge data to preserve values for symbols we fail to fetch
    existing = {}
    if Path(PLEDGE_FILE).exists():
        try:
            existing = json.loads(Path(PLEDGE_FILE).read_text())
            print(f"Loaded {len(existing)} existing pledge values")
        except Exception:
            pass

    result = dict(existing)   # start with existing, overwrite with fresh data
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
            ]
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-IN",
        )
        page = context.new_page()

        # Block images/fonts/media to speed up page loads
        page.route("**/*.{png,jpg,jpeg,gif,webp,woff,woff2,ttf,svg}", lambda r: r.abort())
        page.route("**/{ads,analytics,tracking}**", lambda r: r.abort())

        for i, sym in enumerate(syms):
            print(f"[{i+1}/{len(syms)}] {sym}", end=" ... ", flush=True)
            pledge = fetch_pledge_screener(page, sym)

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

    # Write pledge.json
    Path(PLEDGE_FILE).write_text(
        json.dumps(result, indent=2, sort_keys=True)
    )

    print("\n" + "=" * 50)
    print(f"Done: {success}/{len(syms)} fetched | {len(failed)} failed")
    if failed:
        print(f"Failed: {failed}")
    print(f"pledge.json written ({len(result)} entries)")


if __name__ == "__main__":
    main()
