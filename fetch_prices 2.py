#!/usr/bin/env python3
"""
BharatMarkets Pro — Price & Chart Fetcher
Reads:  symbols.json  (source of truth)
        symbol_map.json (shared exchange overrides)
Writes: prices.json, charts/*.json
"""

import json, time, datetime, os
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("pip install yfinance")

SYMBOLS_FILE   = "unified-symbols.json"
SYMBOL_MAP_FILE= "symbol_map.json"
PRICES_FILE    = "prices.json"
CHARTS_DIR     = Path("charts")
CHARTS_DIR.mkdir(exist_ok=True)

def load_symbol_map():
    try:
        d = json.loads(Path(SYMBOL_MAP_FILE).read_text())
        overrides = d.get("overrides", {})
        indices   = d.get("indices",   {})
        return {**overrides, **indices}, set(indices.keys())
    except:
        return {}, set()

SYMBOL_MAP, INDICES = load_symbol_map()

def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)

def to_yf(sym):
    mapped = SYMBOL_MAP.get(sym)
    if mapped:
        return mapped if ("." in mapped or mapped.startswith("^")) else mapped + ".NS"
    return sym + ".NS"

def load_symbols():
    try:
        data = json.loads(Path(SYMBOLS_FILE).read_text())
    except:
        return [], []

    if isinstance(data, dict) and "symbols" in data:
        data = data["symbols"]
    
    for entry in data:
        if "ticker" in entry and "sym" not in entry:
            entry["sym"] = entry["ticker"]
        entry["resolved"] = True

    syms = [s["sym"] for s in data if s.get("sym") and s.get("resolved")]
    return syms, data

def safe(v, mult=1, dp=2):
    try:
        f = float(v) * mult
        if f != f or abs(f) == float('inf'): return None
        return round(f, dp)
    except: return None

def fetch_ticker(sym):
    yf_sym = to_yf(sym)
    t = yf.Ticker(yf_sym)
    try:
        hist_1m = t.history(period="1mo", interval="1d", auto_adjust=True)
        if hist_1m is None or hist_1m.empty:
            print(f"  ✗ {sym}: not found")
            return {}, None
    except:
        return {}, None
    try:    hist = t.history(period="5y", interval="1d", auto_adjust=True)
    except: hist = hist_1m
    try:    info = t.info or {}
    except: info = {}
    return info, hist

def build_quote(sym, info, hist):
    ltp  = safe(info.get("currentPrice") or info.get("regularMarketPrice"))
    prev = safe(info.get("previousClose"))
    if not ltp and hist is not None and not hist.empty:
        ltp  = round(float(hist["Close"].dropna().iloc[-1]), 2)
        prev = round(float(hist["Close"].dropna().iloc[-2]), 2) if len(hist)>=2 else ltp
    if not ltp: return None
    prev = prev or ltp
    chg  = round(ltp - prev, 2)
    pct  = round(chg / prev * 100, 3) if prev else 0
    return {
        "ticker": sym,
        "name": info.get("longName") or info.get("shortName") or sym,
        "sector": info.get("sector") or "",
        "ltp": ltp, "change": chg, "changePct": pct,
        "open": safe(info.get("open") or ltp), "high": safe(info.get("dayHigh") or ltp),
        "low": safe(info.get("dayLow") or ltp), "prev": prev,
        "vol": int(info.get("volume") or 0),
        "pe": safe(info.get("trailingPE")), "pb": safe(info.get("priceToBook")),
        "eps": safe(info.get("trailingEps")),
        "w52h": safe(info.get("fiftyTwoWeekHigh")), "w52l": safe(info.get("fiftyTwoWeekLow")),
        "beta": safe(info.get("beta")),
        "opm": safe(info.get("operatingMargins"), mult=100),
        "npm": safe(info.get("profitMargins"), mult=100),
    }

def build_chart(sym, hist):
    if hist is None or hist.empty: return
    bars = []
    for date, row in hist.iterrows():
        try:
            bars.append({"d":str(date.date()),
                "o":round(float(row["Open"]),2),"h":round(float(row["High"]),2),
                "l":round(float(row["Low"]),2), "c":round(float(row["Close"]),2),
                "v":int(row.get("Volume",0))})
        except: continue
    if bars:
        (CHARTS_DIR / f"{sym}.json").write_text(
            json.dumps({"sym":sym,"bars":bars}, separators=(",",":")))

def main():
    symbols, symbols_data = load_symbols()
    print(f"📊 BharatMarkets Price Fetch | {now_utc().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"📋 {len(symbols)} symbols\n")

    quotes = {}
    for sym in symbols:
        yf_sym = to_yf(sym)
        info = {}
        hist = None
        try:
            info = yf.Ticker(yf_sym).info or {}
            hist = yf.Ticker(yf_sym).history(period="5y", interval="1d", auto_adjust=True)
        except: pass
        
        q = build_quote(sym, info, hist)
        if q:
            quotes[sym] = q
            print(f"  ✓ {sym}: ₹{q['ltp']}")
        if hist is not None and not hist.empty:
            build_chart(sym, hist)

    Path(PRICES_FILE).write_text(
        json.dumps({
            "updated": now_utc().isoformat(),
            "lastLoadedAt": now_utc().isoformat(),
            "source": "yahoo_finance",
            "count": len(quotes),
            "quotes": quotes
        }, separators=(",",":")))
    
    print(f"\n✓ prices.json → {len(quotes)} quotes")
    print(f"\n✅ Done {now_utc().strftime('%H:%M UTC')}\n")

if __name__ == "__main__":
    main()
