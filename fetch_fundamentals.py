#!/usr/bin/env python3
"""
BharatMarkets Pro — Fundamentals Fetcher v3
============================================
Reads symbols from:
  1. portfolio_symbols.txt  (exported from app — YOUR actual portfolio)
  2. watchlist.txt          (fallback / extras)

Sources for data:
  1. Yahoo Finance (yfinance) — primary, most fields
  2. NSE India API            — promoter%, pledge%, FII%, DII%
  3. Screener.in              — fills remaining gaps

Writes: fundamentals.json
"""

import json, time, datetime, re
from pathlib import Path

try:
    import yfinance as yf
    import logging
    # Suppress yfinance noise for delisted/404 symbols
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    logging.getLogger("peewee").setLevel(logging.CRITICAL)
except ImportError:
    raise SystemExit("pip install yfinance")

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    print("pip install requests beautifulsoup4 lxml  — Screener disabled")

WATCHLIST_FILE  = "watchlist.txt"
PORTFOLIO_FILE  = "portfolio_symbols.txt"   # committed from app
PRICES_FILE     = "prices.json"
FUND_FILE       = "fundamentals.json"
YF_DELAY        = 0.6
SCR_DELAY       = 0.5

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
    "AZADINDIA":     "AZAD",         # Azad Engineering (NSE: AZAD)
    "MINDTREE":      "LTIM",         # Merged into LTIMindtree
    "LTIMINDTREE":   "LTIM",
    "HDFC":          "HDFCBANK",     # Post-merger
    "RUCHI":         "RUCHISOYA",
    "CAPITALNUMB":   "CNINFOTECH",   # CapitalNumbers Infotech
    "BLACKBOXLIMI":  "BBOX",         # Black Box Ltd
    "KWALYPH":       "KWALITYPHARM", # Kwality Pharmaceuticals
    "MBENGINEERING": "MBENGINE",     # M&B Engineering
    # ── Merged banks ───────────────────────────────────────────────────
    "ORIENTBANK":    "PNB",
    "CORPBANK":      "UCOBANK",
    "SYNDIBANK":     "CANBK",
    "ANDHRBANK":     "UCOBANK",
    "ALLBANK":       "INDIANB",
    "DENABANK":      "BANKBARODA",
    "VIJAYABANK":    "BANKBARODA",
    # ── Special characters — URL-encode & as %26 ───────────────────────
    "M&M":           "M%26M",        # Yahoo requires & → %26
    "M&MFIN":        "M%26MFIN",
    # ── Wrong NSE symbol in CDSL vs actual NSE/Yahoo symbol ────────────
    "GRAUERWEIL":    "GRAUWEIL",     # CDSL: GRAUERWEIL  →  NSE/Yahoo: GRAUWEIL
    "ROSSELLTECH":   "ROSSTECH",     # CDSL: ROSSELLTECH →  NSE/Yahoo: ROSSTECH
    "INDOTECHTR":    "INDOTECH",     # CDSL: INDOTECHTR  →  NSE/Yahoo: INDOTECH
    "SHILCHAR":      "SHILCTECH",    # CDSL: SHILCHAR    →  NSE/Yahoo: SHILCTECH
    "HBLPOWER":      "HBLENGINE",    # Renamed HBL Power → HBL Engineering
    # ── BSE-only stocks: correct Yahoo symbol + .BO suffix ─────────────
    # These have NO .NS listing — Yahoo only has .BO
    "TITANBIOTE":    "TITANBIO.BO",  # overrides above — BSE only
    "HIGHENERGYB":   "HIGHENE.BO",   # CDSL: HIGHENERGYB → Yahoo: HIGHENE.BO
    "SIKAINTERP":    "SIKA.BO",      # CDSL: SIKAINTERP  → Yahoo: SIKA.BO
    "SKMEPEX":       "SKMEGGPROD",   # SKM Egg Products  → Yahoo: SKMEGGPROD.NS
    "SHREEREFRI":    "SHREEREF.BO",  # IPO Jul 2025, BSE only
    # ── S&SPOWER has & — must URL-encode ───────────────────────────────
    "SSPOWERSWIT":   "S%26SPOWER",   # S&S Power → Yahoo: S%26SPOWER.NS
}

# Runtime alias cache — populated by yahoo_search_sym during run
YF_ALIAS_CACHE = {}

