“””
fetch_guidance.py
─────────────────
Quarterly run — for each portfolio stock:

1. Fetches last 30 days of Google News via RSS
1. Sends headlines + snippets to Claude API
1. Extracts structured forward guidance
1. Stores in guidance.json

Trigger: workflow_dispatch fetch_type=guidance
or manually after each results season
“””

import os, json, time, re, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

GUIDANCE_FILE = “guidance.json”
ANTHROPIC_URL = “https://api.anthropic.com/v1/messages”

def now_utc():
return datetime.now(timezone.utc)

def load_symbols():
“”“Load ONLY active portfolio symbols — not watchlist, not stale.”””
single = os.environ.get(“SINGLE_SYMBOL”,””).strip().upper()
if single:
return [single]

```
syms = []

# Only portfolio_symbols.txt — not watchlist (watchlist is research, not holdings)
p = Path("portfolio_symbols.txt")
if p.exists():
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        s = line.split("|")[0].strip().upper()  # handle SYM|Company Name format
        if s and s not in syms:
            syms.append(s)

if not syms:
    print("⚠ portfolio_symbols.txt not found or empty")
    return []

# Cross-check: only keep symbols that exist in fundamentals.json
# This excludes stale/removed symbols that were never properly fetched
active = set()
try:
    fund = json.loads(Path("fundamentals.json").read_text())
    active = set(fund.keys())
except:
    print("⚠ fundamentals.json not found — using all portfolio symbols")
    return syms

valid   = [s for s in syms if s in active]
skipped = [s for s in syms if s not in active]

if skipped:
    print(f"⚠ Skipping {len(skipped)} symbols not in fundamentals.json: {', '.join(skipped)}")

print(f"✓ {len(valid)} active portfolio symbols: {', '.join(valid)}")
return valid
```

def fetch_news_for_stock(sym, name=””):
“”“Fetch last 30 days news via Google News RSS”””
query = f”{sym} {name} NSE India earnings results guidance”.strip()
encoded = urllib.parse.quote(query)
url = f”https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en”

```
articles = []
try:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        xml_data = r.read()
    root = ET.fromstring(xml_data)
    channel = root.find("channel")
    if channel is None:
        return articles
    for item in channel.findall("item")[:12]:
        title = item.findtext("title","").strip()
        desc  = item.findtext("description","").strip()
        pub   = item.findtext("pubDate","")
        # Strip HTML tags from description
        desc  = re.sub(r"<[^>]+>","",desc).strip()[:300]
        if title:
            articles.append({
                "title": title,
                "desc":  desc,
                "pub":   pub,
            })
except Exception as e:
    print(f"  ⚠ News fetch failed for {sym}: {e}")
return articles
```

def call_claude(sym, name, articles):
“”“Call Claude API to extract forward guidance from news”””
api_key = os.environ.get(“ANTHROPIC_API_KEY”,””).strip()
if not api_key:
print(f”  ⚠ ANTHROPIC_API_KEY not set — skipping Claude call”)
return None

```
news_text = "\n".join([
    f"- [{a['pub'][:16]}] {a['title']}. {a['desc']}"
    for a in articles
])

prompt = f"""You are a financial analyst. Analyze this news coverage for {name} ({sym}) listed on NSE India.
```

Extract ONLY forward-looking information — management guidance, commitments, projections, and analyst estimates mentioned in recent earnings coverage.

News articles:
{news_text}

Respond with ONLY a JSON object in this exact format (no markdown, no explanation):
{{
“quarter”: “Q3FY25 or similar if mentioned, else null”,
“revenue_guidance”: “specific number or range if mentioned, else null”,
“margin_guidance”: “EBITDA/PAT margin target if mentioned, else null”,
“eps_estimate”: “forward EPS if analyst estimate mentioned, else null”,
“capex_plan”: “capex commitment if mentioned, else null”,
“growth_target”: “revenue/volume growth target if mentioned, else null”,
“key_commitments”: [“list of 2-3 specific forward commitments from management”],
“risks_flagged”: [“list of 1-2 key risks mentioned”],
“analyst_rating”: “Buy/Hold/Sell consensus if mentioned, else null”,
“price_target”: “analyst price target in INR if mentioned, else null”,
“tone”: “Positive/Neutral/Negative based on overall management tone”,
“confidence”: “High/Medium/Low based on how much forward data was found”,
“implied_fwd_growth”: null,
“summary”: “2 sentence max summary of forward outlook”
}}”””

