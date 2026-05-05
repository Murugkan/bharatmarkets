#!/usr/bin/env python3
"""
BharatMarkets Pro — Complete Fundamentals Fetcher
================================================
✨ ONE COMMAND: python3 fetch_fundamentals.py
✨ ALWAYS FRESH: Complete rebuild every run
✨ ALL PHASES: Yahoo → Calculate → Hunt Holdings
✨ ZERO COMPLEXITY: Just works
"""

import json, time, datetime, re, os
from pathlib import Path

try:
    import yfinance as yf
    import logging
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    logging.getLogger("peewee").setLevel(logging.CRITICAL)
except ImportError:
    raise SystemExit("pip install yfinance")

import requests
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

SYMBOLS_FILE = "unified-symbols.json"
FUND_FILE = "fundamentals.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}

SKIP = {"NIFTY","BANKNIFTY","NIFTY50","SENSEX","NIFTYIT","MIDCAP","SMALLCAP","NIFTYBANK"}
DELISTED = set()

try:
    _sm = json.loads(open("symbol_map.json").read())
    NSE_TO_YAHOO = {**_sm.get("overrides",{}), **_sm.get("indices",{})}
    SYMBOL_MAP_DELISTED = set(_sm.get("delisted", []))
except:
    NSE_TO_YAHOO = {}
    SYMBOL_MAP_DELISTED = set()

YF_ALIAS_CACHE = {}
CDSL_NAMES = {}
_SCR_SESSION = None
_MC_SESSION = None

def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)

def safe_float(v, default=None):
    if v is None: return default
    try:
        f = float(str(v).replace(',','').replace('%','').strip())
        if f != f or abs(f) == float('inf'): return default
        return f
    except:
        return default

def to_cr(v):
    return round(v / 1e7, 2) if v else None

def load_symbols():
    global CDSL_NAMES
    syms, seen = [], set()
    try:
        data = json.loads(Path(SYMBOLS_FILE).read_text())
        symbols_list = data.get("symbols", []) if isinstance(data, dict) else data
        for entry in symbols_list:
            ticker = entry.get("ticker", "").strip().upper() or entry.get("sym", "").strip().upper()
            name = entry.get("name", "")
            isin = entry.get("isin", "").strip().upper()
            if ticker and ticker not in SKIP and ticker not in SYMBOL_MAP_DELISTED and ticker not in seen and isin.startswith("INE"):
                syms.append(ticker)
                seen.add(ticker)
                if name: CDSL_NAMES[ticker] = name
        print(f"📋 {len(syms)} symbols loaded\n")
    except Exception as e:
        print(f"⚠ Error: {e}")
    return syms

def resolve_symbols():
    symbols = load_symbols()
    try:
        sm = json.loads(Path("symbol_map.json").read_text())
        overrides = sm.get("overrides", {})
    except:
        overrides = {}
    resolved = {}
    for sym in symbols:
        resolved[sym] = overrides.get(sym, sym + ".NS")
    return resolved

def calculate_metrics(stock, quarterly_list):
    """Phase 2: Calculate all derived metrics"""
    try:
        if quarterly_list and len(quarterly_list) >= 4:
            latest_4q = quarterly_list[-4:]
            ttm_ebit = sum(safe_float(q.get('ebit'), 0) for q in latest_4q)
            ttm_ocf = sum(safe_float(q.get('cfo'), 0) for q in latest_4q)
            ttm_net = sum(safe_float(q.get('net'), 0) for q in latest_4q)
            latest_debt = safe_float(latest_4q[-1].get('debt'), 0)
            
            if ttm_ebit > 0 and (latest_debt or safe_float(latest_4q[-1].get('equity'), 0)):
                invested = (safe_float(latest_4q[-1].get('equity'), 0) or 0) + (latest_debt or 0)
                if invested > 0:
                    nopat = ttm_ebit * 0.75
                    roic = (nopat / invested) * 100
                    if 0 < roic < 200:
                        stock['roic'] = round(roic, 2)
            
            if ttm_net and ttm_net > 0:
                cash_conv = (ttm_ocf / ttm_net) * 100
                if 0 < cash_conv < 500:
                    stock['cash_conv'] = round(cash_conv, 2)
    except:
        pass
    
    try:
        mcap = safe_float(stock.get('mcap'))
        ebitda = safe_float(stock.get('ebitda'))
        if mcap and ebitda and ebitda > 0:
            ev = mcap + safe_float(stock.get('total_debt'), 0) or mcap * 1.2
            ev_ebitda = ev / ebitda
            if 0 < ev_ebitda < 100:
                stock['ev_ebitda'] = round(ev_ebitda, 2)
    except:
        pass