def resolve_yf_sym(nse_sym):
    """Return the correct Yahoo Finance ticker for an NSE symbol.
    Rules:
    - If value already has .NS or .BO suffix, use as-is
    - If value has ^ prefix (index), use as-is
    - If value has %26 (URL-encoded &), append .NS — yfinance handles it
    - Otherwise append .NS
    """
    if nse_sym in YF_ALIAS_CACHE:
        v = YF_ALIAS_CACHE[nse_sym]
        return v if ("." in v or v.startswith("^")) else v + ".NS"
    if nse_sym in NSE_TO_YAHOO:
        v = NSE_TO_YAHOO[nse_sym]
        result = v if ("." in v or v.startswith("^")) else v + ".NS"
        YF_ALIAS_CACHE[nse_sym] = result
        return result
    # Default: try SYM.NS
    return nse_sym + ".NS"

def yahoo_search_sym(nse_sym, cdsl_name=None):
    """
    Search Yahoo Finance API to find correct ticker when standard .NS fails.
    Tries multiple search strategies:
    1. CDSL company name (if available) — most reliable, Yahoo understands full names
    2. Direct search by NSE symbol
    3. Search with "NSE" appended
    4. Shorter version of symbol
    """
    if not HAS_BS4:
        return None

    queries = []
    if cdsl_name:
        queries.append(cdsl_name)          # e.g. "QUALITY POWER ELEC EQUP L"
    queries += [nse_sym, nse_sym + " NSE", nse_sym[:6]]
    for q_str in queries:
        try:
            url = (f"https://query2.finance.yahoo.com/v1/finance/search"
                   f"?q={q_str}&lang=en-IN&region=IN&quotesCount=8&newsCount=0"
                   f"&enableFuzzyQuery=true&enableEnhancedTrivialQuery=true")
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue
            quotes = r.json().get("quotes", [])
            for q in quotes:
                sym_yf = q.get("symbol", "")
                exch   = q.get("exchange", "")
                qtype  = q.get("quoteType", "")
                # Accept NSE (.NS) or BSE (.BO) equity quotes
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

# Global dict: CDSL symbol → full company name from portfolio_symbols.txt
CDSL_NAMES = {}

