#!/usr/bin/env python3
"""
BharatMarkets Pro — Fundamentals Fetcher v3
============================================
Reads symbols from:
  1. portfolio_symbols.txt  (exported from app — YOUR actual portfolio)
  2. watchlist.txt          (fallback / extras)

Sources for data:
  1. Yahoo Finance (yfinance) — primary, most fields
  2. Screener.in              — prom%, FII%, DII%, gap fields

Writes: fundamentals.json
"""

import json, time, datetime, re, os
from pathlib import Path

try:
    import yfinance as yf
    import logging
    # Suppress yfinance noise for delisted/404 symbols
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    logging.getLogger("peewee").setLevel(logging.CRITICAL)
except ImportError:
    raise SystemExit("pip install yfinance")

import requests   # always required — pip install requests

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True   # enables Screener.in parsing
except ImportError:
    HAS_BS4 = False
    print("⚠ beautifulsoup4 not installed — Screener.in disabled (pip install beautifulsoup4 lxml)")

WATCHLIST_FILE  = "watchlist.txt"
PORTFOLIO_FILE  = "portfolio_symbols.txt"   # committed from app
PRICES_FILE     = "prices.json"
FUND_FILE       = "fundamentals.json"
YF_DELAY        = 0.15
SCR_DELAY       = 0.2

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}

SKIP = {"NIFTY","BANKNIFTY","NIFTY50","SENSEX","NIFTYIT","MIDCAP","SMALLCAP","NIFTYBANK"}

# Runtime cache of confirmed-delisted symbols — populated during run, skipped on re-runs
# Also persisted in fundamentals.json under "delisted" key
DELISTED = set()


# NSE symbol → Yahoo Finance ticker alias map
# Rule: only add entries where NSE symbol ≠ Yahoo symbol
# For most stocks, SYM.NS works directly — only exceptions listed here
NSE_TO_YAHOO = {
    # ── Renamed/merged companies ──────────────────────────────────────
    "AMARAJAB":      "ARE&M",        # Amara Raja Energy & Mobility
    "AMARAJABAT":    "ARE&M",
    "ASSALCOHOL":    "ASALCBR",      # Associated Alcohols & Breweries
    "MINDTREE":      "LTIM",         # Merged into LTIMindtree
    "LTIMINDTREE":   "LTIM",
    "HDFC":          "HDFCBANK",     # Post-merger
    "RUCHI":         "RUCHISOYA",
    "BLACKBOXLIMI":  "BBOX",         # Black Box Ltd
    # ── Company renamed — Yahoo dropped old ticker, must hardcode ──────
    "ZINKA":         "BLACKBUCK",    # Renamed to BlackBuck Limited Aug 2025
    "CIGNITI":       "CIGNITITEC",   # Relisted as CIGNITITEC after Coforge acquisition
    "CIGNITITECH":   "CIGNITITEC",   # alternate CDSL spelling
    # ── CDSL symbol → actual NSE/Yahoo symbol (truncation mismatches) ──
    "GRAUERWEIL":    "GRAUWEIL",     # CDSL: GRAUERWEIL  → NSE: GRAUWEIL
    "ROSSELLTECH":   "ROSSTECH",     # CDSL: ROSSELLTECH → NSE: ROSSTECH
    "INDOTECHTR":    "INDOTECH",     # CDSL: INDOTECHTR  → NSE: INDOTECH
    "SHILCHAR":      "SHILCTECH",    # CDSL: SHILCHAR    → NSE: SHILCTECH
    "HBLPOWER":      "HBLENGINE",    # Renamed HBL Power → HBL Engineering
    "KPENERGI":      "KPEL",         # CDSL: KPENERGI    → NSE: KPEL (dots in name break URL)
    "MBENGINEERING": "MBEL",          # CDSL: MBENGINEERING → NSE: MBEL (confirmed Yahoo: MBEL.NS)
    "CAPITALNUMB":   "CNINFOTECH.BO",# BSE only — MUST include .BO suffix
    "KWALYPH":       "KPL.BO",       # BSE only — Kwality Pharmaceuticals
    "KWALITYPHARM":  "KPL.BO",       # BSE only — alternate CDSL spelling
    # ── AZADINDIA = Indian Bright Steel (BSE only) — NOT Azad Engineering
    # AZAD.NS = Azad Engineering (handled by ISIN_MAP in index.html)
    "AZADINDIA":     "AZADIND.BO",   # Indian Bright Steel Company Ltd — BSE: AZADIND
    # ── Merged banks ───────────────────────────────────────────────────
    "ORIENTBANK":    "PNB",
    "CORPBANK":      "UCOBANK",
    "SYNDIBANK":     "CANBK",
    "ANDHRBANK":     "UCOBANK",
    "ALLBANK":       "INDIANB",
    "DENABANK":      "BANKBARODA",
    "VIJAYABANK":    "BANKBARODA",
    # ── Special characters — URL-encode & as %26 ───────────────────────
    "M&M":           "M%26M",
    "M&MFIN":        "M%26MFIN",
    # ── MCDOWELL-N: hyphen silently breaks yfinance — use safe alias ───
    "MCDOWELL-N":    "UNITDSPR",     # United Spirits Ltd, same company
    # ── BSE-only stocks — no .NS listing on Yahoo ─────────────────────
    "TITANBIOTE":    "TITANBIO.BO",
    "HIGHENERGYB":   "HIGHENE.BO",   # Symbol HIGHENE not HIGHENERGYB
    "SIKAINTERP":    "SIKA.BO",      # Symbol SIKA not SIKAINTERP
    "SKMEPEX":       "SKMEGGPROD",   # NSE: SKMEGGPROD
    "SHREEREFRI":    "SHREEREF.BO",  # IPO Jul 2025, BSE only
    # ── S&SPOWER: & must be URL-encoded as %26 ────────────────────────
    "SSPOWERSWIT":   "S%26SPOWER",
    # ── CDSL truncation — confirmed Yahoo tickers, no name-search needed ─
    "REVATHI":       "RVTH",         # REVATHI EQUIPMENT INDIA L → RVTH.NS
    "IGI":           "IGIL",         # INTERNATIO GEMM INS (I) L → IGIL.NS
    "SUYOGTELE":     "SUYOG",        # Suyog Telematics Ltd → SUYOG.NS
    "QUALPOWER":     "QPOWER",       # QUALITY POWER ELEC EQUP L → QPOWER.NS
    "CELLOWORLD":    "CELLO",        # CELLO WORLD LIMITED → CELLO.NS
    "HINDRECTIF":    "HIRECT",       # Hind Rectifiers Ltd → HIRECT.NS
}

