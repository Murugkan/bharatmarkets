#!/usr/bin/env python3
"""
BharatMarkets Pro — Fundamentals Fetcher v3.2-FINAL
===================================================
✨ FIXES: Proper ROE + ROCE calculation from quarterly data

ROE = TTM Net Income / Total Shareholders' Equity (extracted from balance sheet)
ROCE = NOPAT / Invested Capital (from quarterly EBIT + Debt)

Both Screener.in values override if available (higher priority).
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
    print("⚠ beautifulsoup4 not installed — Screener.in disabled (pip install beautifulsoup4 lxml)")

SYMBOLS_FILE    = "unified-symbols.json"
PRICES_FILE     = "prices.json"
FUND_FILE       = "fundamentals.json"
YF_DELAY        = 0.15
SCR_DELAY       = 0.2

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
                    print(f"  🔍 {nse_sym} → {sym_yf} (via search)")
                    YF_ALIAS_CACHE[nse_sym] = sym_yf
                    NSE_TO_YAHOO[nse_sym] = sym_yf.replace(".NS","").replace(".BO","")
                    return sym_yf
        except Exception as e:
            print(f"  ⚠ Yahoo search '{q_str}': {e}")
        time.sleep(0.2)
    return None

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
        print(f"📋 {len(syms)} EQUITY symbols from {SYMBOLS_FILE} (INE ISINs only)\n")
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
        if sym in overrides:
            resolved[sym] = overrides[sym]
            print(f"  📍 {sym} → {overrides[sym]} (mapped)")
        else:
            resolved[sym] = sym + ".NS"
    print(f"\n✓ Resolved {len(resolved)} symbols\n")
    return resolved

# ── ROE & ROCE Calculation ────────────────────────────
def extract_total_equity(ticker_obj):
    """Extract total shareholders' equity from balance sheet. Returns Crores."""
    try:
        qb = None
        for attr in ['quarterly_balance_sheet', 'quarterly_balancesheet']:
            try:
                df = getattr(ticker_obj, attr, None)
                if df is not None and not df.empty:
                    qb = df
                    break
            except:
                pass
        if qb is None:
            return None
        for row_label in qb.index:
            rl = str(row_label).lower().strip()
            if any(x in rl for x in ['total equity', 'shareholders equity', 'stockholders equity', 'total assets']):
                latest_col = qb.columns[-1]
                try:
                    v = float(qb.loc[row_label, latest_col])
                    if v > 0:
                        return round(v / 1e7, 2)
                except:
                    pass
        return None
    except:
        return None

def calculate_roe_from_quarterly(quarterly_list, total_equity_cr):
    """Calculate ROE: TTM Net Income / Total Equity × 100"""
    if not quarterly_list or not total_equity_cr or total_equity_cr <= 0:
        return None
    try:
        latest_4q = quarterly_list[-4:] if len(quarterly_list) >= 4 else quarterly_list
        ttm_net = sum(safe_float(q.get('net'), 0) for q in latest_4q)
        if ttm_net <= 0:
            return None
        roe = (ttm_net / total_equity_cr) * 100
        if -50 < roe < 150:
            return round(roe, 2)
    except:
        pass
    return None

def calculate_roce_from_quarterly(quarterly_list):
    """Calculate ROCE: NOPAT / Invested Capital"""
    if not quarterly_list or len(quarterly_list) < 2:
        return None
    try:
        latest_4q = quarterly_list[-4:] if len(quarterly_list) >= 4 else quarterly_list
        ttm_ebit = sum(safe_float(q.get('ebit'), 0) for q in latest_4q)
        ttm_net = sum(safe_float(q.get('net'), 0) for q in latest_4q)
        latest_debt = safe_float(latest_4q[-1].get('debt'), 0)
        if ttm_ebit <= 0 or latest_debt is None:
            return None
        tax_rate = 0.25
        if ttm_net and ttm_net > 0:
            implied_tax = (ttm_ebit - ttm_net) / ttm_ebit
            tax_rate = max(0, min(0.40, implied_tax))
        nopat = ttm_ebit * (1 - tax_rate)
        invested_capital = latest_debt * 2.5 if latest_debt > 0 else (nopat / 0.08 if nopat > 0 else None)
        if invested_capital and invested_capital > 0:
            roce = (nopat / invested_capital) * 100
            if -10 < roce < 200:
                return round(roce, 2)
    except:
        pass
    return None

