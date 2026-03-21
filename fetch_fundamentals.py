#!/usr/bin/env python3
"""
BharatMarkets Pro — Fundamentals Fetcher
Sources:
  1. Screener.in  → OPM%, NPM%, Sales, CFO, EPS, Promoter%, Pledge%, ROE, P/E, P/B, MCAP
  2. NSE India    → ATH (All-Time High), 52W High/Low, Current Price
  3. Yahoo Finance → fallback for price data

Writes: fundamentals.json (read by the app for the 37-column screener)

Run schedule: Daily at 18:00 IST (after market close)
Also runs on workflow_dispatch (manual trigger)
"""

import json, time, datetime, re, os
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    raise SystemExit("pip install requests beautifulsoup4 lxml")

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False
    print("⚠  yfinance not installed — price fallback disabled")

# ── Config ────────────────────────────────────────────
WATCHLIST_FILE   = "watchlist.txt"
PRICES_FILE      = "prices.json"
FUND_FILE        = "fundamentals.json"
REQUEST_DELAY    = 1.2   # seconds between Screener.in requests (polite)
MAX_RETRIES      = 2

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

session = requests.Session()
session.headers.update(HEADERS)

# ── Load watchlist ────────────────────────────────────
def load_symbols():
    if not Path(WATCHLIST_FILE).exists():
        return ["RELIANCE","TCS","HDFCBANK","INFY","SBIN"]
    syms = []
    with open(WATCHLIST_FILE) as f:
        for line in f:
            s = line.strip().upper()
            if s and not s.startswith("#") and s not in ("NIFTY","BANKNIFTY","NIFTY50","SENSEX"):
                syms.append(s)
    print(f"📋 {len(syms)} symbols from {WATCHLIST_FILE}")
    return syms

# ── NSE ATH + 52W data ────────────────────────────────
def fetch_nse_data(sym):
    """
    NSE provides 52W high/low and price via official API.
    ATH is derived from the all-time max from historical data (yfinance).
    """
    result = {}
    nse_sym = sym.replace("&", "%26")

    # NSE quote API (official, public, no auth)
    try:
        url = f"https://www.nseindia.com/api/quote-equity?symbol={nse_sym}"
        r = session.get(url, timeout=10)
        if r.status_code == 200:
            d = r.json()
            pd = d.get("priceInfo", {})
            result["ltp"]   = pd.get("lastPrice", 0)
            result["open"]  = pd.get("open", 0)
            result["high"]  = pd.get("intraDayHighLow", {}).get("max", 0)
            result["low"]   = pd.get("intraDayHighLow", {}).get("min", 0)
            result["prev"]  = pd.get("previousClose", 0)
            result["chg1d"] = pd.get("pChange", 0)
            w52 = d.get("priceInfo", {}).get("weekHighLow", {})
            result["w52h"]  = w52.get("max", 0)
            result["w52l"]  = w52.get("min", 0)
            if result["w52h"] and result["ltp"]:
                result["w52_pct"] = round((result["ltp"] / result["w52h"] - 1) * 100, 1)
            # Metadata
            meta = d.get("metadata", {})
            result["name"]   = meta.get("companyName", sym)
            result["isin"]   = meta.get("isin", "")
            result["sector"] = meta.get("industry", "")
    except Exception as e:
        print(f"  ⚠ NSE quote {sym}: {e}")

    # ATH via yfinance (max from 10Y history)
    if HAS_YF:
        try:
            t = yf.Ticker(sym + ".NS")
            hist = t.history(period="10y", interval="1mo", auto_adjust=True)
            if not hist.empty:
                ath = float(hist["High"].max())
                result["ath"] = round(ath, 2)
                ltp = result.get("ltp") or ath
                result["ath_pct"] = round((ltp / ath - 1) * 100, 1)
        except Exception as e:
            print(f"  ⚠ ATH {sym}: {e}")

    return result