# Runtime alias cache — populated by yahoo_search_sym during run
YF_ALIAS_CACHE = {}

def resolve_yf_sym(nse_sym):
    """Return the correct Yahoo Finance ticker for an NSE symbol."""
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
    """Search Yahoo Finance API to find correct ticker when standard .NS fails."""
    if cdsl_name:
        queries = [cdsl_name]
    else:
        queries = [nse_sym, nse_sym + " NSE", nse_sym[:6]]

    for q_str in queries:
        try:
            url = (f"https://query2.finance.yahoo.com/v1/finance/search"
                   f"?q={requests.utils.quote(q_str)}&lang=en-IN&region=IN&quotesCount=8&newsCount=0"
                   f"&enableFuzzyQuery=true&enableEnhancedTrivialQuery=true")
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue
            quotes = r.json().get("quotes", [])
            for q in quotes:
                sym_yf = q.get("symbol", "")
                exch   = q.get("exchange", "")
                qtype  = q.get("quoteType", "")
                if (sym_yf.endswith(".NS") or sym_yf.endswith(".BO")) and qtype in ("EQUITY", ""):
                    print(f"  🔍 {nse_sym} → {sym_yf} (via search)")
                    YF_ALIAS_CACHE[nse_sym] = sym_yf
                    NSE_TO_YAHOO[nse_sym] = sym_yf.replace(".NS","").replace(".BO","")
                    return sym_yf
        except Exception as e:
            print(f"  ⚠ Yahoo search '{q_str}': {e}")
        time.sleep(0.2)
    return None

# ── Helpers ────────────────────────────────────────────
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
    """Convert raw value (in INR) to Crores."""
    return round(v / 1e7, 2) if v else None

CDSL_NAMES = {}