```
body = json.dumps({
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 1000,
    "messages": [{"role": "user", "content": prompt}]
}).encode()

req = urllib.request.Request(
    ANTHROPIC_URL,
    data=body,
    headers={
        "Content-Type":      "application/json",
        "x-api-key":         api_key,
        "anthropic-version": "2023-06-01",
    },
    method="POST"
)

try:
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read())
    text = resp["content"][0]["text"].strip()
    # Strip markdown fences if present
    text = re.sub(r"^```json\s*","",text)
    text = re.sub(r"\s*```$","",text)
    result = json.loads(text)
    result["updated"] = now_utc().isoformat()
    result["sym"]     = sym
    return result
except Exception as e:
    print(f"  ⚠ Claude API error for {sym}: {e}")
    return None
```

def main():
syms = load_symbols()
print(f”📋 BharatMarkets Guidance Fetch”)
print(f”🕐 {now_utc().strftime(’%Y-%m-%d %H:%M UTC’)}”)
print(f”📊 {len(syms)} portfolio symbols\n”)

```
if not syms:
    print("Nothing to do.")
    return

# Load existing guidance
existing = {}
try:
    existing = json.loads(Path(GUIDANCE_FILE).read_text())
except:
    pass

# Remove stale entries — symbols no longer in portfolio
stale = [k for k in existing if k not in syms]
if stale:
    print(f"🧹 Removing {len(stale)} stale guidance entries: {', '.join(stale)}")
    for k in stale:
        del existing[k]

results = dict(existing)
success, skipped = 0, 0

for sym in syms:
    print(f"  → {sym}")

    # Skip if updated within last 60 days (don't re-fetch mid-quarter)
    if sym in existing:
        upd = existing[sym].get("updated","")
        try:
            age_days = (now_utc() - datetime.fromisoformat(upd)).days
            if age_days < 60:
                print(f"    ↳ Skipped (updated {age_days}d ago)")
                skipped += 1
                continue
        except:
            pass

    # Get company name from fundamentals.json if available
    name = sym
    try:
        fund = json.loads(Path("fundamentals.json").read_text())
        name = fund.get(sym,{}).get("name", sym)
    except:
        pass

    # Fetch news
    articles = fetch_news_for_stock(sym, name)
    print(f"    ↳ {len(articles)} articles found")
    if not articles:
        skipped += 1
        continue

    # Compute implied forward growth from existing fundamentals data
    try:
        fund_data = json.loads(Path("fundamentals.json").read_text())
        f = fund_data.get(sym, {})
        pe      = f.get("pe")
        fwd_pe  = f.get("fwd_pe")
        if pe and fwd_pe and pe > 0 and fwd_pe > 0:
            implied_growth = round((pe / fwd_pe - 1) * 100, 1)
        else:
            implied_growth = None
    except:
        implied_growth = None

    # Call Claude
    guidance = call_claude(sym, name, articles)
    if guidance:
        if implied_growth is not None:
            guidance["implied_fwd_growth"] = implied_growth
        results[sym] = guidance
        tone = guidance.get("tone","?")
        conf = guidance.get("confidence","?")
        print(f"    ✓ Tone:{tone} Confidence:{conf}")
        success += 1
    else:
        skipped += 1

    time.sleep(2)  # Rate limit

# Save
Path(GUIDANCE_FILE).write_text(
    json.dumps(results, indent=2, ensure_ascii=False)
)
print(f"\n✅ Done — {success} updated, {skipped} skipped")
print(f"📁 guidance.json → {len(results)} stocks")
```

if **name** == “**main**”:
main()
