#!/usr/bin/env python3
"""
SCREENER.IN DEBUG - Inspect actual HTML structure
Shows what tables exist and their content
Helps determine if data is in HTML or JavaScript
"""

import sys
import json
from datetime import datetime
from pathlib import Path

print("\n" + "="*80)
print("SCREENER.IN HTML DEBUG - Inspect Page Structure")
print("="*80)

# ============================================================================
# INSTALL & IMPORT
# ============================================================================
print("\n📦 Installing dependencies...")

import subprocess
for pkg in ["requests", "beautifulsoup4", "lxml"]:
    try:
        if pkg == "beautifulsoup4":
            __import__("bs4")
        else:
            __import__(pkg)
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", pkg, "-q"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

import requests
from bs4 import BeautifulSoup

# ============================================================================
# FETCH PAGE
# ============================================================================
print("🌐 Fetching Screener.in page...")

url = "https://www.screener.in/company/INFY/consolidated/"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

response = requests.get(url, headers=headers, timeout=15)
soup = BeautifulSoup(response.content, 'lxml')

print(f"✅ Page fetched: {response.status_code}")

# ============================================================================
# ANALYZE TABLES
# ============================================================================
print("\n" + "="*80)
print("TABLE ANALYSIS")
print("="*80)

tables = soup.find_all('table')
print(f"\nTotal tables found: {len(tables)}\n")

for idx, table in enumerate(tables):
    print(f"\n{'='*80}")
    print(f"TABLE #{idx}")
    print(f"{'='*80}")
    
    # Get table attributes
    table_id = table.get('id', 'No ID')
    table_class = table.get('class', 'No class')
    rows = table.find_all('tr')
    
    print(f"ID: {table_id}")
    print(f"Class: {table_class}")
    print(f"Rows: {len(rows)}")
    
    if len(rows) > 0:
        # Show first row
        first_row = rows[0]
        headers = [th.get_text(strip=True) for th in first_row.find_all(['th', 'td'])]
        print(f"First row headers/cells: {headers[:5]}...")
        
        # Show first 3 rows content
        print(f"\nFirst 3 rows:")
        for r_idx, row in enumerate(rows[:3]):
            cells = [td.get_text(strip=True) for td in row.find_all(['th', 'td'])]
            print(f"  Row {r_idx}: {cells[:5]}...")
    
    # Get preview of table text
    table_text = table.get_text(strip=True)[:200]
    print(f"\nText preview: {table_text}...")

# ============================================================================
# SEARCH FOR KEYWORDS IN PAGE
# ============================================================================
print("\n\n" + "="*80)
print("KEYWORD SEARCH IN PAGE")
print("="*80)

keywords = [
    'Sales', 'Revenue', 'Expenses', 'Operating Profit', 'Net Profit',
    'Assets', 'Liabilities', 'Equity', 'Current Assets', 'Fixed Assets',
    'Cash Flow', 'Operating Activities', 'Investing', 'Financing',
    'Balance Sheet', 'Income Statement', 'P&L', 'Profit & Loss'
]

page_text = soup.get_text()

print("\nKeywords found in page:")
found_keywords = {}
for keyword in keywords:
    if keyword.lower() in page_text.lower():
        count = page_text.lower().count(keyword.lower())
        found_keywords[keyword] = count
        print(f"  ✅ '{keyword}': {count} times")

# ============================================================================
# CHECK FOR JAVASCRIPT DATA
# ============================================================================
print("\n\n" + "="*80)
print("JAVASCRIPT & DATA DETECTION")
print("="*80)

# Look for script tags
scripts = soup.find_all('script')
print(f"\nTotal script tags: {len(scripts)}")

# Look for JSON data in scripts
json_data_found = False
for idx, script in enumerate(scripts):
    script_text = script.get_text()
    
    # Check if contains JSON-like data
    if '{' in script_text and ':' in script_text:
        # Sample of the script
        sample = script_text[:300]
        if 'window' in sample or 'data' in sample or 'var' in sample:
            print(f"\n✅ Script #{idx} contains potential data:")
            print(f"   Sample: {sample}...")
            json_data_found = True
            break