def resolve_yf_sym(nse_sym):
    if nse_sym in YF_ALIAS_CACHE:
        v = YF_ALIAS_CACHE[nse_sym]
        return v if ("." in v or v.startswith("^")) else v + ".NS"
    if nse_sym in NSE_TO_YAHOO:
        v = NSE_TO_YAHOO[nse_sym]
        result = v if ("." in v or v.startswith("^")) else v + ".NS"
        YF_ALIAS_CACHE[nse_sym] = result
        return result
    return nse_sym + ".NS"

def yahoo_search_sym(nse_sym, cdsl_name=None):
    queries = [cdsl_name] if cdsl_name else [nse_sym]
    for q_str in queries:
        try:
            url = f"https://query2.finance.yahoo.com/v1/finance/search?q={requests.utils.quote(q_str)}&quotesCount=5"
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200: continue
            quotes = r.json().get("quotes", [])
            for q in quotes:
                sym_yf = q.get("symbol", "")
                if (sym_yf.endswith(".NS") or sym_yf.endswith(".BO")) and q.get("quoteType", "") in ("EQUITY", ""):
                    YF_ALIAS_CACHE[nse_sym] = sym_yf
                    return sym_yf
        except:
            pass
        time.sleep(0.2)
    return None

def fetch_yfinance(sym, yf_ticker=None):
    """Phase 1: Fetch from Yahoo Finance"""
    result = {}
    try:
        yf_sym = yf_ticker if yf_ticker else resolve_yf_sym(sym)
        t = yf.Ticker(yf_sym)
        
        try:
            hist = t.history(period="1mo", auto_adjust=True)
        except:
            hist = None

        if hist is None or hist.empty:
            found = yahoo_search_sym(sym, CDSL_NAMES.get(sym))
            if found:
                t = yf.Ticker(found)
                try:
                    hist = t.history(period="1mo", auto_adjust=True)
                except:
                    hist = None
        
        if hist is None or hist.empty:
            return result

        info = {}
        try:
            info = t.info or {}
        except:
            pass

        ltp = None
        try:
            fi = t.fast_info
            ltp = safe_float(getattr(fi, "last_price", None))
        except:
            pass
        if not ltp:
            ltp = safe_float(info.get("currentPrice"))
        if not ltp and len(hist) > 0:
            ltp = round(float(hist["Close"].iloc[-1]), 2)
        
        if not ltp:
            return result

        prev = safe_float(info.get("previousClose")) or (round(float(hist["Close"].iloc[-2]), 2) if len(hist) > 1 else ltp)

        result["ltp"] = ltp
        result["prev"] = prev
        result["chg1d"] = round((ltp - prev) / prev * 100, 2) if prev else 0
        result["w52h"] = safe_float(info.get("fiftyTwoWeekHigh"))
        result["w52l"] = safe_float(info.get("fiftyTwoWeekLow"))
        result["name"] = info.get("longName") or info.get("shortName") or sym
        result["sector"] = info.get("sector") or ""
        result["pe"] = safe_float(info.get("trailingPE"))
        result["pb"] = safe_float(info.get("priceToBook"))
        result["eps"] = safe_float(info.get("trailingEps"))
        result["bv"] = safe_float(info.get("bookValue"))

        roe_raw = safe_float(info.get("returnOnEquity"))
        result["roe"] = round(roe_raw * 100, 2) if roe_raw else None
        
        npm_raw = safe_float(info.get("profitMargins"))
        opm_raw = safe_float(info.get("operatingMargins"))
        result["npm_pct"] = round(npm_raw * 100, 2) if npm_raw else None
        result["opm_pct"] = round(opm_raw * 100, 2) if opm_raw else None

        result["mcap"] = to_cr(info.get("marketCap"))
        result["sales"] = to_cr(info.get("totalRevenue"))
        result["ebitda"] = to_cr(info.get("ebitda"))
        result["cfo"] = to_cr(info.get("operatingCashflow"))

        if result.get("w52h") and ltp:
            result["w52_pct"] = round((ltp / result["w52h"] - 1) * 100, 1)

        # Quarterly data
        try:
            q_data = {}
            def qkey(d): return str(d)[:10]
            
            for attr in ['quarterly_income_stmt', 'quarterly_financials']:
                try:
                    qf = getattr(t, attr, None)
                    if qf is not None and not qf.empty:
                        for row_label in qf.index:
                            rl = str(row_label).lower().strip()
                            for col in qf.columns:
                                k = qkey(col)
                                if k not in q_data: q_data[k] = {}
                                try:
                                    v = float(qf.loc[row_label, col])
                                    if v != v: continue
                                    if rl == 'total revenue': q_data[k]['rev'] = round(v/1e7, 2)
                                    elif rl == 'net income': q_data[k]['net'] = round(v/1e7, 2)
                                    elif rl == 'ebit': q_data[k]['ebit'] = round(v/1e7, 2)
                                except:
                                    continue
                        break
                except:
                    pass
            
            for attr in ['quarterly_cash_flow', 'quarterly_cashflow']:
                try:
                    qc = getattr(t, attr, None)
                    if qc is not None and not qc.empty:
                        for row_label in qc.index:
                            rl = str(row_label).lower().strip()
                            if any(x in rl for x in ('operating cash flow', 'cash from operations')):
                                for col in qc.columns:
                                    k = qkey(col)
                                    if k not in q_data: q_data[k] = {}
                                    try:
                                        v = float(qc.loc[row_label, col])
                                        if v != v: continue
                                        q_data[k]['cfo'] = round(v/1e7, 2)
                                    except:
                                        continue
                        break
                except:
                    pass
            
            for attr in ['quarterly_balance_sheet', 'quarterly_balancesheet']:
                try:
                    qb = getattr(t, attr, None)
                    if qb is not None and not qb.empty:
                        for row_label in qb.index:
                            rl = str(row_label).lower().strip()
                            if any(x in rl for x in ('total debt', 'long term debt')):
                                for col in qb.columns:
                                    k = qkey(col)
                                    if k not in q_data: q_data[k] = {}
                                    try:
                                        v = float(qb.loc[row_label, col])
                                        if v != v: continue
                                        q_data[k]['debt'] = round(v/1e7, 2)
                                    except:
                                        continue
                                break
                        break
                except:
                    pass
            
            if q_data:
                quarters = sorted([(k, v) for k, v in q_data.items() if v])[-12:]
                if quarters:
                    result['quarterly'] = [{'d': k, **v} for k, v in quarters]
        except:
            pass

        print(f"  ✓ {sym}: ₹{ltp}")

    except Exception as e:
        print(f"  ✗ {sym}: {str(e)[:50]}")

    return result

