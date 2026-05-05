#!/usr/bin/env python3
"""
BharatMarkets Pro — Fundamentals Fetcher COMPLETE v3.8-v2
=========================================================
✨ ALL-IN-ONE with --fresh flag for complete rebuild
- Phase 1: Yahoo Finance (fresh fetch)
- Phase 2: Screener.in (secondary)
- Phase 3: Calculated metrics (EV/EBITDA, ROIC, ratios)
- Phase 4: Holdings hunter (Screener → Moneycontrol → TickerTape)

Usage:
  python3 fetch_fundamentals_COMPLETE_v2.py         # Incremental
  python3 fetch_fundamentals_COMPLETE_v2.py --fresh # Fresh rebuild
"""

import json, time, datetime, re, os, sys
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
FRESH_MODE = "--fresh" in sys.argv

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}

SKIP = {"NIFTY","BANKNIFTY","NIFTY50","SENSEX","NIFTYIT","MIDCAP","SMALLCAP","NIFTYBANK"}
DELISTED = set()
COMMON_FACE_VALUES = [1, 2, 5, 10, 25, 50, 100]

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
_TT_SESSION = None

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
        print(f"📋 {len(syms)} EQUITY symbols\n")
    except Exception as e:
        print(f"⚠ Cannot read {SYMBOLS_FILE}: {e}")
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
    print(f"✓ Resolved {len(resolved)} symbols\n")
    return resolved

# ════════════════════════════════════════════════════════════════════════════
# PHASE 2: CALCULATED METRICS
# ════════════════════════════════════════════════════════════════════════════

def calculate_valuation_metrics(stock):
    try:
        mcap = safe_float(stock.get('mcap'))
        ebitda = safe_float(stock.get('ebitda'))
        total_debt = safe_float(stock.get('total_debt'))
        if mcap and ebitda and ebitda > 0:
            if total_debt:
                ev = mcap + total_debt
            else:
                ev = mcap * 1.2
            ev_ebitda = ev / ebitda
            if 0 < ev_ebitda < 100:
                stock['ev_ebitda'] = round(ev_ebitda, 2)
    except:
        pass

def calculate_quality_metrics(stock, quarterly_list):
    try:
        if quarterly_list and len(quarterly_list) >= 4:
            latest_4q = quarterly_list[-4:]
            ttm_ebit = sum(safe_float(q.get('ebit'), 0) for q in latest_4q)
            latest_debt = safe_float(latest_4q[-1].get('debt'), 0)
            latest_equity = safe_float(latest_4q[-1].get('equity'), 0)
            
            if ttm_ebit > 0 and (latest_debt or latest_equity):
                tax_rate = 0.25
                nopat = ttm_ebit * (1 - tax_rate)
                invested_capital = (latest_equity or 0) + (latest_debt or 0)
                if invested_capital > 0:
                    roic = (nopat / invested_capital) * 100
                    if 0 < roic < 200:
                        stock['roic'] = round(roic, 2)
    except:
        pass
    
    try:
        if quarterly_list and len(quarterly_list) >= 4:
            latest_4q = quarterly_list[-4:]
            ttm_ocf = sum(safe_float(q.get('cfo'), 0) for q in latest_4q)
            ttm_net = sum(safe_float(q.get('net'), 0) for q in latest_4q)
            
            if ttm_net and ttm_net > 0:
                cash_conv = (ttm_ocf / ttm_net) * 100
                if 0 < cash_conv < 500:
                    stock['cash_conv'] = round(cash_conv, 2)
    except:
        pass
    
    try:
        mcap = safe_float(stock.get('mcap'))
        cfo = safe_float(stock.get('cfo'))
        if mcap and mcap > 0 and cfo and cfo > 0:
            capex = cfo * 0.3
            fcf = cfo - capex
            fcf_yield = (fcf / mcap) * 100
            if -20 < fcf_yield < 50:
                stock['fcf_yield'] = round(fcf_yield, 2)
    except:
        pass
    
    try:
        total_debt = safe_float(stock.get('total_debt'))
        ebitda = safe_float(stock.get('ebitda'))
        if total_debt and ebitda and ebitda > 0:
            d_ebitda = total_debt / ebitda
            if 0 < d_ebitda < 20:
                stock['d_ebitda'] = round(d_ebitda, 2)
    except:
        pass

def calculate_health_metrics(stock, bs_data):
    try:
        curr_assets = bs_data.get('current_assets')
        curr_liab = bs_data.get('current_liabilities')
        if curr_assets and curr_liab and curr_liab > 0:
            curr_ratio = curr_assets / curr_liab
            if 0 < curr_ratio < 10:
                stock['curr_ratio'] = round(curr_ratio, 2)
    except:
        pass