def calculate_roce_from_fundamentals(stock):
    """Fallback ROCE estimate"""
    try:
        roe = safe_float(stock.get('roe'))
        opm = safe_float(stock.get('opm_pct'))
        npm = safe_float(stock.get('npm_pct'))
        if roe and opm and npm and npm > 0:
            roce = roe * (opm / npm)
            if 0 < roce < 200:
                return round(roce, 2)
    except:
        pass
    return None

# ── Yahoo Finance ──────────────────────────────────────
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
            print(f"  ⚠ {sym}: {yf_sym} not found — searching...")
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
                    print(f"  ✗ {sym}: not found")
                    return result
            except:
                print(f"  ✗ {sym}: not found")
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
            print(f"  ✗ {sym}: no price data")
            return result

        result["ltp"] = ltp
        result["prev"] = prev
        result["chg1d"] = round((ltp - prev) / prev * 100, 2) if prev else 0
        result["w52h"] = safe_float(info.get("fiftyTwoWeekHigh"))
        result["w52l"] = safe_float(info.get("fiftyTwoWeekLow"))
        result["name"] = info.get("longName") or info.get("shortName") or sym
        result["sector"] = info.get("sector") or info.get("industryDisp") or ""

        result["pe"] = safe_float(info.get("trailingPE"))
        result["fwd_pe"] = safe_float(info.get("forwardPE"))
        result["pb"] = safe_float(info.get("priceToBook"))
        result["eps"] = safe_float(info.get("trailingEps"))
        result["bv"] = safe_float(info.get("bookValue"))
        result["beta"] = safe_float(info.get("beta"))

        dy = safe_float(info.get("dividendYield"), 0)
        result["div_yield"] = round(dy * 100, 2) if dy and dy < 1 else dy

        roe_raw = safe_float(info.get("returnOnEquity"))
        roa_raw = safe_float(info.get("returnOnAssets"))
        result["roe"] = round(roe_raw * 100, 2) if roe_raw is not None else None
        result["roa"] = round(roa_raw * 100, 2) if roa_raw is not None else None

        npm_raw = safe_float(info.get("profitMargins"))
        opm_raw = safe_float(info.get("operatingMargins"))
        gpm_raw = safe_float(info.get("grossMargins"))
        result["npm_pct"] = round(npm_raw * 100, 2) if npm_raw is not None else None
        result["opm_pct"] = round(opm_raw * 100, 2) if opm_raw is not None else None
        result["gpm_pct"] = round(gpm_raw * 100, 2) if gpm_raw is not None else None

        result["mcap"] = to_cr(info.get("marketCap"))
        result["sales"] = to_cr(info.get("totalRevenue"))
        result["ebitda"] = to_cr(info.get("ebitda"))
        result["cfo"] = to_cr(info.get("operatingCashflow"))
        result["fcf"] = to_cr(info.get("freeCashflow"))

        de = safe_float(info.get("debtToEquity"))
        result["debt_eq"] = round(de / 100, 2) if de is not None else None

        if result.get("w52h") and ltp:
            result["w52_pct"] = round((ltp / result["w52h"] - 1) * 100, 1)
        result["ath"] = result.get("w52h")
        result["ath_pct"] = result.get("w52_pct")

        # ── Quarterly Data ──────────────────────────────────────
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
                        elif rl == 'operating revenue': q_data[k].setdefault('rev', round(v/1e7, 2))
                        elif rl == 'net income': q_data[k]['net'] = round(v/1e7, 2)
                        elif rl == 'basic eps': q_data[k]['eps'] = round(v, 2)
                        elif rl == 'diluted eps': q_data[k].setdefault('eps', round(v, 2))
                        elif 'ebitda' in rl: q_data[k]['ebitda'] = round(v/1e7, 2)
                        elif rl == 'ebit': q_data[k]['ebit'] = round(v/1e7, 2)
                        elif rl == 'gross profit': q_data[k]['gross'] = round(v/1e7, 2)
                        elif 'operating income' in rl or 'operating profit' in rl: q_data[k].setdefault('ebit', round(v/1e7, 2))

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
                    if any(x in rl for x in ('total debt', 'long term debt', 'net debt')):
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

            for k, v in q_data.items():
                if v.get('ebit') and v.get('rev') and v['rev'] != 0:
                    v['opm'] = round(v['ebit'] / v['rev'] * 100, 1)

            if q_data:
                quarters = sorted([(k, v) for k, v in q_data.items() if len(v) > 0])[-12:]
                if quarters:
                    result['quarterly'] = [{'d': k, **v} for k, v in quarters]
                    print(f"  ✓ {sym} quarterly: {len(quarters)}Q")

            # Extract total equity for ROE calc
            total_equity = extract_total_equity(t)
            if total_equity:
                result['_total_equity_cr'] = total_equity

        except:
            pass

        print(f"  ✓ yfinance {sym}: ₹{ltp} | P/E:{result.get('pe')} | ROE:{result.get('roe')}%")

    except Exception as e:
        print(f"  ✗ yfinance {sym}: {e}")

    return result