def load_symbols():
    """
    Read portfolio_symbols.txt (format: SYM or SYM|CDSL Company Name).
    Fall back to watchlist.txt for extras (plain SYM format).
    Populates global CDSL_NAMES dict for Yahoo search fallback.
    Returns plain list of symbols.
    """
    global CDSL_NAMES
    syms = []
    seen = set()

    # 1. Portfolio symbols (priority)
    if Path(PORTFOLIO_FILE).exists():
        lines = Path(PORTFOLIO_FILE).read_text().splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Format: SYM|CDSL Company Name  or  plain SYM
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

    # 2. Watchlist extras (plain SYM only)
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
        # Resolve correct Yahoo ticker (handles renames, special chars)
        yf_sym = resolve_yf_sym(sym)
        t = yf.Ticker(yf_sym)

        # Try short history first — fastest way to confirm listing
        hist_short = None
        try:
            hist_short = t.history(period="1mo", interval="1d", auto_adjust=True)
        except Exception:
            pass

        # If empty — try Yahoo search to find correct ticker
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

        # Still empty after search — try BSE (.BO) as last resort
        if hist_short is None or hist_short.empty:
            try:
                bo_sym = sym + ".BO"   # FIX: was nse_sym (undefined), use sym
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

        info = {}
        try:
            info = t.info or {}
        except Exception:
            pass  # .info can 404 even when history works — that is fine

        ltp  = safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
        prev = safe_float(info.get("previousClose"))

        # Use history close as price fallback
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

        # Valuation
        result["pe"]      = safe_float(info.get("trailingPE"))
        result["fwd_pe"]  = safe_float(info.get("forwardPE"))
        result["pb"]      = safe_float(info.get("priceToBook"))
        result["eps"]     = safe_float(info.get("trailingEps"))
        result["bv"]      = safe_float(info.get("bookValue"))
        result["beta"]    = safe_float(info.get("beta"))

        # Dividend yield — yfinance returns as decimal (0.012 = 1.2%)
        dy = safe_float(info.get("dividendYield"), 0)
        result["div_yield"] = round(dy * 100, 2) if dy and dy < 1 else dy

        # ROE / ROA — yfinance returns as decimal (0.15 = 15%) FIX
        roe_raw = safe_float(info.get("returnOnEquity"))
        roa_raw = safe_float(info.get("returnOnAssets"))
        result["roe"] = round(roe_raw * 100, 2) if roe_raw is not None else None
        result["roa"] = round(roa_raw * 100, 2) if roa_raw is not None else None

        # Margins — yfinance returns as decimal FIX
        npm_raw = safe_float(info.get("profitMargins"))
        opm_raw = safe_float(info.get("operatingMargins"))
        gpm_raw = safe_float(info.get("grossMargins"))
        result["npm_pct"] = round(npm_raw * 100, 2) if npm_raw is not None else None
        result["opm_pct"] = round(opm_raw * 100, 2) if opm_raw is not None else None
        result["gpm_pct"] = round(gpm_raw * 100, 2) if gpm_raw is not None else None

        # Financials in Crores
        result["mcap"]  = to_cr(info.get("marketCap"))
        result["sales"] = to_cr(info.get("totalRevenue"))
        result["ebitda"]= to_cr(info.get("ebitda"))
        result["cfo"]   = to_cr(info.get("operatingCashflow"))
        result["fcf"]   = to_cr(info.get("freeCashflow"))

        # Debt/equity — yfinance gives as % (150 = 1.5x), normalise to ratio
        de = safe_float(info.get("debtToEquity"))
        result["debt_eq"]   = round(de / 100, 2) if de is not None else None
        result["cur_ratio"] = safe_float(info.get("currentRatio"))

        # 52W%
        if result.get("w52h") and ltp:
            result["w52_pct"] = round((ltp / result["w52h"] - 1) * 100, 1)

        # ATH from 5Y monthly (only fetched when symbol is confirmed listed)
        try:
            h5 = t.history(period="5y",  interval="1mo", auto_adjust=True)
            if not h5.empty:
                ath = float(h5["High"].max())
                result["ath"]     = round(ath, 2)
                result["ath_pct"] = round((ltp / ath - 1) * 100, 1)
            else:
                result["ath"]     = result.get("w52h")
                result["ath_pct"] = result.get("w52_pct")
        except:
            result["ath"]     = result.get("w52h")
            result["ath_pct"] = result.get("w52_pct")

        # 5D return — reuse hist_short (already fetched)
        try:
            closes_5d = hist_short["Close"].dropna().values
            if len(closes_5d) >= 5:
                result["chg5d"] = round(
                    (closes_5d[-1] - closes_5d[-5]) / closes_5d[-5] * 100, 2
                )
        except:
            pass

        # Promoter (yfinance insider = approximate promoter for IN stocks)
        insider = safe_float(info.get("heldPercentInsiders"))
        if insider:
            result["prom_pct"] = round(insider * 100, 2)

        print(
            f"  ✓ yfinance {sym}: ₹{ltp} | "
            f"P/E:{result.get('pe') or '—'} | "
            f"ROE:{result.get('roe') or '—'}% | "
            f"OPM:{result.get('opm_pct') or '—'}%"
        )

    except Exception as e:
        print(f"  ✗ yfinance {sym}: {e}")

    return result

# ── Source 2: NSE Shareholding API ────────────────────
def fetch_nse_shareholding(sym):
    result = {}
    if not HAS_BS4:
        return result
    try:
        sess = requests.Session()
        sess.headers.update(HEADERS)
        sess.get("https://www.nseindia.com", timeout=10)
        time.sleep(0.5)

        today = datetime.date.today()
        fd    = (today - datetime.timedelta(days=120)).strftime("%d-%m-%Y")
        td    = today.strftime("%d-%m-%Y")
        url   = (f"https://www.nseindia.com/api/corporate-shareholding-pattern"
                 f"?symbol={sym}&from={fd}&to={td}")
        r = sess.get(url, timeout=12)
        if r.status_code != 200:
            return result

        data = r.json()
        if not data:
            return result

        latest = data[0] if isinstance(data, list) else data

        MAP = {
            "prom_pct":   ["promoterAndPromoterGroupShareholding","promoterHolding"],
            "public_pct": ["publicShareholding","publicHolding"],
            "fii_pct":    ["foreignPortfolioInvestors","fii"],
            "dii_pct":    ["domesticInstitutionalInvestors","dii"],
            "pledge_pct": ["promoterAndPromoterGroupPledgedSharesPercentage","pledgedShares","pledge"],
        }
        for field, keys in MAP.items():
            for k in keys:
                v = safe_float(latest.get(k))
                if v is not None:
                    # normalise fraction → %
                    result[field] = round(v * 100, 2) if 0 < v < 1 else v
                    break

        if result:
            print(
                f"  ✓ NSE {sym}: "
                f"Prom:{result.get('prom_pct','—')}% "
                f"Pledge:{result.get('pledge_pct','—')}%"
            )
    except Exception as e:
        print(f"  ⚠ NSE {sym}: {e}")

    return result