def load_symbols():
    """Read portfolio_symbols.txt and watchlist.txt."""
    global CDSL_NAMES
    syms = []
    seen = set()

    if Path(PORTFOLIO_FILE).exists():
        lines = Path(PORTFOLIO_FILE).read_text().splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                sym, cdsl_name = line.split("|", 1)
                sym = sym.strip().upper()
                cdsl_name = cdsl_name.strip()
            else:
                sym = line.strip().upper()
                cdsl_name = ""
            if sym and sym not in SKIP and sym not in seen:
                syms.append(sym)
                seen.add(sym)
                if cdsl_name:
                    CDSL_NAMES[sym] = cdsl_name
        print(f"📂 {len(syms)} symbols from {PORTFOLIO_FILE}")
        if CDSL_NAMES:
            print(f"   ✓ {len(CDSL_NAMES)} have CDSL company names for Yahoo search")
    else:
        print(f"⚠  {PORTFOLIO_FILE} not found — using watchlist.txt only")
        print(f"   → Export from app: Portfolio tab ▸ ⬇ Export Symbols ▸ commit file to repo")

    if Path(WATCHLIST_FILE).exists():
        extras = 0
        for s in Path(WATCHLIST_FILE).read_text().splitlines():
            s = s.strip().upper()
            if s and not s.startswith("#") and s not in SKIP and s not in seen:
                syms.append(s)
                seen.add(s)
                extras += 1
        if extras:
            print(f"📋 +{extras} extra symbols from {WATCHLIST_FILE}")

    print(f"🔢 Total: {len(syms)} symbols\n")
    return syms