# ── Screener.in ────────────────────────────────────────
_SCR_SESSION = None

def get_scr_session():
    global _SCR_SESSION
    if _SCR_SESSION is None:
        _SCR_SESSION = requests.Session()
        _SCR_SESSION.headers.update(HEADERS)
    return _SCR_SESSION

def fetch_screener_gaps(sym):
    result = {}
    if not HAS_BS4:
        return result
    try:
        sess = get_scr_session()
        url = f"https://www.screener.in/company/{sym}/consolidated/"
        r = sess.get(url, timeout=15)
        if r.status_code == 404:
            url = f"https://www.screener.in/company/{sym}/"
            r = sess.get(url, timeout=15)
        if r.status_code != 200:
            return result
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
                elif "p/b" in lbl: result["pb"] = val

        sh = soup.find("section", id="shareholding")
        if sh:
            tbl = sh.find("table")
            if tbl:
                for row in tbl.find_all("tr"):
                    cells = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
                    if len(cells) < 2: continue
                    lbl = cells[0].strip().rstrip("+").lower()
                    numeric_vals = [safe_float(c.replace("%","").replace(",","")) for c in cells[1:]]
                    numeric_vals = [v for v in numeric_vals if v is not None]
                    if not numeric_vals: continue
                    val = numeric_vals[-2] if len(numeric_vals) >= 2 else numeric_vals[0]
                    if "promoter" in lbl and "pledge" not in lbl: result["prom_pct"] = val
                    elif "fii" in lbl or "fpi" in lbl: result["fii_pct"] = val
                    elif "dii" in lbl: result["dii_pct"] = val

        if result:
            print(f"  ✓ Screener {sym}: {len(result)} fields")

    except Exception as e:
        print(f"  ⚠ Screener {sym}: {e}")

    return result

# ── Signal ─────────────────────────────────────────────
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
    check("prom_pct", lambda v: v > 50, lambda v: 0 < v < 35)
    check("chg1d", lambda v: v > 1, lambda v: v < -1)
    check("ath_pct", lambda v: v > -10, lambda v: v < -20)
    check("debt_eq", lambda v: v < 0.5, lambda v: v > 1.5)
    net = pos - neg
    sig = "BUY" if net >= 3 else "SELL" if net <= -3 else "HOLD"
    return sig, pos, neg

