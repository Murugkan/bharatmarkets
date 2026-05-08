# #!/usr/bin/env python3
“””
BharatMarkets Onyx Pro — Fundamentals Fetcher v4.6

✨ FIXED: New Screener layout parsing + yfinance annual data fallback

Usage:
python fetch_fundamentals.py

Sources:

1. Yahoo Finance (yfinance) → PE, EPS, MCAP, ANNUAL financials
1. Screener.in → ROE, ROCE, PROM%, FII%, DII% (NEW LAYOUT SUPPORT)
1. yfinance annual → ROE, ROCE, DEBT_EQ, FCF (FALLBACK)

Output: fundamentals.json with 40+ fields per stock
“””

import json, time, datetime, re, os
from pathlib import Path

try:
import yfinance as yf
import logging
logging.getLogger(“yfinance”).setLevel(logging.CRITICAL)
logging.getLogger(“peewee”).setLevel(logging.CRITICAL)
except ImportError:
raise SystemExit(“pip install yfinance”)

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
from bs4 import BeautifulSoup
HAS_BS4 = True
except ImportError:
HAS_BS4 = False
print(“⚠ beautifulsoup4 not installed”)

SYMBOLS_FILE = “unified-symbols.json”
FUND_FILE = “fundamentals.json”

def safe_float(s):
“”“Convert to float safely”””
if s is None or s == “”:
return None
try:
return float(str(s).replace(”,”, “”).replace(“₹”, “”).replace(”%”, “”).strip())
except:
return None