# ── Source 1: Yahoo Finance ────────────────────────────
def fetch_yfinance(sym):
    result = {}
    try:
        yf_sym = resolve_yf_sym(sym)
        t = yf.Ticker(yf_sym)

        hist_short = None
        try:
            hist_short = t.history(period="1mo", interval="1d", auto_adjust=True)
        except Exception:
            pass

        if hist_short is None or hist_short.empty:
            print(f"  ⚠ {sym}: {yf_sym} not found — searching Yahoo for correct ticker...")
            found_sym = yahoo_search_sym(sym, cdsl_name=CDSL_NAMES.get(sym))
            if found_sym:
                yf_sym = found_sym
                t = yf.Ticker(yf_sym)
                try:
                    hist_short = t.history(period="1mo", interval="1d", auto_adjust=True)
                except Exception:
                    hist_short = None

        if hist_short is None or hist_short.empty:
            try:
                bo_sym = sym + ".BO"
                t_bo = yf.Ticker(bo_sym)
                hist_bo = t_bo.history(period="1mo", interval="1d", auto_adjust=True)
                if hist_bo is not None and not hist_bo.empty:
                    print(f"  ⚠ {sym}: using BSE ticker {bo_sym}")
                    yf_sym = bo_sym
                    t = t_bo
                    hist_short = hist_bo
                    YF_ALIAS_CACHE[sym] = bo_sym
                else:
                    print(f"  ✗ {sym}: not found on NSE or BSE — skipping")
                    return result
            except Exception:
                print(f"  ✗ {sym}: not found on Yahoo Finance — skipping")
                return result

        # fast_info: lightweight, no extra HTTP call — use for price fields
        # t.info: full data for fundamentals — single call, cached by yfinance
        info = {}
        try:
            info = t.info or {}
        except Exception:
            pass

        # Try fast_info first for price (faster), fall back to info
        ltp, prev = None, None
        try:
            fi  = t.fast_info
            ltp = safe_float(getattr(fi, "last_price", None))
            prev= safe_float(getattr(fi, "previous_close", None))
        except Exception:
            pass
        if not ltp:
            ltp  = safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
            prev = safe_float(info.get("previousClose"))

        if not ltp:
            closes = hist_short["Close"].dropna()
            if not closes.empty:
                ltp  = round(float(closes.iloc[-1]), 2)
                prev = round(float(closes.iloc[-2]), 2) if len(closes) >= 2 else ltp
                print(f"  ⚠ history price fallback: ₹{ltp}")

        if not ltp:
            print(f"  ✗ yfinance {sym}: no price data")
            return result

        result["ltp"]   = ltp
        result["prev"]  = prev
        result["chg1d"] = round((ltp - prev) / prev * 100, 2) if prev else 0
        result["w52h"]  = safe_float(info.get("fiftyTwoWeekHigh"))
        result["w52l"]  = safe_float(info.get("fiftyTwoWeekLow"))
        result["name"]  = info.get("longName") or info.get("shortName") or sym
        result["sector"]= info.get("sector") or info.get("industryDisp") or ""

        result["pe"]      = safe_float(info.get("trailingPE"))
        result["fwd_pe"]  = safe_float(info.get("forwardPE"))
        result["pb"]      = safe_float(info.get("priceToBook"))
        result["eps"]     = safe_float(info.get("trailingEps"))
        result["bv"]      = safe_float(info.get("bookValue"))
        result["beta"]    = safe_float(info.get("beta"))

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

        result["mcap"]  = to_cr(info.get("marketCap"))
        result["sales"] = to_cr(info.get("totalRevenue"))
        result["ebitda"]= to_cr(info.get("ebitda"))
        result["cfo"]   = to_cr(info.get("operatingCashflow"))
        result["fcf"]   = to_cr(info.get("freeCashflow"))

        de = safe_float(info.get("debtToEquity"))
        result["debt_eq"]   = round(de / 100, 2) if de is not None else None
        result["cur_ratio"] = safe_float(info.get("currentRatio"))

        if result.get("w52h") and ltp:
            result["w52_pct"] = round((ltp / result["w52h"] - 1) * 100, 1)

        # ATH: use 52W high as proxy — 5Y history removed (saved ~0.5s per stock)
        result["ath"]     = result.get("w52h")
        result["ath_pct"] = result.get("w52_pct")

        try:
            closes_5d = hist_short["Close"].dropna().values
            if len(closes_5d) >= 5:
                result["chg5d"] = round(
                    (closes_5d[-1] - closes_5d[-5]) / closes_5d[-5] * 100, 2
                )
        except:
            pass

        insider = safe_float(info.get("heldPercentInsiders"))
        if insider:
            result["yf_insider_pct"] = round(insider * 100, 2)

        # ── Quarterly history for chart overlays ──────────────────────
        try:
            q_data = {}
            def qkey(d): return str(d)[:10]

            # ── Income statement: try every known attribute name ──────
            qf = None
            for attr in ['quarterly_income_stmt', 'quarterly_financials']:
                try:
                    df = getattr(t, attr, None)
                    if df is not None and not df.empty:
                        qf = df
                        break
                except Exception as ex:
                    print(f"  ⚠ {sym} {attr}: {ex}")

            if qf is not None:
                for row_label in qf.index:
                    rl = str(row_label).lower().strip()
                    for col in qf.columns:
                        k = qkey(col)
                        if k not in q_data: q_data[k] = {}
                        raw = qf.loc[row_label, col]
                        try:
                            v = float(raw)
                            if v != v: continue  # nan
                        except (TypeError, ValueError):
                            continue
                        if   rl == 'total revenue':                    q_data[k]['rev']   = round(v/1e7, 2)
                        elif rl == 'operating revenue':                q_data[k].setdefault('rev', round(v/1e7, 2))
                        elif rl == 'net income':                       q_data[k]['net']   = round(v/1e7, 2)
                        elif rl == 'basic eps':                        q_data[k]['eps']   = round(v, 2)
                        elif rl == 'diluted eps':                      q_data[k].setdefault('eps', round(v, 2))
                        elif rl == 'ebitda' or rl == 'normalized ebitda': q_data[k]['ebitda']= round(v/1e7, 2)
                        elif rl == 'ebit':                             q_data[k]['ebit']  = round(v/1e7, 2)
                        elif rl == 'gross profit':                     q_data[k]['gross'] = round(v/1e7, 2)
                        elif rl == 'operating income' or rl == 'operating profit': q_data[k].setdefault('ebit', round(v/1e7, 2))
            else:
                print(f"  ⚠ {sym}: no income stmt data")

            # ── Cash flow ──────────────────────────────────────────────
            qc = None
            for attr in ['quarterly_cash_flow', 'quarterly_cashflow']:
                try:
                    df = getattr(t, attr, None)
                    if df is not None and not df.empty:
                        qc = df
                        print(f"  📊 {sym} cashflow rows: {[str(r) for r in df.index]}")
                        break
                except Exception as ex:
                    print(f"  ⚠ {sym} {attr}: {ex}")

            if qc is not None:
                for row_label in qc.index:
                    rl = str(row_label).lower().strip()
                    for col in qc.columns:
                        k = qkey(col)
                        if k not in q_data: q_data[k] = {}
                        try:
                            v = float(qc.loc[row_label, col])
                            if v != v: continue
                        except (TypeError, ValueError):
                            continue
                        if any(x in rl for x in ('operating cash flow',
                                                  'cash from operations',
                                                  'cash flow from continuing operating',
                                                  'net cash from operating',
                                                  'cash flows from operations')):
                            q_data[k]['cfo'] = round(v/1e7, 2)
                        elif 'free cash flow' in rl:
                            q_data[k]['fcf'] = round(v/1e7, 2)

            # Check if CFO was populated; if not, try direct row search
            cfo_missing = any('cfo' not in v for v in q_data.values() if v)
            if cfo_missing and qc is not None:
                for row_label in qc.index:
                    rl = str(row_label).lower().strip()
                    if 'operating' in rl and ('cash' in rl or 'flow' in rl):
                        print(f"  🔍 {sym} CFO fallback row: '{row_label}'")
                        for col in qc.columns:
                            k = qkey(col)
                            if k not in q_data: q_data[k] = {}
                            try:
                                v = float(qc.loc[row_label, col])
                                if v != v: continue
                                q_data[k].setdefault('cfo', round(v/1e7, 2))
                            except (TypeError, ValueError):
                                continue
                        break

            # ── Balance sheet ──────────────────────────────────────────
            qb = None
            for attr in ['quarterly_balance_sheet', 'quarterly_balancesheet']:
                try:
                    df = getattr(t, attr, None)
                    if df is not None and not df.empty:
                        qb = df
                        break
                except Exception as ex:
                    print(f"  ⚠ {sym} {attr}: {ex}")

            if qb is not None:
                for row_label in qb.index:
                    rl = str(row_label).lower().strip()
                    if rl in ('total debt', 'long term debt', 'current debt', 'net debt'):
                        for col in qb.columns:
                            k = qkey(col)
                            if k not in q_data: q_data[k] = {}
                            try:
                                v = float(qb.loc[row_label, col])
                                if v != v: continue
                                q_data[k]['debt'] = round(v/1e7, 2)
                            except (TypeError, ValueError):
                                continue
                        break

            # ── Compute derived fields ─────────────────────────────────
            for k, v in q_data.items():
                if v.get('ebit') and v.get('rev') and v['rev'] != 0:
                    v['opm'] = round(v['ebit'] / v['rev'] * 100, 1)

            # ── Save only quarters that have at least one data field ───
            if q_data:
                quarters = sorted(
                    [(k, v) for k, v in q_data.items() if len(v) > 0],
                )[-12:]
                if quarters:
                    result['quarterly'] = [{'d': k, **v} for k, v in quarters]
                    fields = set(f for _, v in quarters for f in v if f != 'd')
                    print(f"  ✓ {sym} quarterly: {len(quarters)}Q fields={fields}")
                else:
                    print(f"  ⚠ {sym} quarterly: q_data has keys but all empty")
            else:
                print(f"  ⚠ {sym} quarterly: q_data empty — income stmt returned no matching rows")

        except Exception as e:
            pass  # quarterly optional

        print(
            f"  ✓ yfinance {sym}: ₹{ltp} | "
            f"P/E:{result.get('pe') or '—'} | "
            f"ROE:{result.get('roe') or '—'}% | "
            f"OPM:{result.get('opm_pct') or '—'}%"
        )

    except Exception as e:
        print(f"  ✗ yfinance {sym}: {e}")

    return result


