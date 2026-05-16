#!/usr/bin/env python3
"""
SCREENER.IN FINANCIAL DATA EXTRACTION TEST
Tests real data extraction from Screener.in for INFY
- Fetches actual HTML
- Extracts Balance Sheet
- Extracts Income Statement (P&L)
- Extracts Cash Flow
- Extracts Quarterly Results
- Extracts Ratios
"""

import sys
import time
import json
from datetime import datetime
from pathlib import Path

print("\n" + "="*80)
print("SCREENER.IN FINANCIAL DATA - EXTRACTION TEST")
print("="*80)

# ============================================================================
# STEP 1: INSTALL & IMPORT DEPENDENCIES
# ============================================================================
print("\n📦 STEP 1: Installing dependencies...")
print("-" * 80)

import subprocess

packages = {
    "requests": "requests",
    "beautifulsoup4": "bs4",
    "pandas": "pandas",
    "lxml": "lxml"
}

for pip_pkg, import_name in packages.items():
    try:
        __import__(import_name)
        print(f"✅ {pip_pkg} ready")
    except ImportError:
        print(f"📥 Installing {pip_pkg}...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", pip_pkg, "-q"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print(f"✅ {pip_pkg} installed")

print("\n📋 Importing libraries...")
try:
    import requests
    from bs4 import BeautifulSoup
    import pandas as pd
    print("✅ All imports successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# ============================================================================
# STEP 2: FETCH SCREENER.IN PAGE
# ============================================================================
print("\n🌐 STEP 2: Fetching Screener.in page...")
print("-" * 80)

test_stock = "INFY"
url = f"https://www.screener.in/company/{test_stock}/consolidated/"

print(f"   URL: {url}")

try:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    response = requests.get(url, headers=headers, timeout=15)
    
    if response.status_code == 200:
        print(f"✅ Page fetched successfully")
        print(f"   Status: {response.status_code}")
        print(f"   Content length: {len(response.text)} bytes")
    else:
        print(f"❌ Failed to fetch page")
        print(f"   Status: {response.status_code}")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Connection error: {e}")
    sys.exit(1)

# ============================================================================
# STEP 3: PARSE HTML & FIND TABLES
# ============================================================================
print("\n🔍 STEP 3: Parsing HTML...")
print("-" * 80)

try:
    soup = BeautifulSoup(response.content, 'lxml')
    tables = soup.find_all('table')
    print(f"✅ Found {len(tables)} tables on page")
    
    # Show table headings to identify them
    print("\n   Table identification:")
    for i, table in enumerate(tables[:8]):  # Show first 8 tables
        # Get the table content
        text_preview = table.get_text()[:100].replace('\n', ' ').strip()
        print(f"   Table {i}: {text_preview}...")
        
except Exception as e:
    print(f"❌ Parsing error: {e}")
    sys.exit(1)

# ============================================================================
# STEP 4: EXTRACT QUARTERLY RESULTS
# ============================================================================
print("\n📊 STEP 4: Extracting Quarterly Results...")
print("-" * 80)

quarterly_results = {}

try:
    # Look for quarterly data - usually one of the first few tables
    for i, table in enumerate(tables[:5]):
        table_text = table.get_text()
        
        # Check if this looks like quarterly data
        if 'Sales' in table_text and 'Mar' in table_text and 'Jun' in table_text:
            print(f"   ✅ Found Quarterly Results in table #{i}")
            
            try:
                df = pd.read_html(str(table))[0]
                print(f"      Rows: {len(df)}")
                print(f"      Columns: {len(df.columns)}")
                
                # Show sample
                if len(df) > 0:
                    print(f"\n   Sample Quarterly Data:")
                    print(f"      Columns: {list(df.columns[:5])}")
                    
                    # Get first data row
                    for col in df.columns[:3]:
                        val = df.iloc[0][col]
                        print(f"      {col}: {val}")
                
                quarterly_results = {
                    'status': 'FOUND',
                    'rows': len(df),
                    'columns': len(df.columns),
                    'first_columns': list(df.columns[:10]),
                    'sample_row': df.iloc[0].to_dict() if len(df) > 0 else None
                }
                break
                
            except Exception as e:
                continue
    
    if not quarterly_results:
        quarterly_results = {'status': 'NOT_FOUND'}
        print(f"   ⚠️  Quarterly results not found in expected format")
        
except Exception as e:
    print(f"   ❌ Error: {str(e)[:100]}")
    quarterly_results = {'status': 'ERROR', 'error': str(e)}

time.sleep(1)

# ============================================================================
# STEP 5: EXTRACT PROFIT & LOSS (ANNUAL)
# ============================================================================
print("\n📈 STEP 5: Extracting Profit & Loss (Annual)...")
print("-" * 80)

profit_loss_results = {}

try:
    # P&L is usually after quarterly
    for i, table in enumerate(tables[4:12]):  # Check tables 4-12
        table_text = table.get_text()
        
        # Check if this looks like P&L data
        if ('Sales' in table_text and 'Mar' in table_text and 
            ('Operating Profit' in table_text or 'Net Profit' in table_text or 'Expenses' in table_text)):
            
            print(f"   ✅ Found P&L in table #{i+4}")
            
            try:
                df = pd.read_html(str(table))[0]
                print(f"      Rows: {len(df)}")
                print(f"      Columns: {len(df.columns)}")
                
                # Show sample
                if len(df) > 0:
                    print(f"\n   Sample P&L Data:")
                    print(f"      Columns: {list(df.columns[:5])}")
                    for col in df.columns[:3]:
                        val = df.iloc[0][col]
                        print(f"      {col}: {val}")
                
                profit_loss_results = {
                    'status': 'FOUND',
                    'rows': len(df),
                    'columns': len(df.columns),
                    'first_columns': list(df.columns[:10]),
                    'sample_row': df.iloc[0].to_dict() if len(df) > 0 else None
                }
                break
                
            except Exception as e:
                continue
    
    if not profit_loss_results:
        profit_loss_results = {'status': 'NOT_FOUND'}
        print(f"   ⚠️  P&L data not found in expected format")
        
except Exception as e:
    print(f"   ❌ Error: {str(e)[:100]}")
    profit_loss_results = {'status': 'ERROR', 'error': str(e)}

time.sleep(1)

# ============================================================================
# STEP 6: EXTRACT BALANCE SHEET
# ============================================================================
print("\n📊 STEP 6: Extracting Balance Sheet...")
print("-" * 80)

balance_sheet_results = {}

try:
    # Balance sheet is usually later in the page
    for i, table in enumerate(tables[10:20]):  # Check tables 10-20
        table_text = table.get_text()
        
        # Check if this looks like Balance Sheet
        if ('Assets' in table_text or 'Liabilities' in table_text or 'Equity' in table_text):
            
            print(f"   ✅ Found Balance Sheet in table #{i+10}")
            
            try:
                df = pd.read_html(str(table))[0]
                print(f"      Rows: {len(df)}")
                print(f"      Columns: {len(df.columns)}")
                
                # Show sample
                if len(df) > 0:
                    print(f"\n   Sample Balance Sheet Data:")
                    print(f"      Columns: {list(df.columns[:5])}")
                    for col in df.columns[:3]:
                        val = df.iloc[0][col]
                        print(f"      {col}: {val}")
                
                balance_sheet_results = {
                    'status': 'FOUND',
                    'rows': len(df),
                    'columns': len(df.columns),
                    'first_columns': list(df.columns[:10]),
                    'sample_row': df.iloc[0].to_dict() if len(df) > 0 else None
                }
                break
                
            except Exception as e:
                continue
    
    if not balance_sheet_results:
        balance_sheet_results = {'status': 'NOT_FOUND'}
        print(f"   ⚠️  Balance Sheet not found in expected format")
        
except Exception as e:
    print(f"   ❌ Error: {str(e)[:100]}")
    balance_sheet_results = {'status': 'ERROR', 'error': str(e)}

time.sleep(1)

# ============================================================================
# STEP 7: EXTRACT CASH FLOW
# ============================================================================
print("\n💰 STEP 7: Extracting Cash Flow...")
print("-" * 80)

cash_flow_results = {}

try:
    # Cash Flow is usually near the end
    for i, table in enumerate(tables[18:30]):  # Check tables 18-30
        table_text = table.get_text()
        
        # Check if this looks like Cash Flow
        if ('Cash Flow' in table_text or 'Operating Activities' in table_text or 
            'Investing' in table_text or 'Financing' in table_text):
            
            print(f"   ✅ Found Cash Flow in table #{i+18}")
            
            try:
                df = pd.read_html(str(table))[0]
                print(f"      Rows: {len(df)}")
                print(f"      Columns: {len(df.columns)}")
                
                # Show sample
                if len(df) > 0:
                    print(f"\n   Sample Cash Flow Data:")
                    print(f"      Columns: {list(df.columns[:5])}")
                    for col in df.columns[:3]:
                        val = df.iloc[0][col]
                        print(f"      {col}: {val}")
                
                cash_flow_results = {
                    'status': 'FOUND',
                    'rows': len(df),
                    'columns': len(df.columns),
                    'first_columns': list(df.columns[:10]),
                    'sample_row': df.iloc[0].to_dict() if len(df) > 0 else None
                }
                break
                
            except Exception as e:
                continue
    
    if not cash_flow_results:
        cash_flow_results = {'status': 'NOT_FOUND'}
        print(f"   ⚠️  Cash Flow not found in expected format")
        
except Exception as e:
    print(f"   ❌ Error: {str(e)[:100]}")
    cash_flow_results = {'status': 'ERROR', 'error': str(e)}

# ============================================================================
# STEP 8: EXTRACT KEY METRICS/RATIOS
# ============================================================================
print("\n📐 STEP 8: Extracting Key Metrics...")
print("-" * 80)

metrics_results = {}

try:
    # Look for key metrics in the page
    soup_text = soup.get_text()
    
    metrics_found = {}
    metric_keywords = ['P/E', 'PE', 'ROE', 'ROA', 'ROCE', 'Book Value', 'Dividend']
    
    for keyword in metric_keywords:
        if keyword in soup_text:
            metrics_found[keyword] = True
            print(f"   ✅ Found '{keyword}' metric on page")
    
    metrics_results = {
        'status': 'SUCCESS' if metrics_found else 'PARTIAL',
        'metrics_found': metrics_found
    }
    
except Exception as e:
    print(f"   ❌ Error: {str(e)[:100]}")
    metrics_results = {'status': 'ERROR', 'error': str(e)}

# ============================================================================
# STEP 9: COMPILE RESULTS
# ============================================================================
print("\n" + "="*80)
print("EXTRACTION TEST RESULTS")
print("="*80)

test_report = {
    "timestamp": datetime.now().isoformat(),
    "stock": test_stock,
    "url": url,
    "page_status": "✅ SUCCESS",
    "extraction_results": {
        "quarterly_results": quarterly_results,
        "profit_loss": profit_loss_results,
        "balance_sheet": balance_sheet_results,
        "cash_flow": cash_flow_results,
        "metrics": metrics_results
    },
    "total_tables_found": len(tables)
}

print(f"\n✅ Connectivity: Page accessible")
print(f"✅ Total tables: {len(tables)}")
print(f"\n📊 Quarterly Results: {quarterly_results.get('status', 'UNKNOWN')}")
print(f"📈 Profit & Loss: {profit_loss_results.get('status', 'UNKNOWN')}")
print(f"📊 Balance Sheet: {balance_sheet_results.get('status', 'UNKNOWN')}")
print(f"💰 Cash Flow: {cash_flow_results.get('status', 'UNKNOWN')}")
print(f"📐 Metrics: {metrics_results.get('status', 'UNKNOWN')}")

# ============================================================================
# STEP 10: SAVE RESULTS
# ============================================================================
print("\n💾 Saving test results...")
print("-" * 80)

output_dir = Path("screener_test_results")
output_dir.mkdir(exist_ok=True)

report_file = output_dir / f"screener_extraction_{test_stock}.json"
with open(report_file, "w") as f:
    json.dump(test_report, f, indent=2, default=str)

print(f"✅ Results saved to: {report_file}")

# ============================================================================
# RECOMMENDATIONS
# ============================================================================
print("\n" + "="*80)
print("ANALYSIS & RECOMMENDATIONS")
print("="*80)

success_count = sum(1 for r in test_report["extraction_results"].values() 
                   if r.get('status') == 'FOUND')

if success_count >= 3:
    print(f"""
✅ EXTRACTION SUCCESSFUL! ({success_count}/4 statements found)

Web scraping approach is VIABLE!

NEXT STEPS:
1. ✅ Screener.in pages are scrapeable
2. ✅ Tables are in standard HTML format
3. ✅ pandas.read_html() works perfectly
4. ✅ Data structure is consistent

READY FOR PRODUCTION:
- Create full scraper for all 97 stocks
- Extract Balance Sheet, Income Statement, Cash Flow
- Store 10 years of historical data
- Calculate ratios
- Export to JSON

APPROACH:
✅ Use requests to fetch page
✅ Use BeautifulSoup to parse HTML
✅ Use pandas.read_html() to extract tables
✅ Clean and structure data
✅ Save to JSON

Start implementation now! 🚀
    """)
    
elif success_count >= 1:
    print(f"""
⚠️  PARTIAL SUCCESS ({success_count}/4 statements found)

Some tables found, but not all expected statements.

POTENTIAL ISSUES:
1. Table structure might vary by stock
2. May need to refine table identification logic
3. Some metrics might be on different pages

ACTION:
- Refine table detection algorithm
- Test with more stocks
- Handle missing data gracefully

STATUS: Can proceed with caution, but needs refinement
    """)
else:
    print(f"""
❌ EXTRACTION FAILED - No statements found

ISSUES:
1. Table detection logic needs adjustment
2. Page structure might be different
3. Possible JavaScript rendering needed

SOLUTIONS:
1. Check if page uses JavaScript (try Selenium)
2. Inspect page directly in browser
3. Test with curl/wget first
4. Review Screener.in page manually

ACTION: Debug by manually opening in browser and inspecting source
    """)

print("\n" + "="*80)
print(f"Test completed for {test_stock}")
print("="*80 + "\n")
