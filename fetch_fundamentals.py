#!/usr/bin/env python3
"""
BharatMarkets Pro — Fundamentals Fetcher v2
============================================
Sources (priority order):
  1. Yahoo Finance (yfinance) — P/E, P/B, ROE, EPS, MCAP, margins, debt, ATH
  2. NSE India API            — promoter%, pledging%, FII%, DII%
  3. Screener.in              — fills any remaining gaps

Writes: fundamentals.json
"""

import json, time, datetime, re, os
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("pip install yfinance")

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    print("pip install requests beautifulsoup4 lxml")

WATCHLIST_FILE = "watchlist.txt"
PRICES_FILE    = "prices.json"
FUND_FILE      = "fundamentals.json"
YF_DELAY       = 0.6
SCR_DELAY      = 2.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}

def safe_float(v, default=None):
    if v is None: return default
    try:
        f = float(str(v).replace(',','').replace('%','').strip())
        return None if (f != f or abs(f) == float('inf')) else f
    except:
        return default

def load_symbols():
    if not Path(WATCHLIST_FILE).exists():
        return ["RELIANCE","TCS","HDFCBANK","INFY","SBIN"]
    skip = {"NIFTY","BANKNIFTY","NIFTY50","SENSEX","NIFTYIT","MIDCAP","SMALLCAP"}
    syms = [l.strip().upper() for l in open(WATCHLIST_FILE)
            if l.strip() and not l.startswith("#") and l.strip().upper() not in skip]
    print(f"Loaded {len(syms)} symbols")
    return syms

def fetch_yfinance(sym):
    result = {}
    try:
        t    = yf.Ticker(sym + ".NS")
        info = t.info or {}
        ltp  = safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
        prev = safe_float(info.get("previousClose"))
        if not ltp:
            return result

        result.update({
            "ltp":       ltp,
            "prev":      prev,
            "chg1d":     round((ltp-prev)/prev*100,2) if prev else 0,
            "w52h":      safe_float(info.get("fiftyTwoWeekHigh")),
            "w52l":      safe_float(info.get("fiftyTwoWeekLow")),
            "pe":        safe_float(info.get("trailingPE")),
            "fwd_pe":    safe_float(info.get("forwardPE")),
            "pb":        safe_float(info.get("priceToBook")),
            "eps":       safe_float(info.get("trailingEps")),
            "bv":        safe_float(info.get("bookValue")),
            "roe":       round(safe_float(info.get("returnOnEquity"),0)*100,2),
            "roa":       round(safe_float(info.get("returnOnAssets"),0)*100,2),
            "beta":      safe_float(info.get("beta")),
            "div_yield": round(safe_float(info.get("dividendYield"),0)*100,2),
            "name":      info.get("longName") or info.get("shortName") or sym,
            "sector":    info.get("sector") or info.get("industryDisp") or "",
            "industry":  info.get("industry") or "",
        })

        # Margins (fractions → %)
        for k, fk in [("npm_pct","profitMargins"),("opm_pct","operatingMargins"),("gpm_pct","grossMargins")]:
            v = safe_float(info.get(fk))
            result[k] = round(v*100,2) if v is not None else None

        # Financials in Cr
        for k, fk in [("sales","totalRevenue"),("ebitda","ebitda"),("cfo","operatingCashflow"),("fcf","freeCashflow")]:
            v = info.get(fk)
            result[k] = round(v/1e7,2) if v else None

        # Market cap in Cr
        mc = info.get("marketCap")
        result["mcap"] = round(mc/1e7,2) if mc else None

        # Debt/equity
        de = safe_float(info.get("debtToEquity"))
        result["debt_eq"] = round(de/100,2) if de else None

        # Current ratio
        result["cur_ratio"] = safe_float(info.get("currentRatio"))

        # 52W%
        if result.get("w52h") and ltp:
            result["w52_pct"] = round((ltp/result["w52h"]-1)*100,1)

        # ATH from 5Y monthly history
        try:
            h5 = t.history(period="5y", interval="1mo", auto_adjust=True)
            if not h5.empty:
                ath = float(h5["High"].max())
                result["ath"]     = round(ath,2)
                result["ath_pct"] = round((ltp/ath-1)*100,1) if ltp else None
        except:
            result["ath"]     = result.get("w52h")
            result["ath_pct"] = result.get("w52_pct")

        # 5D return
        try:
            h7 = t.history(period="7d", interval="1d", auto_adjust=True)
            closes = h7["Close"].dropna().values
            if len(closes) >= 5:
                result["chg5d"] = round((closes[-1]-closes[-5])/closes[-5]*100,2)
        except:
            pass

        # Promoter from insider holdings
        insider = safe_float(info.get("heldPercentInsiders"))
        if insider: result["prom_pct"] = round(insider*100,2)

        print(f"  ✓ yfinance {sym}: ₹{ltp} P/E:{result.get('pe','—')} ROE:{result.get('roe','—')}% OPM:{result.get('opm_pct','—')}%")
    except Exception as e:
        print(f"  ✗ yfinance {sym}: {e}")
    return result