# ════════════════════════════════════════════════════════════════════════════
# YAHOO FINANCE
# ════════════════════════════════════════════════════════════════════════════

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
    queries = [cdsl_name] if cdsl_name else [nse_sym, nse_sym + " NSE", nse_sym[:6]]
    for q_str in queries:
        try:
            url = f"https://query2.finance.yahoo.com/v1/finance/search?q={requests.utils.quote(q_str)}&lang=en-IN&region=IN&quotesCount=8&newsCount=0&enableFuzzyQuery=true&enableEnhancedTrivialQuery=true"
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200: continue
            quotes = r.json().get("quotes", [])
            for q in quotes:
                sym_yf = q.get("symbol", "")
                if (sym_yf.endswith(".NS") or sym_yf.endswith(".BO")) and q.get("quoteType", "") in ("EQUITY", ""):
                    YF_ALIAS_CACHE[nse_sym] = sym_yf
                    NSE_TO_YAHOO[nse_sym] = sym_yf.replace(".NS","").replace(".BO","")
                    return sym_yf
        except:
            pass
        time.sleep(0.2)
    return None

def fetch_yfinance(sym, yf_ticker=None):
    result = {}
    try:
        yf_sym = yf_ticker if yf_ticker else resolve_yf_sym(sym)
        t = yf.Ticker(yf_sym)
        hist_short = None
        try:
            hist_short = t.history(period="1mo", interval="1d", auto_adjust=True)
        except:
            pass

        if hist_short is None or hist_short.empty:
            found_sym = yahoo_search_sym(sym, cdsl_name=CDSL_NAMES.get(sym))
            if found_sym:
                yf_sym = found_sym
                t = yf.Ticker(yf_sym)
                try:
                    hist_short = t.history(period="1mo", interval="1d", auto_adjust=True)
                except:
                    hist_short = None

        if hist_short is None or hist_short.empty:
            try:
                bo_sym = sym + ".BO"
                t_bo = yf.Ticker(bo_sym)
                hist_bo = t_bo.history(period="1mo", interval="1d", auto_adjust=True)
                if hist_bo is not None and not hist_bo.empty:
                    yf_sym = bo_sym
                    t = t_bo
                    hist_short = hist_bo
                    YF_ALIAS_CACHE[sym] = bo_sym
                else:
                    return result
            except:
                return result

        info = {}
        try:
            info = t.info or {}
        except:
            pass

        ltp, prev = None, None
        try:
            fi = t.fast_info
            ltp = safe_float(getattr(fi, "last_price", None))
            prev = safe_float(getattr(fi, "previous_close", None))
        except:
            pass
        if not ltp:
            ltp = safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
            prev = safe_float(info.get("previousClose"))
        if not ltp:
            closes = hist_short["Close"].dropna()
            if not closes.empty:
                ltp = round(float(closes.iloc[-1]), 2)
                prev = round(float(closes.iloc[-2]), 2) if len(closes) >= 2 else ltp

        if not ltp:
            return result

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
        roa_raw = safe_float(info.get("returnOnAssets"))
        result["roe"] = round(roe_raw * 100, 2) if roe_raw is not None else None
        result["roa"] = round(roa_raw * 100, 2) if roa_raw is not None else None

        npm_raw = safe_float(info.get("profitMargins"))
        opm_raw = safe_float(info.get("operatingMargins"))
        result["npm_pct"] = round(npm_raw * 100, 2) if npm_raw is not None else None
        result["opm_pct"] = round(opm_raw * 100, 2) if opm_raw is not None else None

        result["mcap"] = to_cr(info.get("marketCap"))
        result["sales"] = to_cr(info.get("totalRevenue"))
        result["ebitda"] = to_cr(info.get("ebitda"))
        result["cfo"] = to_cr(info.get("operatingCashflow"))

        if result.get("w52h") and ltp:
            result["w52_pct"] = round((ltp / result["w52h"] - 1) * 100, 1)
        result["ath"] = result.get("w52h")
        result["ath_pct"] = result.get("w52_pct")

        try:
            q_data = {}
            def qkey(d): return str(d)[:10]

            qf = None
            for attr in ['quarterly_income_stmt', 'quarterly_financials']:
                try:
                    df = getattr(t, attr, None)
                    if df is not None and not df.empty:
                        qf = df
                        break
                except:
                    pass

            if qf is not None:
                for row_label in qf.index:
                    rl = str(row_label).lower().strip()
                    for col in qf.columns:
                        k = qkey(col)
                        if k not in q_data: q_data[k] = {}
                        try:
                            v = float(qf.loc[row_label, col])
                            if v != v: continue
                        except:
                            continue
                        if rl == 'total revenue': q_data[k]['rev'] = round(v/1e7, 2)
                        elif rl == 'net income': q_data[k]['net'] = round(v/1e7, 2)
                        elif rl == 'ebit': q_data[k]['ebit'] = round(v/1e7, 2)

            qc = None
            for attr in ['quarterly_cash_flow', 'quarterly_cashflow']:
                try:
                    df = getattr(t, attr, None)
                    if df is not None and not df.empty:
                        qc = df
                        break
                except:
                    pass

            if qc is not None:
                for row_label in qc.index:
                    rl = str(row_label).lower().strip()
                    for col in qc.columns:
                        k = qkey(col)
                        if k not in q_data: q_data[k] = {}
                        try:
                            v = float(qc.loc[row_label, col])
                            if v != v: continue
                        except:
                            continue
                        if any(x in rl for x in ('operating cash flow', 'cash from operations')):
                            q_data[k]['cfo'] = round(v/1e7, 2)

            qb = None
            for attr in ['quarterly_balance_sheet', 'quarterly_balancesheet']:
                try:
                    df = getattr(t, attr, None)
                    if df is not None and not df.empty:
                        qb = df
                        break
                except:
                    pass

            if qb is not None:
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

            if q_data:
                quarters = sorted([(k, v) for k, v in q_data.items() if len(v) > 0])[-12:]
                if quarters:
                    result['quarterly'] = [{'d': k, **v} for k, v in quarters]

        except:
            pass

        try:
            qb = None
            for attr in ['quarterly_balance_sheet', 'quarterly_balancesheet']:
                try:
                    df = getattr(t, attr, None)
                    if df is not None and not df.empty:
                        qb = df
                        break
                except:
                    pass
            
            if qb is not None:
                bs_data = {}
                latest_col = qb.columns[-1]
                for row_label in qb.index:
                    rl = str(row_label).lower().strip()
                    try:
                        v = float(qb.loc[row_label, latest_col])
                        if v > 0:
                            if any(x in rl for x in ['total equity', 'shareholders equity']):
                                bs_data['total_equity'] = round(v / 1e7, 2)
                            elif any(x in rl for x in ['total debt', 'long term debt']):
                                bs_data['total_debt'] = round(v / 1e7, 2)
                            elif 'current asset' in rl:
                                bs_data['current_assets'] = round(v / 1e7, 2)
                            elif 'current liability' in rl or 'current liabilities' in rl:
                                bs_data['current_liabilities'] = round(v / 1e7, 2)
                    except:
                        pass
                
                if bs_data:
                    result['_bs_data'] = bs_data
        except:
            pass

        print(f"  ✓ {sym}: ₹{ltp}")

    except Exception as e:
        print(f"  ✗ {sym}: {e}")

    return result