def get_session(name):
    global _SCR_SESSION, _MC_SESSION
    if name == "screener":
        if _SCR_SESSION is None:
            _SCR_SESSION = requests.Session()
            _SCR_SESSION.headers.update(HEADERS)
        return _SCR_SESSION
    elif name == "mc":
        if _MC_SESSION is None:
            _MC_SESSION = requests.Session()
            _MC_SESSION.headers.update(HEADERS)
        return _MC_SESSION

def hunt_holdings(sym):
    """Phase 3: Hunt for holdings data"""
    result = {}
    if not HAS_BS4: return result, None
    
    # Try Screener
    try:
        sess = get_session("screener")
        for url in [f"https://www.screener.in/company/{sym}/consolidated/", f"https://www.screener.in/company/{sym}/"]:
            try:
                r = sess.get(url, timeout=15)
                if r.status_code != 200: continue
                soup = BeautifulSoup(r.text, "html.parser")
                
                sh = soup.find("section", id="shareholding")
                if sh:
                    tbl = sh.find("table")
                    if tbl:
                        for row in tbl.find_all("tr"):
                            cells = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
                            if len(cells) < 2: continue
                            lbl = cells[0].lower()
                            vals = [safe_float(c.replace("%","").replace(",","")) for c in cells[1:]]
                            vals = [v for v in vals if v]
                            if not vals: continue
                            val = vals[-2] if len(vals) >= 2 else vals[0]
                            if "promoter" in lbl and "pledge" not in lbl: result["prom_pct"] = val
                            elif "fii" in lbl or "fpi" in lbl: result["fii_pct"] = val
                            elif "dii" in lbl: result["dii_pct"] = val
                if result: return result, "screener"
            except:
                pass
        time.sleep(0.2)
    except:
        pass
    
    # Try Moneycontrol
    try:
        sess = get_session("mc")
        for url in [f"https://www.moneycontrol.com/stock/{sym}", f"https://www.moneycontrol.com/stockprice/{sym}"]:
            try:
                r = sess.get(url, timeout=15)
                if r.status_code != 200: continue
                soup = BeautifulSoup(r.text, "html.parser")
                for table in soup.find_all('table'):
                    for row in table.find_all('tr'):
                        cells = [c.get_text(strip=True) for c in row.find_all(['td','th'])]
                        if len(cells) < 2: continue
                        lbl = cells[0].lower().strip()
                        try:
                            val = safe_float(cells[-1].replace("%","").replace(",",""))
                        except:
                            continue
                        if not val: continue
                        if "promoter" in lbl: result["prom_pct"] = val
                        elif "fii" in lbl or "fpi" in lbl: result["fii_pct"] = val
                        elif "dii" in lbl: result["dii_pct"] = val
                if result: return result, "moneycontrol"
            except:
                pass
        time.sleep(0.2)
    except:
        pass
    
    return result, None