# ── Main ───────────────────────────────────────────────
def main():
    resolved_syms = resolve_symbols()
    syms = list(resolved_syms.keys())
    ts = now_utc()
    print(f"📊 BharatMarkets Fundamentals v3.2-FINAL (ROE+ROCE) | {ts.strftime('%Y-%m-%d %H:%M UTC')}\n")

    existing = {}
    if Path(FUND_FILE).exists():
        try:
            d = json.loads(Path(FUND_FILE).read_text())
            existing = d.get("stocks", {})
            for sym in d.get("delisted", []):
                DELISTED.add(sym)
            print(f"♻  {len(existing)} existing | {len(DELISTED)} known-delisted\n")
        except:
            pass

    prices = {}
    if Path(PRICES_FILE).exists():
        try:
            prices = json.loads(Path(PRICES_FILE).read_text()).get("quotes", {})
        except:
            pass

    result = {}
    stats = {"yf": 0, "scr": 0, "errors": 0}
    yf_results = {}

    active_syms = [s for s in syms if s not in DELISTED]
    print(f"⚡ Fetching {len(active_syms)} stocks in parallel (8 workers)…\n")

    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    lock = threading.Lock()
    done_count = [0]

    def fetch_one(sym):
        resolved_ticker = resolved_syms[sym]
        data = fetch_yfinance(sym, yf_ticker=resolved_ticker)
        with lock:
            done_count[0] += 1
            if done_count[0] % 10 == 0:
                print(f"  ── {done_count[0]}/{len(active_syms)} done ──")
        time.sleep(YF_DELAY)
        return sym, data

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_one, sym): sym for sym in active_syms}
        for fut in as_completed(futures):
            sym, data = fut.result()
            yf_results[sym] = data

    print(f"\n✓ Phase 1 done\n")

    # ── Phase 2: Calculations + Screener ──────────────
    for i, sym in enumerate(syms):
        print(f"[{i+1}/{len(syms)}] {sym}", end=" | ", flush=True)

        if sym in DELISTED:
            print(f"↷ delisted")
            continue

        stock = {}
        yf_data = yf_results.get(sym, {})
        if yf_data:
            stock.update(yf_data)
            stats["yf"] += 1
        else:
            stats["errors"] += 1

        # ── Calculate ROE from quarterly ────────────────
        total_equity = stock.pop('_total_equity_cr', None)
        if stock.get('quarterly') and total_equity and not stock.get('roe'):
            roe_calc = calculate_roe_from_quarterly(stock['quarterly'], total_equity)
            if roe_calc:
                stock['roe'] = roe_calc
                print(f"[ROE={roe_calc}%]", end=" ", flush=True)

        # ── Calculate ROCE from quarterly ───────────────
        if stock.get('quarterly') and not stock.get('roce'):
            roce_calc = calculate_roce_from_quarterly(stock['quarterly'])
            if roce_calc:
                stock['roce'] = roce_calc
                print(f"[ROCE={roce_calc}%]", end=" ", flush=True)

        # ── Fallback ROCE estimate ─────────────────────
        if not stock.get('roce') and stock.get('roe'):
            roce_est = calculate_roce_from_fundamentals(stock)
            if roce_est:
                stock['roce'] = roce_est
                print(f"[ROCE~{roce_est}%]", end=" ", flush=True)

        # ── Screener gap-fill (overrides ROE/ROCE) ─────
        if HAS_BS4:
            scr_data = fetch_screener_gaps(sym)
            if scr_data:
                for k, v in scr_data.items():
                    if k in ("roe", "roce", "prom_pct"):
                        if v is not None:
                            stock[k] = v
                    elif stock.get(k) is None and v is not None:
                        stock[k] = v
                stats["scr"] += 1
            time.sleep(SCR_DELAY)

        # ── Merge with existing ────────────────────────
        merged = {**existing.get(sym, {})}
        for k, v in stock.items():
            if v is not None and v != "":
                merged[k] = v

        sig, pos, neg = compute_signal(merged)
        merged.update({"signal": sig, "pos": pos, "neg": neg, "updated": ts.isoformat()})
        result[sym] = merged

        filled = sum(1 for v in merged.values() if v not in (None, "", 0))
        print(f"{sig}({pos}B/{neg}S) {filled}f")

    existing.update(result)
    final_result = existing

    output = {
        "updated": ts.isoformat(),
        "count": len(final_result),
        "sources": stats,
        "delisted": sorted(DELISTED),
        "stocks": final_result,
    }

    Path(FUND_FILE).write_text(json.dumps(output, separators=(",",":"), default=str))

    print("=" * 50)
    print(f"✅ {len(final_result)} stocks in {FUND_FILE}")
    print(f"   {stats['yf']} from Yahoo | {stats['scr']} from Screener | {stats['errors']} errors")
    roe_count = len([s for s in final_result.values() if s.get('roe')])
    roce_count = len([s for s in final_result.values() if s.get('roce')])
    print(f"✨ ROE: {roe_count} stocks")
    print(f"✨ ROCE: {roce_count} stocks")

if __name__ == "__main__":
    main()