def fetch_nse_shareholding(sym):
    result = {}
    if not HAS_BS4: return result
    try:
        sess = requests.Session()
        sess.headers.update(HEADERS)
        sess.get("https://www.nseindia.com", timeout=10)
        time.sleep(0.5)
        today = datetime.date.today()
        fd    = (today-datetime.timedelta(days=120)).strftime("%d-%m-%Y")
        td    = today.strftime("%d-%m-%Y")
        url   = f"https://www.nseindia.com/api/corporate-shareholding-pattern?symbol={sym}&from={fd}&to={td}"
        r     = sess.get(url, timeout=12)
        if r.status_code != 200: return result
        data  = r.json()
        if not data: return result
        latest = data[0] if isinstance(data, list) else data
        key_map = {
            "prom_pct":   ["promoterAndPromoterGroupShareholding","promoterHolding","promoterAndPromoterGroup"],
            "public_pct": ["publicShareholding","publicHolding"],
            "fii_pct":    ["foreignPortfolioInvestors","fii"],
            "dii_pct":    ["domesticInstitutionalInvestors","dii"],
            "pledge_pct": ["promoterAndPromoterGroupPledgedSharesPercentage","pledgedShares","pledge"],
        }
        for field, keys in key_map.items():
            for k in keys:
                v = safe_float(latest.get(k))
                if v is not None:
                    result[field] = round(v*100,2) if 0 < v < 1 else v
                    break
        if result:
            print(f"  ✓ NSE sharehld {sym}: Prom:{result.get('prom_pct','—')}% Pledge:{result.get('pledge_pct','—')}%")
    except Exception as e:
        print(f"  ⚠ NSE {sym}: {e}")
    return result

def fetch_screener_gaps(sym, missing_fields):
    """Only call Screener.in if key fields are missing after yfinance + NSE."""
    result = {}
    if not HAS_BS4 or not missing_fields: return result
    try:
        sess = requests.Session()
        sess.headers.update(HEADERS)
        for url in [f"https://www.screener.in/company/{sym}/consolidated/",
                    f"https://www.screener.in/company/{sym}/"]:
            r = sess.get(url, timeout=15)
            if r.status_code == 200: break
        else: return result

        soup = BeautifulSoup(r.text, "html.parser")

        # Top ratios
        ul = soup.find("ul", id="top-ratios") or soup.find("ul", class_=re.compile("top-ratios"))
        if ul:
            for li in ul.find_all("li"):
                spans = li.find_all("span")
                if len(spans) < 2: continue
                lbl = spans[0].get_text(strip=True).lower()
                val = safe_float(spans[-1].get_text(strip=True).replace(",","").replace("₹","").replace("%",""))
                if val is None: continue
                if "roce" in lbl: result.setdefault("roce", val)
                elif "p/e" in lbl: result.setdefault("pe", val)
                elif "p/b" in lbl: result.setdefault("pb", val)
                elif "roe" in lbl: result.setdefault("roe", val)

        # Shareholding for promoter/pledge
        sh = soup.find("section", id="shareholding")
        if sh:
            tbl = sh.find("table")
            if tbl:
                for row in tbl.find_all("tr"):
                    cells = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
                    if len(cells) < 2: continue
                    lbl = cells[0].lower()
                    val = safe_float(cells[-1].replace("%","").replace(",",""))
                    if val is None: continue
                    if "promoter" in lbl and "pledge" not in lbl: result.setdefault("prom_pct", val)
                    elif "pledge" in lbl: result.setdefault("pledge_pct", val)
                    elif "public" in lbl: result.setdefault("public_pct", val)

        # P&L for OPM%, NPM%, sales
        pl = soup.find("section", id="profit-loss")
        if pl:
            for row in (pl.find("table") or {}).find_all("tr") if pl.find("table") else []:
                cells = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
                if len(cells) < 2: continue
                lbl = cells[0].lower()
                val = safe_float(cells[-1].replace("%","").replace(",",""))
                if val is None: continue
                if "opm" in lbl: result.setdefault("opm_pct", val)
                elif "npm" in lbl: result.setdefault("npm_pct", val)
                elif lbl.startswith("sales"): result.setdefault("sales", val)

        # Cash flow
        cf = soup.find("section", id="cash-flow")
        if cf:
            for row in (cf.find("table") or {}).find_all("tr") if cf.find("table") else []:
                cells = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
                if len(cells) < 2: continue
                if "operating" in cells[0].lower():
                    val = safe_float(cells[-1].replace(",",""))
                    if val: result.setdefault("cfo", val)

        if result:
            print(f"  ✓ Screener {sym}: {len(result)} gap fields filled")
    except Exception as e:
        print(f"  ⚠ Screener {sym}: {e}")
    return result