# ── Screener.in scraper ───────────────────────────────
def fetch_screener(sym):
    """
    Scrapes Screener.in public stock page for fundamentals.
    No login required — public data.
    URL: https://www.screener.in/company/SYMBOL/consolidated/
    """
    result = {}
    url = f"https://www.screener.in/company/{sym}/consolidated/"
    fallback_url = f"https://www.screener.in/company/{sym}/"

    for attempt_url in [url, fallback_url]:
        try:
            r = session.get(attempt_url, timeout=15)
            if r.status_code == 404:
                continue
            if r.status_code != 200:
                print(f"  ⚠ Screener {sym}: HTTP {r.status_code}")
                continue

            soup = BeautifulSoup(r.text, "html.parser")

            # ── Company name ──
            h1 = soup.find("h1", class_=re.compile("company-name|h1"))
            if h1:
                result["name"] = h1.get_text(strip=True)

            # ── Key ratios (top number boxes) ──
            # Screener shows: Market Cap, Current Price, High/Low, P/E, Book Value,
            #                  Dividend Yield, ROCE, ROE, Face Value
            ratio_divs = soup.find_all("li", class_=re.compile("flex-column"))
            for div in ratio_divs:
                label_el = div.find("span", class_=re.compile("name|label"))
                value_el = div.find("span", class_=re.compile("number|value"))
                if not label_el or not value_el:
                    # try alternate structure
                    spans = div.find_all("span")
                    if len(spans) >= 2:
                        label_el = spans[0]
                        value_el = spans[-1]
                if not label_el or not value_el:
                    continue
                lbl = label_el.get_text(strip=True).lower()
                val_txt = value_el.get_text(strip=True).replace(",", "").replace("₹", "").replace("%", "").strip()
                try:
                    val = float(val_txt)
                except:
                    val = None

                if "market cap" in lbl:        result["mcap"]    = val
                elif "p/e" in lbl or "price to earnings" in lbl: result["pe"] = val
                elif "book value" in lbl:      result["bv"]      = val
                elif "roce" in lbl:            result["roce"]    = val
                elif "roe" in lbl:             result["roe"]     = val
                elif "dividend yield" in lbl:  result["div_yield"]= val
                elif "eps" in lbl:             result["eps"]     = val
                elif "debt to equity" in lbl:  result["debt_eq"] = val
                elif "current ratio" in lbl:   result["cur_ratio"]= val

            # ── Shareholding pattern ──
            # Look for shareholding section
            sh_section = soup.find("section", id=re.compile("shareholding"))
            if not sh_section:
                sh_section = soup.find("div", class_=re.compile("shareholding"))
            if sh_section:
                rows = sh_section.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    if len(cells) >= 2:
                        lbl = cells[0].get_text(strip=True).lower()
                        # Last column = most recent quarter
                        val_txt = cells[-1].get_text(strip=True).replace("%","").replace(",","").strip()
                        try: val = float(val_txt)
                        except: val = None
                        if val is None: continue
                        if "promoter" in lbl:  result["prom_pct"]  = val
                        elif "fii" in lbl:     result["fii_pct"]   = val
                        elif "dii" in lbl:     result["dii_pct"]   = val
                        elif "public" in lbl:  result["public_pct"]= val

            # ── Pledging ──
            pledge_el = soup.find(string=re.compile(r"Pledge", re.I))
            if pledge_el:
                parent = pledge_el.find_parent()
                if parent:
                    nums = re.findall(r"[\d.]+", parent.get_text())
                    if nums:
                        try: result["pledge_pct"] = float(nums[-1])
                        except: pass

            # ── P&L data (quarterly/annual table) ──
            # Find the profit and loss section
            pl_section = soup.find("section", id=re.compile("profit-loss|income"))
            if not pl_section:
                pl_section = soup.find("h2", string=re.compile(r"Profit.+Loss|Income", re.I))
                if pl_section: pl_section = pl_section.find_parent("section")

            if pl_section:
                table = pl_section.find("table")
                if table:
                    rows = table.find_all("tr")
                    for row in rows:
                        cells = row.find_all(["td", "th"])
                        if len(cells) < 2: continue
                        lbl = cells[0].get_text(strip=True).lower()
                        # Most recent column (second to last — last is TTM or recent)
                        for cidx in [-1, -2]:
                            try:
                                val_txt = cells[cidx].get_text(strip=True).replace(",","").replace("₹","").strip()
                                val = float(val_txt)
                                break
                            except:
                                val = None

                        if val is None: continue
                        if lbl.startswith("sales") or "revenue" in lbl: result["sales"] = val
                        elif "operating profit" in lbl:                  result["ebitda"] = val
                        elif "opm" in lbl or "operating margin" in lbl:  result["opm_pct"]= val
                        elif "net profit" in lbl or "profit after" in lbl: result["pat"]  = val
                        elif "npm" in lbl or "net margin" in lbl:         result["npm_pct"]= val
                        elif "tax" in lbl and "%" not in lbl:             pass

            # ── Cash Flow ──
            cf_section = soup.find("section", id=re.compile("cash-flow"))
            if not cf_section:
                cf_section = soup.find("h2", string=re.compile(r"Cash Flow", re.I))
                if cf_section: cf_section = cf_section.find_parent("section")

            if cf_section:
                table = cf_section.find("table")
                if table:
                    rows = table.find_all("tr")
                    for row in rows:
                        cells = row.find_all(["td","th"])
                        if len(cells) < 2: continue
                        lbl = cells[0].get_text(strip=True).lower()
                        try:
                            val = float(cells[-1].get_text(strip=True).replace(",","").strip())
                        except:
                            val = None
                        if val is None: continue
                        if "operating" in lbl or "from operations" in lbl: result["cfo"] = val
                        elif "investing" in lbl:   result["cfi"] = val
                        elif "financing" in lbl:   result["cff"] = val
                        elif "net cash" in lbl:    result["net_cf"] = val

            # ── Compute derived fields ──
            # OPM% if not scraped directly
            if "opm_pct" not in result and "ebitda" in result and "sales" in result and result["sales"]>0:
                result["opm_pct"] = round(result["ebitda"] / result["sales"] * 100, 1)

            # NPM% if not scraped directly
            if "npm_pct" not in result and "pat" in result and "sales" in result and result["sales"]>0:
                result["npm_pct"] = round(result["pat"] / result["sales"] * 100, 1)

            # P/B from book value if not present
            if "pe" not in result or "roe" not in result:
                # Try alternate ratio table
                ratio_table = soup.find("table", class_=re.compile("data-table|ratios"))
                if ratio_table:
                    for tr in ratio_table.find_all("tr"):
                        tds = tr.find_all("td")
                        if len(tds) >= 2:
                            lbl = tds[0].get_text(strip=True).lower()
                            try: val = float(tds[-1].get_text(strip=True).replace(",","").replace("%",""))
                            except: val = None
                            if val is None: continue
                            if "roe" in lbl and "roe" not in result: result["roe"] = val
                            elif "roce" in lbl and "roce" not in result: result["roce"] = val

            if result:
                print(f"  ✓ Screener: {sym} — {len(result)} fields")
                return result

        except Exception as e:
            print(f"  ✗ Screener {sym}: {e}")
            time.sleep(1)

    return result

