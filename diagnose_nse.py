import requests
import gzip
from pathlib import Path

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.nseindia.com/",
}

DEBUG_DIR = Path("diagnostic")
DEBUG_DIR.mkdir(exist_ok=True)

session = requests.Session()

# Initialize with NSE
print("Initializing NSE session...")
session.get("https://www.nseindia.com/api/marketStatus", headers=BASE_HEADERS, timeout=30)

test_urls = [
    ("https://www.nseindia.com/api/quote-equity?symbol=INFY", "INFY_quote"),
    ("https://www.nseindia.com/api/corporates-financial-results?index=equities&symbol=INFY", "INFY_financial"),
    ("https://www.nseindia.com/api/corporate-announcements?index=equities&symbol=INFY", "INFY_announce"),
]

for url, label in test_urls:
    print(f"\n{'='*80}")
    print(f"Testing: {label}")
    print(f"URL: {url}")
    print('='*80)
    
    try:
        response = session.get(url, headers=BASE_HEADERS, timeout=30)
        
        print(f"\n✓ Status: {response.status_code}")
        print(f"✓ Content-Encoding: {response.headers.get('content-encoding', 'none')}")
        print(f"✓ Content-Type: {response.headers.get('content-type', 'unknown')}")
        print(f"✓ Content-Length: {len(response.content)} bytes")
        
        # Try to decompress
        if response.headers.get('content-encoding') == 'gzip':
            print("\n⚙️  Decompressing gzip...")
            try:
                decompressed = gzip.decompress(response.content).decode('utf-8')
                print(f"✓ Decompressed size: {len(decompressed)} bytes")
            except Exception as e:
                print(f"✗ Decompression failed: {e}")
                decompressed = response.text
        else:
            decompressed = response.text
        
        # Save to file
        output_file = DEBUG_DIR / f"{label}_raw.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(decompressed)
        print(f"\n✓ Saved to: {output_file}")
        
        # Show first 500 chars
        print(f"\nFirst 500 characters:")
        print("-" * 80)
        print(decompressed[:500])
        print("-" * 80)
        
        # Check what it looks like
        if not decompressed.strip():
            print("⚠️  EMPTY RESPONSE")
        elif decompressed.strip().startswith('<'):
            print("⚠️  HTML RESPONSE (not JSON)")
        elif decompressed.strip().startswith('{'):
            print("✓ Looks like JSON object")
        elif decompressed.strip().startswith('['):
            print("✓ Looks like JSON array")
        else:
            print(f"⚠️  UNKNOWN FORMAT")
            
    except Exception as e:
        print(f"✗ Error: {e}")

print(f"\n\nDiagnostic files saved to: {DEBUG_DIR}/")