def compute_signal(d):
    pos, neg = 0, 0
    checks = [
        ("roe",      lambda v: (pos:=pos+1) if v>15 else (neg:=neg+1) if v<8 else None),
        ("pe",       lambda v: (pos:=pos+1) if 0<v<18 else (neg:=neg+1) if v>35 else None),
        ("opm_pct",  lambda v: (pos:=pos+1) if v>15 else (neg:=neg+1) if 0<v<8 else None),
        ("npm_pct",  lambda v: (pos:=pos+1) if v>10 else (neg:=neg+1) if 0<v<5 else None),
        ("prom_pct", lambda v: (pos:=pos+1) if v>50 else (neg:=neg+1) if 0<v<35 else None),
        ("pledge_pct",lambda v:(pos:=pos+1) if v<5 else (neg:=neg+1) if v>20 else None),
        ("chg1d",    lambda v: (pos:=pos+1) if v>1 else (neg:=neg+1) if v<-1 else None),
        ("ath_pct",  lambda v: (pos:=pos+1) if v>-10 else (neg:=neg+1) if v<-20 else None),
        ("debt_eq",  lambda v: (pos:=pos+1) if v<0.5 else (neg:=neg+1) if v>1.5 else None),
    ]
    for field, fn in checks:
        v = d.get(field)
        if v is not None and v != 0:
            try: fn(v)
            except: pass
    net = pos - neg
    return ("BUY" if net>=3 else "SELL" if net<=-3 else "HOLD"), pos, neg

def main():
    syms = load_symbols()
    now  = datetime.datetime.utcnow()
    print(f"\n📊 BharatMarkets Fundamentals v2 | {now.strftime('%Y-%m-%d %H:%M UTC')}\n")

    existing = {}
    if Path(FUND_FILE).exists():
        try:
            existing = json.loads(Path(FUND_FILE).read_text()).get("stocks", {})
            print(f"♻  {len(existing)} existing records\n")
        except: pass

    prices = {}
    if Path(PRICES_FILE).exists():
        try:
            prices = json.loads(Path(PRICES_FILE).read_text()).get("quotes", {})
        except: pass

    result = {}
    stats  = {"yf":0,"nse":0,"scr":0,"errors":0}

    for i, sym in enumerate(syms):
        print(f"[{i+1}/{len(syms)}] {sym}")
        stock = {}

        # 1. Yahoo Finance
        yf_data = fetch_yfinance(sym)
        if yf_data: stock.update(yf_data); stats["yf"] += 1
        time.sleep(YF_DELAY)

        # 2. NSE shareholding (override promoter/pledge with official data)
        nse_data = fetch_nse_shareholding(sym)
        if nse_data:
            for k in ["prom_pct","public_pct","fii_pct","dii_pct","pledge_pct"]:
                if nse_data.get(k) is not None: stock[k] = nse_data[k]
            stats["nse"] += 1
        time.sleep(0.3)

        # 3. Screener.in — only for missing fields
        missing = [f for f in ["prom_pct","pledge_pct","opm_pct","cfo","roce"] if stock.get(f) is None]
        if missing:
            scr_data = fetch_screener_gaps(sym, missing)
            if scr_data:
                for k,v in scr_data.items():
                    if stock.get(k) is None: stock[k] = v
                stats["scr"] += 1
            time.sleep(SCR_DELAY)

        # 4. prices.json fallback
        pq = prices.get(sym, {})
        for src_k, dst_k in [("pe","pe"),("pb","pb"),("roe","roe"),("eps","eps"),
                               ("w52h","w52h"),("w52l","w52l"),("promoter","prom_pct"),
                               ("pledging","pledge_pct"),("beta","beta"),("mktCap","mcap_raw")]:
            if stock.get(dst_k) is None and pq.get(src_k):
                v = pq[src_k]
                stock[dst_k] = round(v/1e7,2) if src_k=="mktCap" else v

        # 5. Merge with existing
        merged = {**existing.get(sym,{})}
        for k,v in stock.items():
            if v is not None and v != "" and v != 0:
                merged[k] = v

        # 6. Signal
        sig, pos, neg = compute_signal(merged)
        merged.update({"signal":sig,"pos":pos,"neg":neg,"updated":now.isoformat()+"Z"})
        result[sym] = merged

        fields = sum(1 for v in merged.values() if v not in (None,"",0))
        print(f"  → {sig} ({pos}B/{neg}S) | {fields} fields\n")

    output = {
        "updated": now.isoformat()+"Z",
        "count":   len(result),
        "sources": stats,
        "stocks":  result,
    }
    Path(FUND_FILE).write_text(json.dumps(output, separators=(",",":"), default=str))

    print(f"{'='*48}")
    print(f"✅ {len(result)} stocks | yf:{stats['yf']} nse:{stats['nse']} scr:{stats['scr']}")
    print(f"🕐 {datetime.datetime.utcnow().strftime('%H:%M UTC')}\n")

if __name__ == "__main__":
    main()