# ── Signal computation ────────────────────────────────
def compute_signal(data):
    """
    Composite BUY/SELL/HOLD signal from multiple factors.
    Returns: signal str, pos count, neg count
    """
    pos, neg = 0, 0

    roe      = data.get("roe", 0) or 0
    pe       = data.get("pe", 0) or 0
    opm      = data.get("opm_pct", 0) or 0
    npm      = data.get("npm_pct", 0) or 0
    prom     = data.get("prom_pct", 0) or 0
    pledge   = data.get("pledge_pct", 0) or 0
    chg1d    = data.get("chg1d", 0) or 0
    ath_pct  = data.get("ath_pct", -100) or -100
    w52_pct  = data.get("w52_pct", -100) or -100
    debt_eq  = data.get("debt_eq", 0) or 0

    if roe > 15:   pos += 1
    elif roe < 8:  neg += 1
    if pe > 0:
        if pe < 18: pos += 1
        elif pe > 35: neg += 1
    if opm > 15:   pos += 1
    elif opm < 8:  neg += 1
    if npm > 10:   pos += 1
    elif npm < 5:  neg += 1
    if prom > 50:  pos += 1
    elif prom < 35: neg += 1
    if pledge < 5: pos += 1
    elif pledge > 20: neg += 1
    if chg1d > 1:  pos += 1
    elif chg1d < -1: neg += 1
    if ath_pct > -10: pos += 1
    elif ath_pct < -20: neg += 1
    if debt_eq < 0.5: pos += 1
    elif debt_eq > 1.5: neg += 1

    net = pos - neg
    if net >= 3:   sig = "BUY"
    elif net <= -3: sig = "SELL"
    else:           sig = "HOLD"

    return sig, pos, neg