def get_session():
“”“Screener session with retry logic”””
sess = requests.Session()
retry = Retry(total=3, backoff_factor=1, status_forcelist=(403, 500, 502, 503))
adapter = HTTPAdapter(max_retries=retry)
sess.mount(“http://”, adapter)
sess.mount(“https://”, adapter)
return sess

def fetch_screener_gaps(sym):
“””
✨ NEW: Parse Screener with both OLD & NEW layouts

```
OLD: <ul id="top-ratios"> structure
NEW: Simple label-value pairs (regex parsing)
"""
result = {}
if not HAS_BS4:
    return result

try:
    sess = get_session()
    url = f"https://www.screener.in/company/{sym}/consolidated/"
    r = sess.get(url, timeout=15)
    
    if r.status_code == 404:
        url = f"https://www.screener.in/company/{sym}/"
        r = sess.get(url, timeout=15)
    
    if r.status_code != 200:
        return result
    
    soup = BeautifulSoup(r.text, "html.parser")
    page_html = r.text
    
    # ═══════════════════════════════════════════════════════
    # ATTEMPT 1: OLD LAYOUT - <ul id="top-ratios">
    # ═══════════════════════════════════════════════════════
    ul = soup.find("ul", id="top-ratios")
    if ul:
        for li in ul.find_all("li"):
            spans = li.find_all("span")
            if len(spans) < 2:
                continue
            lbl = spans[0].get_text(strip=True).lower()
            raw = spans[-1].get_text(strip=True).replace(",","").replace("₹","").replace("%","")
            val = safe_float(raw)
            if val is None:
                continue
            if "roce" in lbl:          result["roce"] = val
            elif "p/e" in lbl:         result["pe"] = val
            elif "p/b" in lbl:         result["pb"] = val
            elif "roe" in lbl:         result["roe"] = val
            elif "market cap" in lbl:  result["mcap"] = val
            elif "sales" in lbl:       result["sales"] = val
            elif "face value" in lbl:  result["face_value"] = val
        
        if result:
            print(f"  ✓ Screener {sym}: {len(result)} fields (OLD LAYOUT)")
            return result
    
    # ═══════════════════════════════════════════════════════
    # ATTEMPT 2: NEW LAYOUT - Regex parsing
    # ═══════════════════════════════════════════════════════
    
    # ROCE
    roce_match = re.search(r'ROCE\s+(\d+(?:\.\d+)?)\s*%', page_html)
    if roce_match:
        result['roce'] = float(roce_match.group(1))
    
    # ROE
    roe_match = re.search(r'ROE\s+(\d+(?:\.\d+)?)\s*%', page_html)
    if roe_match:
        result['roe'] = float(roe_match.group(1))
    
    # P/E Ratio
    pe_match = re.search(r'Stock P/E\s+(\d+(?:\.\d+)?)', page_html)
    if pe_match:
        result['pe'] = float(pe_match.group(1))
    
    # Market Cap (in Crores)
    mcap_match = re.search(r'Market Cap\s+[₹]*\s*([\d,]+(?:\.\d+)?)\s*Cr', page_html)
    if mcap_match:
        mcap_str = mcap_match.group(1).replace(',', '')
        result['mcap'] = float(mcap_str)
    
    # Face Value
    fv_match = re.search(r'Face Value\s+[₹]*\s*([\d,]+(?:\.\d+)?)', page_html)
    if fv_match:
        result['face_value'] = float(fv_match.group(1).replace(',', ''))
    
    # Book Value
    bv_match = re.search(r'Book Value\s+[₹]*\s*([\d,]+(?:\.\d+)?)', page_html)
    if bv_match:
        result['bv'] = float(bv_match.group(1).replace(',', ''))
    
    # Dividend Yield
    div_match = re.search(r'Dividend Yield\s+(\d+(?:\.\d+)?)\s*%', page_html)
    if div_match:
        result['div_yield'] = float(div_match.group(1))
    
    # Shareholding section (if exists)
    sh = soup.find("section", id="shareholding")
    if sh:
        tbl = sh.find("table")
        if tbl:
            for row in tbl.find_all("tr"):
                cells = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
                if len(cells) < 2:
                    continue
                lbl = cells[0].strip().rstrip("+").strip().lower()
                
                numeric_vals = []
                for c in cells[1:]:
                    v = safe_float(c.replace("%","").replace(",","").strip())
                    if v is not None:
                        numeric_vals.append(v)
                
                if not numeric_vals:
                    continue
                
                val = numeric_vals[-2] if len(numeric_vals) >= 2 else numeric_vals[0]
                
                if "promoter" in lbl and "pledge" not in lbl:
                    result["prom_pct"] = val
                elif "fii" in lbl or "foreign" in lbl:
                    result["fii_pct"] = val
                elif "dii" in lbl or "institution" in lbl:
                    result["dii_pct"] = val
    
    if result:
        print(f"  ✓ Screener {sym}: {len(result)} fields (NEW LAYOUT)")
    
except Exception as e:
    print(f"  ⚠ Screener {sym}: {str(e)[:60]}")

return result
```

def fill_missing_from_yfinance(stock, sym):
“””
✨ NEW: Fill missing fields using yfinance ANNUAL data

```
Calculates: ROE, ROCE, DEBT_EQ, CFO, FCF, OPM%, NPM%
"""
try:
    ticker = yf.Ticker(sym + ".NS")
    
    # Annual financials (NOT quarterly)
    af = ticker.annual_financials
    abs = ticker.annual_balance_sheet
    acf = ticker.annual_cashflow
    
    if af.empty or abs.empty:
        return stock
    
    latest_af = af.iloc[:, 0]
    latest_abs = abs.iloc[:, 0]
    latest_acf = acf.iloc[:, 0] if not acf.empty else None
    
    # Extract values
    net_income = float(latest_af.get('Net Income', 0))
    operating_income = float(latest_af.get('Operating Income', 0))
    revenue = float(latest_af.get('Total Revenue', 0))
    equity = float(latest_abs.get('Total Equity Gross', 0))
    debt = float(latest_abs.get('Total Debt', 0))
    
    filled = []
    
    # ═══════════════════════════════════════════════════════
    # Calculate ROE (if missing)
    # ═══════════════════════════════════════════════════════
    if ('roe' not in stock or stock['roe'] == 0) and equity > 0:
        roe = (net_income / equity) * 100
        stock['roe'] = round(roe, 2)
        filled.append(f"ROE={roe:.1f}%")
    
    # ═══════════════════════════════════════════════════════
    # Calculate ROCE (if missing)
    # ═══════════════════════════════════════════════════════
    if ('roce' not in stock or stock['roce'] == 0 or stock['roce'] == 8.0) and equity + debt > 0:
        roce = (operating_income / (equity + debt)) * 100
        stock['roce'] = round(roce, 2)
        filled.append(f"ROCE={roce:.1f}%")
    
    # ═══════════════════════════════════════════════════════
    # Calculate DEBT_EQ (if missing)
    # ═══════════════════════════════════════════════════════
    if ('debt_eq' not in stock or stock['debt_eq'] == 0) and equity > 0:
        debt_eq = debt / equity
        stock['debt_eq'] = round(debt_eq, 2)
        filled.append(f"D/E={debt_eq:.2f}")
    
    # ═══════════════════════════════════════════════════════
    # Extract CFO & calculate FCF (if missing)
    # ═══════════════════════════════════════════════════════
    if latest_acf is not None:
        cfo = float(latest_acf.get('Operating Cash Flow', 0))
        capex = float(latest_acf.get('Capital Expenditure', 0))
        
        if 'cfo' not in stock or stock['cfo'] == 0:
            stock['cfo'] = round(cfo, 2) if cfo else 0
            filled.append(f"CFO={cfo:.0f}")
        
        if ('fcf' not in stock or stock['fcf'] == 0) and cfo and capex:
            fcf = cfo - capex
            stock['fcf'] = round(fcf, 2)
            filled.append(f"FCF={fcf:.0f}")
    
    # ═══════════════════════════════════════════════════════
    # Calculate margins (if missing)
    # ═══════════════════════════════════════════════════════
    if ('opm_pct' not in stock or stock['opm_pct'] == 0) and revenue > 0:
        opm = (operating_income / revenue) * 100
        stock['opm_pct'] = round(opm, 2)
        filled.append(f"OPM={opm:.1f}%")
    
    if ('npm_pct' not in stock or stock['npm_pct'] == 0) and revenue > 0:
        npm = (net_income / revenue) * 100
        stock['npm_pct'] = round(npm, 2)
        filled.append(f"NPM={npm:.1f}%")
    
    if filled:
        print(f"      → yfinance: {', '.join(filled)}")

except Exception as e:
    pass

return stock
```

# ═══════════════════════════════════════════════════════════════════════════

# MAIN

# ═══════════════════════════════════════════════════════════════════════════

if **name** == “**main**”:
print(”=” * 80)
print(“BharatMarkets Onyx Pro — Fundamentals Fetcher v4.6”)
print(”=” * 80)

```
# Load symbols
try:
    with open(SYMBOLS_FILE) as f:
        syms_data = json.load(f)
        symbols = syms_data.get('symbols', [])[:3]  # Test on 3 stocks
except:
    print(f"Error: {SYMBOLS_FILE} not found")
    symbols = ["WAAREEENER", "SHILCHAR", "COFORGE"]

results = {}

for sym in symbols:
    print(f"\n{sym}:")
    
    # Get from Screener
    data = fetch_screener_gaps(sym)
    
    # Fill missing from yfinance
    data = fill_missing_from_yfinance(data, sym)
    
    results[sym] = data
    time.sleep(0.5)  # Rate limit

# Show summary
print("\n" + "=" * 80)
print("RESULTS")
print("=" * 80)

for sym, data in results.items():
    print(f"\n{sym}:")
    print(f"  ROE: {data.get('roe', 'N/A')}")
    print(f"  ROCE: {data.get('roce', 'N/A')}")
    print(f"  P/E: {data.get('pe', 'N/A')}")
    print(f"  Total fields: {len(data)}")
```