def compute_signal(d):
    pos, neg = 0, 0
    for field, good, bad in [
        ("roe", lambda v: v > 15, lambda v: v < 8),
        ("roce", lambda v: v > 15, lambda v: v < 8),
        ("pe", lambda v: 0 < v < 18, lambda v: v > 35),
        ("opm_pct", lambda v: v > 15, lambda v: 0 < v < 8),
        ("prom_pct", lambda v: v > 50, lambda v: v < 35),
    ]:
        v = d.get(field)
        if v and v != 0:
            if good(v): pos += 1
            elif bad(v): neg += 1
    net = pos - neg
    return ("BUY" if net >= 3 else "SELL" if net <= -3 else "HOLD"), pos, neg

def main():
    resolved = resolve_symbols()
    syms = list(resolved.keys())
    ts = now_utc()
    
    print(f"📊 BharatMarkets Fundamentals | {ts.strftime('%Y-%m-%d %H:%M UTC')}\n")
    print(f"🔄 FRESH BUILD - Complete rebuild all phases\n")

    # Delete old data to start fresh
    Path(FUND_FILE).unlink(missing_ok=True)

    stats = {"yf": 0, "holdings": 0, "calc": 0, "err": 0}
    yf_results = {}

    # PHASE 1: FETCH
    print(f"⚡ PHASE 1: Yahoo Finance Fetch…\n")
    
    lock = threading.Lock()
    done = [0]

    def fetch_one(sym):
        data = fetch_yfinance(sym, yf_ticker=resolved[sym])
        with lock:
            done[0] += 1
            if done[0] % 15 == 0:
                print(f"  ── {done[0]}/{len(syms)} ──")
        time.sleep(0.15)
        return sym, data

    with ThreadPoolExecutor(max_workers=8) as ex:
        for fut in as_completed({ex.submit(fetch_one, s): s for s in syms}):
            sym, data = fut.result()
            yf_results[sym] = data

    print(f"\n✓ Phase 1 complete\n")

    # PHASE 2 & 3: CALCULATE & HUNT
    print(f"🔄 PHASE 2: Calculate Metrics & Hunt Holdings…\n")

    result = {}
    for i, sym in enumerate(syms):
        print(f"[{i+1}/{len(syms)}] {sym}", end=" | ", flush=True)

        stock = yf_results.get(sym, {})
        if not stock:
            stats["err"] += 1
            print("✗ No data")
            continue

        stats["yf"] += 1
        
        # Calculate metrics
        quarterly = stock.get('quarterly', [])
        if quarterly:
            calculate_metrics(stock, quarterly)
            stats["calc"] += 1
        
        # Hunt holdings
        holdings, src = hunt_holdings(sym)
        if holdings:
            stock.update(holdings)
            stats["holdings"] += 1

        # Signal
        sig, pos, neg = compute_signal(stock)
        stock.update({"signal": sig, "pos": pos, "neg": neg, "updated": ts.isoformat()})
        result[sym] = stock

        h_count = sum(1 for k in ['prom_pct','fii_pct','dii_pct'] if stock.get(k))
        print(f"{sig} h:{h_count}/3")

    # SAVE
    output = {
        "updated": ts.isoformat(),
        "count": len(result),
        "stocks": result,
    }

    Path(FUND_FILE).write_text(json.dumps(output, separators=(",",":"), default=str))

    print("\n" + "=" * 70)
    print(f"✅ COMPLETE! {len(result)} stocks\n")
    print(f"📊 Yahoo:{stats['yf']} Holdings:{stats['holdings']} Calc:{stats['calc']} Err:{stats['err']}\n")
    
    # Coverage
    prom = len([s for s in result.values() if s.get('prom_pct')])
    fii = len([s for s in result.values() if s.get('fii_pct')])
    dii = len([s for s in result.values() if s.get('dii_pct')])
    ev = len([s for s in result.values() if s.get('ev_ebitda')])
    
    print(f"✨ Holdings Coverage: Promoter:{prom}/{len(result)} FII:{fii}/{len(result)} DII:{dii}/{len(result)}")
    print(f"✨ Metrics: EV/EBITDA:{ev} ROIC:{len([s for s in result.values() if s.get('roic')])}")
    print(f"\n🎉 Ready: git add fundamentals.json && git push")

if __name__ == "__main__":
    main()