# ════════════════════════════════════════════════════════════════════════════
# PHASE 3: SCREENER + HOLDINGS HUNTER
# ════════════════════════════════════════════════════════════════════════════

def get_session(name):
    global _SCR_SESSION, _MC_SESSION, _TT_SESSION
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
    elif name == "tt":
        if _TT_SESSION is None:
            _TT_SESSION = requests.Session()
            _TT_SESSION.headers.update(HEADERS)
        return _TT_SESSION

def fetch_screener(sym):
    result = {}
    if not HAS_BS4: return result, None
    try:
        sess = get_session("screener")
        url = f"https://www.screener.in/company/{sym}/consolidated/"
        r = sess.get(url, timeout=15)
        if r.status_code == 404:
            url = f"https://www.screener.in/company/{sym}/"
            r = sess.get(url, timeout=15)
        if r.status_code != 200: return result, None
        
        soup = BeautifulSoup(r.text, "html.parser")

        ul = soup.find("ul", id="top-ratios")
        if ul:
            for li in ul.find_all("li"):
                spans = li.find_all("span")
                if len(spans) < 2: continue
                lbl = spans[0].get_text(strip=True).lower()
                raw = spans[-1].get_text(strip=True).replace(",","").replace("₹","").replace("%","")
                val = safe_float(raw)
                if val is None: continue
                if "roce" in lbl: result["roce"] = val
                elif "roe" in lbl: result["roe"] = val
                elif "p/e" in lbl: result["pe"] = val
                elif "face value" in lbl: result["face_value"] = val
                elif "debt" in lbl and "ebitda" in lbl: result["d_ebitda"] = val

        sh = soup.find("section", id="shareholding")
        if sh:
            tbl = sh.find("table")
            if tbl:
                for row in tbl.find_all("tr"):
                    cells = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
                    if len(cells) < 2: continue
                    lbl = cells[0].lower()
                    numeric_vals = [safe_float(c.replace("%","").replace(",","")) for c in cells[1:]]
                    numeric_vals = [v for v in numeric_vals if v is not None]
                    if not numeric_vals: continue
                    val = numeric_vals[-2] if len(numeric_vals) >= 2 else numeric_vals[0]
                    if "promoter" in lbl and "pledge" not in lbl: result["prom_pct"] = val
                    elif "fii" in lbl or "fpi" in lbl: result["fii_pct"] = val
                    elif "dii" in lbl: result["dii_pct"] = val

        if result: return result, "screener"
    except:
        pass
    return result, None

