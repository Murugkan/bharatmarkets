"""
Diagnostic for AMFI-NAV 'ISIN not found' warnings.
Run in your pipeline (has network access there, unlike this sandbox).
Paste the missing ISINs into MISSING_ISINS and your unified-symbols.json path.
"""
import json
import urllib.request

MISSING_ISINS = [
    "INF090I01CU0", "INF109K01YT5", "INF109KB1YP8",
    "INF194KB1VY2", "INF204K01KD1", "INF209KB1UQ6", "INF251K01VQ3",
]

NAVALL_URL = "https://www.amfiindia.com/spages/NAVAll.txt"

def fetch_navall():
    req = urllib.request.Request(NAVALL_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")

def build_isin_index(navall_text):
    """Map every ISIN (both growth/payout col AND reinvestment col) -> scheme name."""
    payout_idx, reinvest_idx = {}, {}
    for line in navall_text.splitlines():
        parts = line.split(";")
        if len(parts) < 5 or parts[0].strip() == "Scheme Code":
            continue
        code, isin_payout, isin_reinvest, name = parts[0], parts[1], parts[2], parts[3]
        if isin_payout and isin_payout != "-":
            payout_idx[isin_payout.strip()] = name.strip()
        if isin_reinvest and isin_reinvest != "-":
            reinvest_idx[isin_reinvest.strip()] = name.strip()
    return payout_idx, reinvest_idx

def diagnose(isins, unified_symbols_path=None):
    text = fetch_navall()
    payout_idx, reinvest_idx = build_isin_index(text)

    registry_names = {}
    if unified_symbols_path:
        with open(unified_symbols_path) as f:
            reg = json.load(f)
        # adjust key names to match your actual schema
        for entry in reg if isinstance(reg, list) else reg.values():
            isin = entry.get("isin") or entry.get("ISIN")
            if isin:
                registry_names[isin] = entry.get("name") or entry.get("scheme_name")

    for isin in isins:
        in_payout = isin in payout_idx
        in_reinvest = isin in reinvest_idx
        reg_name = registry_names.get(isin, "(not found in registry / no path given)")
        if in_payout:
            status = f"FOUND as payout/growth col -> {payout_idx[isin]}  [check parser logic]"
        elif in_reinvest:
            status = f"FOUND but only in REINVESTMENT col -> {reinvest_idx[isin]}  [likely wrong ISIN stored — swap to payout/growth ISIN]"
        else:
            status = "NOT in today's NAVAll.txt at all -> likely matured/merged/delisted scheme"
        print(f"{isin} | registry name: {reg_name}")
        print(f"  -> {status}\n")

if __name__ == "__main__":
    diagnose(MISSING_ISINS)  # add unified_symbols_path="unified-symbols.json" when run in your pipeline