# ── Source 3: Screener.in (gap filler only) ────────────
def fetch_screener_gaps(sym):
    result = {}
    if not HAS_BS4:
        return result
    try:
        sess = requests.Session()
        sess.headers.update(HEADERS)

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
        sh = soup.find("section", id="shareholding")
        if sh:
            tbl = sh.find("table")
            if tbl:
                for row in tbl.find_all("tr"):
                    cells = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
                    if len(cells) < 2:
                        continue
                    lbl = cells[0].lower()
                    val = safe_float(cells[-1].replace("%","").replace(",",""))
                    if val is None:
                        continue
                    if "promoter" in lbl and "pledge" not in lbl:
                        result.setdefault("prom_pct",  val)
                    elif "pledge" in lbl:
                        result.setdefault("pledge_pct",val)
                    elif "public" in lbl:
                        result.setdefault("public_pct",val)

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

# ── Signal — fixed, no walrus operator ────────────────
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
    check("pledge_pct",lambda v: v < 5,         lambda v: v > 20)
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

    # Load existing to merge
    existing = {}
    if Path(FUND_FILE).exists():
        try:
            d = json.loads(Path(FUND_FILE).read_text())
            existing = d.get("stocks", {})
            # Load previously confirmed delisted symbols — skip them instantly
            for sym in d.get("delisted", []):
                DELISTED.add(sym)
            print(f"♻  {len(existing)} existing | {len(DELISTED)} known-delisted\n")
        except:
            pass

    # Load prices.json fallback
    prices = {}
    if Path(PRICES_FILE).exists():
        try:
            prices = json.loads(Path(PRICES_FILE).read_text()).get("quotes", {})
        except:
            pass

    result = {}
    stats  = {"yf": 0, "nse": 0, "scr": 0, "errors": 0}

    for i, sym in enumerate(syms):
        # Progress indicator
        if i % 10 == 0:
            elapsed = (now_utc() - ts).seconds
            print(f"\n── Progress: {i}/{len(syms)} stocks | {elapsed}s elapsed ──")
        print(f"[{i+1}/{len(syms)}] {sym}", end=" | ", flush=True)

        # Skip known-delisted symbols instantly (no network call)
        if sym in DELISTED:
            print(f"  ↷ {sym}: known delisted — skipped\n")
            continue

        stock = {}

        # 1. Yahoo Finance (primary)
        yf_data = fetch_yfinance(sym)
        if yf_data:
            stock.update(yf_data)
            stats["yf"] += 1
        else:
            stats["errors"] += 1
        time.sleep(YF_DELAY)

        # 2. NSE shareholding — disabled (slow, yfinance provides prom% already)
        # stats["nse"] stays 0

        # 3. Screener.in — only if promoter% or pledge% missing
        # (opm, npm, cfo, roe all come from yfinance — no need to scrape)
        needs = stock.get("prom_pct") is None or stock.get("pledge_pct") is None
        if needs and HAS_BS4:
            scr_data = fetch_screener_gaps(sym)
            if scr_data:
                for k, v in scr_data.items():
                    if stock.get(k) is None and v is not None:
                        stock[k] = v
                stats["scr"] += 1
            time.sleep(SCR_DELAY)

        # 4. prices.json fallback
        pq = prices.get(sym, {})
        fb = {
            "pe": pq.get("pe"), "pb": pq.get("pb"),
            "roe": pq.get("roe"), "eps": pq.get("eps"),
            "w52h": pq.get("w52h"), "w52l": pq.get("w52l"),
            "prom_pct": pq.get("promoter"), "pledge_pct": pq.get("pledging"),
            "beta": pq.get("beta"),
        }
        for k, v in fb.items():
            if stock.get(k) is None and v:
                stock[k] = v

        # 5. Merge (existing values kept only if new run has nothing)
        merged = {**existing.get(sym, {})}
        for k, v in stock.items():
            if v is not None and v != "" and v != 0:
                merged[k] = v

        # 6. Signal
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

    # Write output
    output = {
        "updated":  ts.isoformat(),
        "count":    len(result),
        "sources":  stats,
        "delisted": sorted(DELISTED),   # persisted so next run skips instantly
        "stocks":   result,
    }
    Path(FUND_FILE).write_text(
        json.dumps(output, separators=(",",":"), default=str)
    )

    print("=" * 50)
    print(f"✅ {len(result)} stocks written to {FUND_FILE}")
    print(f"   yfinance:{stats['yf']} | NSE:{stats['nse']} | Screener:{stats['scr']} | errors:{stats['errors']}")
    print(f"🕐 {now_utc().strftime('%H:%M UTC')}\n")

if __name__ == "__main__":
    main()
