#!/usr/bin/env python3
"""
BharatMarkets Pro - Pledge% Fetcher v3
========================================
Uses Playwright to fetch NSE corporate filings pledge data.
NSE requires real browser session (cookies + JS) — Playwright handles this.

NSE endpoint: /api/corporates-pledgedata?index=equities&symbol=SYM
Returns JSON with latest promoter pledge data per company.

Reads:  portfolio_symbols.txt
Writes: pledge.json  { "PVRINOX": 10.89, "ABFRL": 0.0, ... }

Run:    python fetch_pledge.py
"""

import json, time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    raise SystemExit("pip install playwright && playwright install chromium")

PORTFOLIO_FILE = "portfolio_symbols.txt"
PLEDGE_FILE    = "pledge.json"
DELAY          = 1.0

SKIP = {"NIFTY","BANKNIFTY","NIFTY50","SENSEX","NIFTYIT","MIDCAP","SMALLCAP","NIFTYBANK"}

# Map CDSL symbols to correct NSE symbols for the API
NSE_SYM_MAP = {
    "AMARAJAB":      "ARE&M",
    "AMARAJABAT":    "ARE&M",
    "HBLPOWER":      "HBLENGINE",
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
    "MCDOWELL-N":    "MCDOWELL-N",
    "SSPOWERSWIT":   "S&SPOWER",
    "REVATHI":       "RVTH",
    "IGI":           "IGIL",
    "SUYOGTELE":     "SUYOG",
    "QUALPOWER":     "QPOWER",
    "CELLOWORLD":    "CELLO",
    # BSE-only — no NSE listing, skip gracefully
    "AZADINDIA":     None,
    "KWALITYPHARM":  None,
    "CAPITALNUMB":   None,
    "TITANBIOTE":    None,
    "HIGHENERGYB":   None,
    "SIKAINTERP":    None,
    "SHREEREFRI":    None,
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


def fetch_nse_pledge(page, sym):
    """
    Fetch pledge% from NSE corporate filings API using Playwright browser session.
    NSE requires cookies from homepage — Playwright maintains the session.
    Returns float pledge% or None if unavailable.
    """
    # Resolve NSE symbol
    nse_sym = NSE_SYM_MAP.get(sym, sym)
    if nse_sym is None:
        return None  # BSE-only stock, no NSE listing

    try:
        # Use Playwright to fetch the JSON API — browser session has NSE cookies
        url = f"https://www.nseindia.com/api/corporates-pledgedata?index=equities&symbol={nse_sym}"

        # Use page.evaluate to make a fetch() call from within the browser context
        # This uses the existing NSE session/cookies set up by the homepage visit
        result = page.evaluate(f"""
            async () => {{
                try {{
                    const r = await fetch('{url}', {{
                        headers: {{
                            'Accept': 'application/json, text/plain, */*',
                            'Referer': 'https://www.nseindia.com/',
                            'X-Requested-With': 'XMLHttpRequest'
                        }},
                        credentials: 'include'
                    }});
                    if (!r.ok) return {{ error: r.status }};
                    return await r.json();
                }} catch(e) {{
                    return {{ error: e.toString() }};
                }}
            }}
        """)

        if not result or isinstance(result, dict) and result.get("error"):
            err = result.get("error") if result else "empty"
            if sym == "PVRINOX":
                print(f"\n  DEBUG NSE API error for {sym}: {err}")
            return None

        # Debug first successful response
        if not getattr(fetch_nse_pledge, "_debug_done", False):
            fetch_nse_pledge._debug_done = True
            print(f"\n  DEBUG NSE pledge response for {sym}:")
            if isinstance(result, list) and result:
                print(f"    Keys: {list(result[0].keys())}")
                print(f"    First row: {result[0]}")
            elif isinstance(result, dict):
                print(f"    Keys: {list(result.keys())}")
                print(f"    Data: {str(result)[:300]}")

        # Parse response — NSE returns list of quarterly records
        rows = result if isinstance(result, list) else result.get("data", [])
        if not rows:
            return 0.0

        # Get latest record (first in list = most recent)
        latest = rows[0] if rows else {}

        # Try known field names for pledge%
        for field in [
            "pPledgePercentage", "pledgePercent", "promoterPledge",
            "percentPledged", "pctPledged", "pledgePct",
            "promoterAndPromoterGroupPledgedSharesPercentage",
            "percentageOfPromoterSharesPledged",
            "pPledge", "pledgedPct", "pledged_pct",
        ]:
            v = safe_float(latest.get(field))
            if v is not None:
                return round(v, 2) if v > 1 else round(v * 100, 2)

        # Debug if PVRINOX fields not matched
        if sym == "PVRINOX":
            print(f"\n  DEBUG PVRINOX latest record fields: {list(latest.keys())}")
            print(f"  DEBUG PVRINOX latest record: {latest}")

        return 0.0

    except Exception as e:
        print(f"  ERROR {sym}: {e}")
        return None


def main():
    syms = load_symbols()
    if not syms:
        print("No symbols found.")
        return

    existing = {}
    if Path(PLEDGE_FILE).exists():
        try:
            existing = json.loads(Path(PLEDGE_FILE).read_text())
            print(f"Existing: {len(existing)} pledge values")
        except Exception:
            pass

    result  = dict(existing)
    success = 0
    failed  = []
    bse_only = 0

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

        # Block images/media to speed up
        page.route("**/*.{png,jpg,jpeg,gif,webp,woff,woff2,ttf,svg,ico}",
                   lambda r: r.abort())

        # Visit NSE homepage to get session cookies — critical for API access
        print("Setting up NSE session...")
        page.goto("https://www.nseindia.com", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2000)
        print("NSE session ready.\n")

        for i, sym in enumerate(syms):
            # Check if BSE-only
            if NSE_SYM_MAP.get(sym) is None and sym in NSE_SYM_MAP:
                print(f"[{i+1}/{len(syms)}] {sym} ... BSE-only (skipped)")
                bse_only += 1
                continue

            print(f"[{i+1}/{len(syms)}] {sym}", end=" ... ", flush=True)
            pledge = fetch_nse_pledge(page, sym)

            if pledge is not None:
                result[sym] = pledge
                success += 1
                label = f"pledge={pledge}%" if pledge > 0 else "pledge=0.0% (clean)"
                print(label)
            else:
                failed.append(sym)
                print("FAILED")

            time.sleep(DELAY)

        page.close()
        context.close()
        browser.close()

    Path(PLEDGE_FILE).write_text(
        json.dumps(result, indent=2, sort_keys=True)
    )

    print("\n" + "=" * 50)
    print(f"Done: {success} fetched | {bse_only} BSE-only skipped | {len(failed)} failed")
    if failed:
        print(f"Failed: {failed}")
    print(f"pledge.json: {len(result)} entries")


if __name__ == "__main__":
    main()