def fetch_moneycontrol_holdings(sym):
    result = {}
    if not HAS_BS4: return result, None
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
                continue
    except:
        pass
    return result, None

def fetch_tickertape_holdings(sym):
    result = {}
    if not HAS_BS4: return result, None
    try:
        sess = get_session("tt")
        url = f"https://tickertape.in/stocks/{sym}"
        r = sess.get(url, timeout=15)
        if r.status_code != 200: return result, None
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
        if result: return result, "tickertape"
    except:
        pass
    return result, None

def hunt_holdings(sym):
    """Aggressive holdings hunt with multiple fallbacks"""
    result, src = fetch_screener(sym)
    if result: return result, src
    time.sleep(0.2)
    
    result, src = fetch_moneycontrol_holdings(sym)
    if result: return result, src
    time.sleep(0.2)
    
    result, src = fetch_tickertape_holdings(sym)
    if result: return result, src
    time.sleep(0.2)
    
    return {}, None

def compute_signal(d):
    pos, neg = 0, 0
    def check(field, good_fn, bad_fn):
        nonlocal pos, neg
        v = d.get(field)
        if v is None or v == 0: return
        if good_fn(v): pos += 1
        elif bad_fn(v): neg += 1
    check("roe", lambda v: v > 15, lambda v: v < 8)
    check("roce", lambda v: v > 15, lambda v: v < 8)
    check("pe", lambda v: 0 < v < 18, lambda v: v > 35)
    check("opm_pct", lambda v: v > 15, lambda v: 0 < v < 8)
    check("npm_pct", lambda v: v > 10, lambda v: 0 < v < 5)
    check("prom_pct", lambda v: v > 50, lambda v: v < 35)
    net = pos - neg
    sig = "BUY" if net >= 3 else "SELL" if net <= -3 else "HOLD"
    return sig, pos, neg

# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def main():
    resolved_syms = resolve_symbols()
    syms = list(resolved_syms.keys())
    ts = now_utc()
    
    mode_str = "🔄 FRESH REBUILD" if FRESH_MODE else "♻️  INCREMENTAL"
    print(f"📊 BharatMarkets COMPLETE v3.8-v2 | {mode_str} | {ts.strftime('%Y-%m-%d %H:%M UTC')}\n")

    existing = {}
    if not FRESH_MODE and Path(FUND_FILE).exists():
        try:
            d = json.loads(Path(FUND_FILE).read_text())
            existing = d.get("stocks", {})
            for sym in d.get("delisted", []):
                DELISTED.add(sym)
            print(f"♻  {len(existing)} existing stocks loaded\n")
        except:
            pass
    elif FRESH_MODE:
        print(f"🔄 FRESH MODE: Starting from scratch\n")
        Path(FUND_FILE).unlink(missing_ok=True)

    result = {}
    stats = {"yf": 0, "scr": 0, "mc": 0, "tt": 0, "calc": 0, "errors": 0, "updated": 0}
    yf_results = {}

    active_syms = [s for s in syms if s not in DELISTED]
    
    # ── PHASE 1: FETCH ─────────────────────────────────────────────────────
    print(f"⚡ PHASE 1: Fetching {len(active_syms)} stocks…\n")
    
    lock = threading.Lock()
    done_count = [0]

    def fetch_one(sym):
        resolved_ticker = resolved_syms[sym]
        data = fetch_yfinance(sym, yf_ticker=resolved_ticker)
        with lock:
            done_count[0] += 1
            if done_count[0] % 10 == 0:
                print(f"  ── {done_count[0]}/{len(active_syms)} ──")
        time.sleep(0.15)
        return sym, data

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_one, sym): sym for sym in active_syms}
        for fut in as_completed(futures):
            sym, data = fut.result()
            yf_results[sym] = data

    print(f"\n✓ Phase 1 done\n")

    # ── PHASE 2: CALCULATE + HUNT ──────────────────────────────────────────
    print(f"🔄 PHASE 2: Calculations & Holdings Hunt…\n")

    for i, sym in enumerate(syms):
        print(f"[{i+1}/{len(syms)}] {sym}", end=" | ", flush=True)

        if sym in DELISTED:
            print("↷ delisted")
            continue

        stock = {}
        
        # In FRESH mode, start from zero. In incremental, load existing
        if not FRESH_MODE and sym in existing:
            stock.update(existing[sym])
        
        yf_data = yf_results.get(sym, {})
        if yf_data:
            # FRESH mode: replace all. Incremental: merge
            if FRESH_MODE:
                stock = yf_data.copy()
            else:
                stock.update(yf_data)
            stats["yf"] += 1
        else:
            stats["errors"] += 1

        bs_data = stock.pop('_bs_data', {})
        quarterly_list = stock.get('quarterly', [])

        # Calculate metrics
        if quarterly_list:
            calculate_quality_metrics(stock, quarterly_list)
            stats["calc"] += 1
        
        calculate_valuation_metrics(stock)
        calculate_health_metrics(stock, bs_data)

        # Hunt holdings
        holdings, src = hunt_holdings(sym)
        if holdings:
            for k, v in holdings.items():
                if v is not None and (FRESH_MODE or not stock.get(k)):
                    stock[k] = v
            if src == "screener": stats["scr"] += 1
            elif src == "moneycontrol": stats["mc"] += 1
            elif src == "tickertape": stats["tt"] += 1

        # Finalize
        sig, pos, neg = compute_signal(stock)
        stock.update({"signal": sig, "pos": pos, "neg": neg, "updated": ts.isoformat()})
        result[sym] = stock
        stats["updated"] += 1

        filled = sum(1 for v in stock.values() if v not in (None, "", 0))
        holdings_filled = sum(1 for k in ['prom_pct','fii_pct','dii_pct'] if stock.get(k))
        print(f"{sig} h:{holdings_filled}/3 f:{filled}")

    final_result = result

    output = {
        "updated": ts.isoformat(),
        "count": len(final_result),
        "sources": stats,
        "delisted": sorted(DELISTED),
        "stocks": final_result,
    }

    Path(FUND_FILE).write_text(json.dumps(output, separators=(",",":"), default=str))

    print("\n" + "=" * 70)
    print(f"✅ COMPLETE! {len(final_result)} stocks {'FRESH rebuilt' if FRESH_MODE else 'updated'}\n")
    print(f"📊 Phase 1 Sources: YF:{stats['yf']} ERR:{stats['errors']}")
    print(f"📊 Phase 2 Calc: {stats['calc']} stocks")
    print(f"📊 Holdings Found: Screener:{stats['scr']} Moneycontrol:{stats['mc']} TickerTape:{stats['tt']}\n")
    
    # Coverage
    roe = len([s for s in final_result.values() if s.get('roe')])
    roce = len([s for s in final_result.values() if s.get('roce')])
    ev_eb = len([s for s in final_result.values() if s.get('ev_ebitda')])
    roic = len([s for s in final_result.values() if s.get('roic')])
    cash_c = len([s for s in final_result.values() if s.get('cash_conv')])
    d_eb = len([s for s in final_result.values() if s.get('d_ebitda')])
    curr_r = len([s for s in final_result.values() if s.get('curr_ratio')])
    prom = len([s for s in final_result.values() if s.get('prom_pct')])
    fii = len([s for s in final_result.values() if s.get('fii_pct')])
    dii = len([s for s in final_result.values() if s.get('dii_pct')])
    
    print(f"✨ COVERAGE:")
    print(f"   Fundamentals: ROE:{roe} ROCE:{roce} PE:{len([s for s in final_result.values() if s.get('pe')])}")
    print(f"   Valuations: EV/EBITDA:{ev_eb} ROIC:{roic} CashConv:{cash_c}")
    print(f"   Health: D/EBITDA:{d_eb} CurrRatio:{curr_r}")
    print(f"   Holdings: Promoter:{prom}/{len(final_result)} FII:{fii}/{len(final_result)} DII:{dii}/{len(final_result)}")
    print(f"\n🎉 Ready to deploy! fundamentals.json updated")
    print(f"\n💡 Next time: python3 fetch_fundamentals_COMPLETE_v2.py --fresh")

if __name__ == "__main__":
    main()