if json_data_found:
    print("\n⚠️  Data appears to be loaded via JavaScript!")
    print("    Will need Selenium or API approach")
else:
    print("\n✅ No JavaScript data detected")

# ============================================================================
# LOOK FOR DATA IN HTML ATTRIBUTES
# ============================================================================
print("\n\n" + "="*80)
print("DATA ATTRIBUTES & HIDDEN ELEMENTS")
print("="*80)

# Look for data attributes
all_tags = soup.find_all(True)
data_attrs_found = 0

for tag in all_tags:
    for attr in tag.attrs:
        if 'data-' in attr:
            data_attrs_found += 1
            if data_attrs_found <= 5:
                print(f"✅ Found data attribute: {attr}")

print(f"\nTotal data attributes: {data_attrs_found}")

# Look for hidden divs with data
hidden_elements = soup.find_all(['div', 'span'], style=lambda x: x and 'display:none' in x)
print(f"Hidden elements with display:none: {len(hidden_elements)}")

# ============================================================================
# SAVE DEBUG INFO
# ============================================================================
print("\n\n" + "="*80)
print("SAVING DEBUG INFORMATION")
print("="*80)

output_dir = Path("screener_debug")
output_dir.mkdir(exist_ok=True)

debug_info = {
    "timestamp": datetime.now().isoformat(),
    "url": url,
    "status_code": response.status_code,
    "content_length": len(response.text),
    "tables_found": len(tables),
    "keywords_found": found_keywords,
    "scripts_detected": len(scripts),
    "javascript_data_detected": json_data_found,
    "data_attributes": data_attrs_found,
    "recommendations": []
}

# Add recommendations
if json_data_found:
    debug_info["recommendations"].append("Use Selenium for JavaScript rendering")
    debug_info["recommendations"].append("Look for API endpoints")
    debug_info["recommendations"].append("Check Network tab in browser")
else:
    debug_info["recommendations"].append("Data might be in table attributes")
    debug_info["recommendations"].append("Try different parsing approach")
    debug_info["recommendations"].append("Inspect individual table structures")

# Save full HTML for inspection
html_file = output_dir / "page_source.html"
with open(html_file, "w", encoding='utf-8') as f:
    f.write(response.text)
print(f"✅ Full HTML saved to: {html_file}")

# Save debug info
debug_file = output_dir / "debug_info.json"
with open(debug_file, "w") as f:
    json.dump(debug_info, f, indent=2)
print(f"✅ Debug info saved to: {debug_file}")

# ============================================================================
# RECOMMENDATION
# ============================================================================
print("\n\n" + "="*80)
print("NEXT STEPS")
print("="*80)

print("""
To understand the data loading mechanism:

1. OPEN IN BROWSER:
   Open: https://www.screener.in/company/INFY/consolidated/
   
2. RIGHT-CLICK → INSPECT (or F12):
   - Go to Network tab
   - Reload page
   - Look for API calls (XHR/Fetch)
   - Check what endpoints are called for financial data
   
3. CHECK CONSOLE:
   - Look for JavaScript errors
   - See what data is available in window object
   
4. LOOK FOR:
   - API endpoints returning JSON
   - Alternative data sources
   - React/Vue data stores

DEBUG FILES SAVED:
- screener_debug/page_source.html (full HTML)
- screener_debug/debug_info.json (analysis results)

POSSIBLE SOLUTIONS:
✅ Option 1: Find and use API endpoints (fastest)
✅ Option 2: Use Selenium to render JavaScript
✅ Option 3: Parse HTML attributes/data differently
❌ Option 4: Manual export via Screener UI (too slow)
""")

print("="*80)
print("Debug complete - Check browser DevTools for next clues!")
print("="*80 + "\n")