# ── Source 3: Screener.in ──────────────────────────────
# Module-level Screener session — created once, reused for all stocks
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
        r   = sess.get(url, timeout=15)
        if r.status_code == 404:
            url = f"https://www.screener.in/company/{sym}/"
            r   = sess.get(url, timeout=15)
        if r.status_code != 200:
            return result
        soup = BeautifulSoup(r.text, "html.parser")

        # Top ratios
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
                if "roce" in lbl:          result.setdefault("roce",    val)
                elif "p/e" in lbl:         result.setdefault("pe",      val)
                elif "p/b" in lbl:         result.setdefault("pb",      val)
                elif "roe" in lbl:         result.setdefault("roe",     val)
                elif "market cap" in lbl:  result.setdefault("mcap",    val)
                elif "sales" in lbl:       result.setdefault("sales",   val)

        # Shareholding table
        # Screener columns: Label | Q(oldest) ... Q(latest) | Change
        # THE FIX: use second-to-last numeric value = latest quarter
        # Last value = QoQ change column (can be negative or zero — was causing wrong 0.0)
        sh = soup.find("section", id="shareholding")
        if sh:
            tbl = sh.find("table")
            if tbl:
                for row in tbl.find_all("tr"):
                    cells = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
                    if len(cells) < 2:
                        continue
                    lbl = cells[0].strip().rstrip("+").strip().lower()

                    # Collect ALL numeric values from data columns
                    numeric_vals = []
                    for c in cells[1:]:
                        v = safe_float(c.replace("%","").replace(",","").strip())
                        if v is not None:
                            numeric_vals.append(v)

                    if not numeric_vals:
                        continue

                    # Second-to-last = latest quarter; last = change col (can be negative)
                    if len(numeric_vals) >= 2:
                        val = numeric_vals[-2]
                    else:
                        val = numeric_vals[0]

                    if "promoter" in lbl and "pledge" not in lbl:
                        result["prom_pct"] = val

                    elif "pledge" in lbl:
                        # Sanity check: pledge must be 0–100
                        if 0 <= val <= 100:
                            result["pledge_pct"] = val
                        else:
                            # Fallback: try last column value
                            last = numeric_vals[-1]
                            if 0 <= last <= 100:
                                result["pledge_pct"] = last

                    elif "public" in lbl:
                        result.setdefault("public_pct", val)
                    elif "fii" in lbl or "fpi" in lbl or "foreign" in lbl:
                        result.setdefault("fii_pct", val)
                    elif "dii" in lbl or "institution" in lbl:
                        result.setdefault("dii_pct", val)

        # P&L table
        pl = soup.find("section", id="profit-loss")
        if pl:
            tbl = pl.find("table")
            if tbl:
                for row in tbl.find_all("tr"):
                    cells = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
                    if len(cells) < 2:
                        continue
                    lbl = cells[0].lower()
                    val = safe_float(cells[-1].replace("%","").replace(",",""))
                    if val is None:
                        continue
                    if "opm" in lbl:                                    result.setdefault("opm_pct",val)
                    elif "npm" in lbl:                                  result.setdefault("npm_pct",val)
                    elif lbl.startswith("sales") or "revenue" in lbl:  result.setdefault("sales",  val)

        # Cash flow
        cf = soup.find("section", id="cash-flow")
        if cf:
            tbl = cf.find("table")
            if tbl:
                for row in tbl.find_all("tr"):
                    cells = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
                    if len(cells) < 2:
                        continue
                    if "operating" in cells[0].lower():
                        val = safe_float(cells[-1].replace(",",""))
                        if val is not None:
                            result.setdefault("cfo", val)

        if result:
            print(f"  ✓ Screener {sym}: {len(result)} gap fields filled")

    except Exception as e:
        print(f"  ⚠ Screener {sym}: {e}")

    return result

