#!/usr/bin/env python3
"""
Screener Concalls Downloader - Single file, no external requirements
Usage: python screener_fetch.py [SECTOR]
Example: python screener_fetch.py IT
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime

# Check and install dependencies
def install_dependencies():
    """Install required packages if missing"""
    required = ['playwright', 'reportlab']
    import subprocess
    
    for package in required:
        try:
            __import__(package)
        except ImportError:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    
    # Install playwright browser
    print("Installing Chromium browser...")
    subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])

try:
    install_dependencies()
except Exception as e:
    print(f"Failed to install dependencies: {e}")
    sys.exit(1)

import asyncio
from playwright.async_api import async_playwright
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch

# Constants
DATA_DIR = Path('data')
LOGS_DIR = DATA_DIR / 'logs'
CONCALLS_DIR = DATA_DIR / 'screener-concalls'
SYMBOLS_FILE = Path('unified-symbols.json')
OUTPUT_FILE = DATA_DIR / 'screener-concalls.json'
LOG_FILE = LOGS_DIR / 'fetch-concall-history.log'

# Create directories
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
CONCALLS_DIR.mkdir(parents=True, exist_ok=True)

# Setup logging
class SimpleLogger:
    def __init__(self, log_file):
        self.log_file = log_file
    
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"{timestamp} - {level} - {message}"
        print(msg)
        with open(self.log_file, 'a') as f:
            f.write(msg + '\n')

logger = SimpleLogger(LOG_FILE)

# Credentials
EMAIL = os.getenv('SCREENER_EMAIL')
PASSWORD = os.getenv('SCREENER_PASSWORD')

class ScreenerFetcher:
    def __init__(self):
        self.data = {}
        self.load_data()
    
    def load_data(self):
        """Load existing data"""
        if OUTPUT_FILE.exists():
            with open(OUTPUT_FILE) as f:
                self.data = json.load(f)
    
    def save_data(self):
        """Save data to JSON"""
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(self.data, f, indent=2)
        logger.log(f"Saved to {OUTPUT_FILE}")
    
    def load_symbols(self, sector=None):
        """Load symbols from JSON, optionally filter by sector"""
        if not SYMBOLS_FILE.exists():
            logger.log(f"File not found: {SYMBOLS_FILE}", "ERROR")
            return []
        
        with open(SYMBOLS_FILE) as f:
            data = json.load(f)
        
        # Handle different formats
        if isinstance(data, list):
            symbols = data
        elif isinstance(data, dict):
            symbols = list(data.keys())
        else:
            return []
        
        # Filter by sector if provided
        if sector and isinstance(data, dict):
            filtered = []
            for sym in symbols:
                item = data.get(sym, {})
                if isinstance(item, dict):
                    if item.get('sector') == sector:
                        filtered.append(sym)
                elif isinstance(item, str):
                    if item == sector:
                        filtered.append(sym)
            return filtered
        
        return symbols
    
    def text_to_pdf(self, text, output_path):
        """Convert text to PDF"""
        try:
            doc = SimpleDocTemplate(str(output_path), pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            
            for line in text.split('\n')[:100]:  # Limit to 100 lines
                if line.strip():
                    story.append(Paragraph(line[:100], styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
            
            doc.build(story)
            return True
        except Exception as e:
            logger.log(f"PDF conversion error: {e}", "ERROR")
            return False
    
    async def fetch_stock(self, page, symbol):
        """Fetch concalls for one stock"""
        try:
            url = f"https://www.screener.in/company/{symbol}/"
            logger.log(f"Fetching {symbol}...")
            
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.click('text=Documents', timeout=5000)
            await page.wait_for_timeout(2000)
            
            # Check for concalls
            if not await page.query_selector('text=Concalls'):
                logger.log(f"No concalls for {symbol}")
                return None
            
            concalls = []
            rows = await page.query_selector_all('[class*="concall"], tr')
            
            for row in rows[:5]:  # Limit to 5 concalls per stock
                try:
                    date_text = await row.text_content()
                    if not date_text or not any(c.isdigit() for c in date_text):
                        continue
                    
                    date = date_text.strip()[:20]
                    
                    # Create directory
                    safe_date = date.replace(' ', '-').replace('/', '-')
                    file_dir = CONCALLS_DIR / symbol / safe_date
                    file_dir.mkdir(parents=True, exist_ok=True)
                    
                    files = {}
                    
                    # Try transcript
                    try:
                        trans_btn = await row.query_selector('text=Transcript')
                        if trans_btn:
                            await trans_btn.click()
                            await page.wait_for_timeout(1000)
                            content = await page.text_content()
                            if content:
                                pdf_path = file_dir / 'transcript.pdf'
                                self.text_to_pdf(content[:5000], pdf_path)
                                files['transcript'] = 'transcript.pdf'
                    except:
                        pass
                    
                    # Try summary
                    try:
                        sum_btn = await row.query_selector('text=AI Summary')
                        if sum_btn:
                            await sum_btn.click()
                            await page.wait_for_timeout(1000)
                            content = await page.text_content()
                            if content:
                                pdf_path = file_dir / 'summary.pdf'
                                self.text_to_pdf(content[:5000], pdf_path)
                                files['summary'] = 'summary.pdf'
                    except:
                        pass
                    
                    concalls.append({
                        'date': date,
                        'files': files,
                        'downloaded_at': datetime.now().isoformat()
                    })
                    
                except Exception as e:
                    logger.log(f"Row error: {e}", "WARN")
                    continue
            
            return concalls if concalls else None
            
        except Exception as e:
            logger.log(f"Stock fetch error ({symbol}): {e}", "ERROR")
            return None
    
    async def run(self, sector=None):
        """Main execution"""
        if not EMAIL or not PASSWORD:
            logger.log("Missing SCREENER_EMAIL or SCREENER_PASSWORD", "ERROR")
            return
        
        logger.log("=" * 60)
        logger.log(f"Starting Screener fetch{f' for sector: {sector}' if sector else ''}")
        logger.log("=" * 60)
        
        symbols = self.load_symbols(sector=sector)
        if not symbols:
            logger.log("No symbols found", "ERROR")
            return
        
        logger.log(f"Found {len(symbols)} symbols")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            try:
                # Login
                logger.log("Logging in...")
                await page.goto('https://www.screener.in/login/', wait_until='networkidle')
                await page.fill('input[name="username"]', EMAIL)
                await page.fill('input[name="password"]', PASSWORD)
                await page.click('button[type="submit"]')
                await page.wait_for_timeout(3000)
                
                logger.log("Login successful")
                
                # Fetch each symbol
                for i, symbol in enumerate(symbols, 1):
                    logger.log(f"[{i}/{len(symbols)}] Processing {symbol}")
                    
                    concalls = await self.fetch_stock(page, symbol)
                    if concalls:
                        self.data[symbol] = {
                            'concalls': concalls,
                            'last_updated': datetime.now().isoformat(),
                            'count': len(concalls)
                        }
                        logger.log(f"✓ Downloaded {len(concalls)} concalls for {symbol}")
                    
                    await page.wait_for_timeout(1000)
                
                self.save_data()
                logger.log("=" * 60)
                logger.log("DONE")
                logger.log("=" * 60)
                
            except Exception as e:
                logger.log(f"Fatal error: {e}", "ERROR")
            finally:
                await browser.close()

async def main():
    sector = sys.argv[1] if len(sys.argv) > 1 else os.getenv('SECTOR_FILTER')
    fetcher = ScreenerFetcher()
    await fetcher.run(sector=sector)

if __name__ == "__main__":
    asyncio.run(main())