# ── 5D change via yfinance ────────────────────────────
def fetch_5d_change(sym):
    if not HAS_YF:
        return 0
    try:
        t = yf.Ticker(sym + ".NS")
        h = t.history(period="7d", interval="1d", auto_adjust=True)
        if len(h) >= 5:
            first = float(h["Close"].iloc[-5])
            last  = float(h["Close"].iloc[-1])
            if first > 0:
                return round((last - first) / first * 100, 2)
    except:
        pass
    return 0

# ── Main ──────────────────────────────────────────────
def main():
    syms = load_symbols()
    now  = datetime.datetime.utcnow()
    print(f"\n📊 BharatMarkets Fundamentals Fetch")
    print(f"🕐 {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"📋 {len(syms)} symbols\n")

    # Load existing data to merge (don't wipe good data)
    existing = {}
    if Path(FUND_FILE).exists():
        try:
            with open(FUND_FILE) as f:
                d = json.load(f)
                existing = d.get("stocks", {})
        except:
            pass

    # Load existing prices.json for fallback
    prices = {}
    if Path(PRICES_FILE).exists():
        try:
            with open(PRICES_FILE) as f:
                d = json.load(f)
                prices = d.get("quotes", d)
        except:
            pass

    result = {}
    errors = []

    for sym in syms:
        print(f"→ {sym}")
        stock = {}

        # 1. NSE data (ATH, 52W, price, sector)
        nse = fetch_nse_data(sym)
        stock.update(nse)
        time.sleep(0.3)

        # 2. Screener.in fundamentals
        scr = fetch_screener(sym)
        stock.update({k:v for k,v in scr.items() if v is not None})
        time.sleep(REQUEST_DELAY)

        # 3. 5D change
        stock["chg5d"] = fetch_5d_change(sym)

        # 4. Fallback from prices.json
        pq = prices.get(sym, {})
        if not stock.get("ltp") and pq.get("ltp"):
            stock["ltp"] = pq["ltp"]
        if not stock.get("pe") and pq.get("pe"):
            stock["pe"] = pq["pe"]
        if not stock.get("roe") and pq.get("roe"):
            stock["roe"] = pq["roe"]
        if not stock.get("eps") and pq.get("eps"):
            stock["eps"] = pq["eps"]
        if not stock.get("w52h") and pq.get("w52h"):
            stock["w52h"] = pq["w52h"]
        if not stock.get("w52l") and pq.get("w52l"):
            stock["w52l"] = pq["w52l"]
        if not stock.get("mcap") and pq.get("mktCap"):
            stock["mcap"] = round(pq["mktCap"] / 1e7, 2)  # convert to Cr
        if not stock.get("prom_pct") and pq.get("promoter"):
            stock["prom_pct"] = pq["promoter"]

        # 5. Compute signal
        sig, pos, neg = compute_signal(stock)
        stock["signal"] = sig
        stock["pos"]    = pos
        stock["neg"]    = neg

        # 6. Merge with existing (keep old values for missing new fields)
        old = existing.get(sym, {})
        merged = {**old, **{k:v for k,v in stock.items() if v is not None and v != 0}}
        result[sym] = merged

        ltp_str = f"₹{stock.get('ltp', 0):.1f}" if stock.get("ltp") else "no price"
        print(f"  ✓ {sig} ({pos}B/{neg}S) | {ltp_str} | ROE:{stock.get('roe','—')} PE:{stock.get('pe','—')} OPM:{stock.get('opm_pct','—')}")

        time.sleep(0.2)

    # Write output
    output = {
        "updated": now.isoformat() + "Z",
        "count":   len(result),
        "stocks":  result,
    }
    with open(FUND_FILE, "w") as f:
        json.dump(output, f, separators=(",",":"), default=str)

    print(f"\n✅ fundamentals.json → {len(result)} stocks")
    print(f"⚠  Errors: {errors}" if errors else "")
    print(f"🕐 Done {datetime.datetime.utcnow().strftime('%H:%M UTC')}\n")

if __name__ == "__main__":
    main()