# ── Signal ─────────────────────────────────────────────
def compute_signal(d):
    pos = 0
    neg = 0

    def check(field, good_fn, bad_fn):
        nonlocal pos, neg
        v = d.get(field)
        if v is None or v == 0:
            return
        if good_fn(v):
            pos += 1
        elif bad_fn(v):
            neg += 1

    check("roe",       lambda v: v > 15,       lambda v: v < 8)
    check("pe",        lambda v: 0 < v < 18,   lambda v: v > 35)
    check("opm_pct",   lambda v: v > 15,        lambda v: 0 < v < 8)
    check("npm_pct",   lambda v: v > 10,        lambda v: 0 < v < 5)
    check("prom_pct",  lambda v: v > 50,        lambda v: 0 < v < 35)
    check("chg1d",     lambda v: v > 1,         lambda v: v < -1)
    check("ath_pct",   lambda v: v > -10,       lambda v: v < -20)
    check("debt_eq",   lambda v: v < 0.5,       lambda v: v > 1.5)

    net = pos - neg
    sig = "BUY" if net >= 3 else "SELL" if net <= -3 else "HOLD"
    return sig, pos, neg


# ── Main ───────────────────────────────────────────────
def main():
    syms = load_symbols()
    ts   = now_utc()
    print(f"📊 BharatMarkets Fundamentals v3 | {ts.strftime('%Y-%m-%d %H:%M UTC')}\n")

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
    stats  = {"yf": 0, "scr": 0, "errors": 0}
    yf_results = {}

    # ── Phase 1: Parallel yfinance ──
    active_syms = [s for s in syms if s not in DELISTED]
    print(f"⚡ Fetching {len(active_syms)} stocks in parallel (8 workers)…\n")

    from concurrent.futures import ThreadPoolExecutor, as_completed
    lock = __import__("threading").Lock()
    done_count = [0]

    def fetch_one(sym):
        data = fetch_yfinance(sym)
        with lock:
            done_count[0] += 1
            elapsed = (now_utc() - ts).seconds
            if done_count[0] % 10 == 0:
                print(f"  ── {done_count[0]}/{len(active_syms)} done | {elapsed}s elapsed ──")
        time.sleep(YF_DELAY)
        return sym, data

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_one, sym): sym for sym in active_syms}
        for fut in as_completed(futures):
            sym, data = fut.result()
            yf_results[sym] = data

    print(f"\n✓ Phase 1 done in {(now_utc()-ts).seconds}s\n")

    # ── Phase 2: Sequential Screener + merge ──
    for i, sym in enumerate(syms):
        print(f"[{i+1}/{len(syms)}] {sym}", end=" | ", flush=True)

        if sym in DELISTED:
            print(f"↷ known delisted — skipped")
            continue

        stock = {}

        yf_data = yf_results.get(sym, {})
        if yf_data:
            stock.update(yf_data)
            stats["yf"] += 1
        else:
            stats["errors"] += 1


        # Screener — prom% and pledge% always override; other fields gap-fill only
        if HAS_BS4:
            scr_data = fetch_screener_gaps(sym)
            if scr_data:
                for k, v in scr_data.items():
                    if k in ("prom_pct", "pledge_pct"):
                        if v is not None:
                            stock[k] = v
                    elif stock.get(k) is None and v is not None:
                        stock[k] = v
                stats["scr"] += 1
            time.sleep(SCR_DELAY)


        # prices.json fallback
        pq = prices.get(sym, {})
        fb = {
            "pe": pq.get("pe"), "pb": pq.get("pb"),
            "roe": pq.get("roe"), "eps": pq.get("eps"),
            "w52h": pq.get("w52h"), "w52l": pq.get("w52l"),
            "prom_pct": pq.get("promoter"),
            "beta": pq.get("beta"),
        }
        for k, v in fb.items():
            if stock.get(k) is None and v:
                stock[k] = v

        # Merge with existing
        merged = {**existing.get(sym, {})}
        for k, v in stock.items():
            if v is not None and v != "":
                merged[k] = v

        sig, pos, neg = compute_signal(merged)
        merged.update({
            "signal":  sig,
            "pos":     pos,
            "neg":     neg,
            "updated": ts.isoformat(),
        })
        result[sym] = merged

        filled = sum(1 for v in merged.values() if v not in (None, "", 0))
        print(f"{sig}({pos}B/{neg}S) {filled}f")

    output = {
        "updated":  ts.isoformat(),
        "count":    len(result),
        "sources":  stats,
        "delisted": sorted(DELISTED),
        "stocks":   result,
    }
    Path(FUND_FILE).write_text(
        json.dumps(output, separators=(",",":"), default=str)
    )

    print("=" * 50)
    print(f"✅ {len(result)} stocks written to {FUND_FILE}")
    print(f"   yfinance:{stats['yf']} | Screener:{stats['scr']} | errors:{stats['errors']}")
    print(f"🕐 {now_utc().strftime('%H:%M UTC')}\n")

if __name__ == "__main__":
    main()
