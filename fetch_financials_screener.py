#!/usr/bin/env python3
"""
Screener.in Financial Data Scraper - Single File Version
=========================================================
Fetches raw financial data for 100+ stocks from Screener.in

Usage:
    python fetch_financials_screener.py
    python fetch_financials_screener.py --symbols 50 --resume

Dependencies:
    - selenium
    - beautifulsoup4
    - requests
    - lxml
    
Install: pip install selenium beautifulsoup4 requests lxml
"""

import json
import time
import logging
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# ============================================================================
# DEPENDENCY CHECK
# ============================================================================

REQUIRED_PACKAGES = {
    'selenium': 'Selenium for browser automation',
    'bs4': 'BeautifulSoup for HTML parsing',
    'requests': 'Requests for HTTP',
    'lxml': 'LXML for XML parsing'
}

def check_dependencies():
    """Check if all required packages are installed"""
    missing = []
    for package, description in REQUIRED_PACKAGES.items():
        try:
            __import__(package)
        except ImportError:
            missing.append(f"  - {package} ({description})")
    
    if missing:
        print("❌ Missing required packages:")
        print("\n".join(missing))
        print("\nInstall all at once:")
        print("  pip install selenium beautifulsoup4 requests lxml")
        sys.exit(1)

check_dependencies()

# Now import after checking
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import csv

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Configuration - Modify these as needed"""
    
    # Paths (relative to current directory)
    DATA_DIR = Path('data')
    LOGS_DIR = Path('logs')
    SYMBOLS_FILE = Path('unified-symbols.json')
    
    # Output files
    OUTPUT_JSON = DATA_DIR / "screener-history.json"
    OUTPUT_CSV = DATA_DIR / "screener-raw.csv"
    CHECKPOINT_FILE = DATA_DIR / "checkpoint.json"
    LOG_FILE = LOGS_DIR / "fetch_financials_screener.log"
    
    # Scraper settings
    BASE_URL = "https://www.screener.in/company"
    REQUEST_TIMEOUT = 30
    BROWSER_TIMEOUT = 15
    RATE_LIMIT_DELAY = 2  # seconds between requests
    RETRY_ATTEMPTS = 3
    RETRY_DELAY = 2
    HEADLESS_MODE = True
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    
    # Create directories on init
    @staticmethod
    def init():
        """Initialize directories"""
        Config.DATA_DIR.mkdir(exist_ok=True)
        Config.LOGS_DIR.mkdir(exist_ok=True)


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    """Setup logging configuration"""
    Config.init()
    
    # Use module name (__name__) for logger - Python standard
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # File handler
    fh = logging.FileHandler(Config.LOG_FILE)
    fh.setLevel(logging.DEBUG)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger

logger = setup_logging()

# ============================================================================
# SCREENER SCRAPER CLASS
# ============================================================================

class ScreenerFinancialsScraper:
    """Scrapes financial data from Screener.in"""
    
    def __init__(self):
        """Initialize scraper"""
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': Config.USER_AGENT})
        self.scraped_data: Dict[str, Any] = {}
        self.failed_symbols: List[str] = []
        self.skipped_symbols: List[str] = []
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'start_time': None,
            'end_time': None
        }
    
    def load_symbols(self) -> List[str]:
        """Load stock symbols from unified-symbols.json"""
        try:
            if not Config.SYMBOLS_FILE.exists():
                logger.error(f"Symbol file not found: {Config.SYMBOLS_FILE}")
                return []
            
            with open(Config.SYMBOLS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            symbols = []
            
            # Handle dict format: {"symbols": [{"ticker": "INFY"}, ...]}
            if isinstance(data, dict):
                symbols_data = data.get('symbols', [])
                if isinstance(symbols_data, list):
                    for item in symbols_data:
                        if isinstance(item, dict):
                            # Try ticker first, then symbol, then NSE
                            sym = item.get('ticker') or item.get('symbol') or item.get('Symbol') or item.get('NSE')
                            if sym:
                                symbols.append(str(sym).strip())
            
            # Handle list format: [{"ticker": "INFY"}, ...] or ["INFY", ...]
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        sym = item.get('ticker') or item.get('symbol') or item.get('Symbol') or item.get('NSE')
                        if sym:
                            symbols.append(str(sym).strip())
                    elif isinstance(item, str):
                        if item.strip():
                            symbols.append(item.strip())
            
            # Clean and deduplicate
            symbols = [s.upper() for s in symbols if s]
            symbols = sorted(list(set(symbols)))
            
            if not symbols:
                logger.error("No valid symbols found in file")
                return []
            
            logger.info(f"✓ Loaded {len(symbols)} symbols")
            return symbols
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            return []
        except Exception as e:
            logger.error(f"Error loading symbols: {e}")
            return []
    
    def load_checkpoint(self) -> Tuple[List[str], int]:
        """Load resume checkpoint"""
        try:
            if Config.CHECKPOINT_FILE.exists():
                with open(Config.CHECKPOINT_FILE, 'r') as f:
                    checkpoint = json.load(f)
                completed = checkpoint.get('completed', [])
                logger.info(f"✓ Resumed from checkpoint: {len(completed)} already completed")
                return completed, len(completed)
        except Exception as e:
            logger.debug(f"No checkpoint found: {e}")
        return [], 0
    
    def save_checkpoint(self, completed_symbols: List[str]):
        """Save resume checkpoint"""
        try:
            checkpoint = {
                'timestamp': datetime.now().isoformat(),
                'completed': completed_symbols,
                'count': len(completed_symbols)
            }
            with open(Config.CHECKPOINT_FILE, 'w') as f:
                json.dump(checkpoint, f, indent=2)
        except Exception as e:
            logger.debug(f"Could not save checkpoint: {e}")
    
    def setup_browser(self):
        """Setup Selenium WebDriver with webdriver-manager"""
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            
            options = webdriver.ChromeOptions()
            if Config.HEADLESS_MODE:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument(f'user-agent={Config.USER_AGENT}')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            return driver
        except Exception as e:
            logger.error(f"Failed to setup browser: {e}")
            return None
    
    def fetch_page(self, symbol: str) -> Optional[str]:
        """Fetch page HTML with retry logic"""
        url = f"{Config.BASE_URL}/{symbol}/consolidated/"
        
        for attempt in range(Config.RETRY_ATTEMPTS):
            try:
                driver = self.setup_browser()
                if not driver:
                    raise Exception("Browser setup failed")
                
                driver.set_page_load_timeout(Config.BROWSER_TIMEOUT)
                driver.get(url)
                
                # Wait for tables to load
                WebDriverWait(driver, Config.BROWSER_TIMEOUT).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "data-table"))
                )
                
                html = driver.page_source
                driver.quit()
                
                time.sleep(Config.RATE_LIMIT_DELAY)
                return html
            
            except TimeoutException:
                logger.debug(f"Timeout: {symbol} (attempt {attempt + 1})")
                try:
                    driver.quit()
                except:
                    pass
            except Exception as e:
                logger.debug(f"Fetch error: {symbol} - {str(e)[:60]}")
                try:
                    driver.quit()
                except:
                    pass
            
            if attempt < Config.RETRY_ATTEMPTS - 1:
                time.sleep(Config.RETRY_DELAY)
        
        return None
    
    def parse_table(self, table) -> Dict[str, Dict[str, str]]:
        """Parse a data table into structured format"""
        data = {}
        
        try:
            headers = []
            thead = table.find('thead')
            if thead:
                for th in thead.find_all('th')[1:]:
                    headers.append(th.text.strip())
            
            tbody = table.find('tbody')
            if tbody:
                for tr in tbody.find_all('tr'):
                    tds = tr.find_all('td')
                    if not tds:
                        continue
                    
                    row_label = tds[0].text.strip()
                    row_data = {}
                    
                    for i, header in enumerate(headers):
                        if i + 1 < len(tds):
                            value = tds[i + 1].text.strip()
                            row_data[header] = value
                    
                    if row_data:
                        data[row_label] = row_data
            
            return data
        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return {}
    
    def extract_data(self, symbol: str, html: str) -> Optional[Dict[str, Any]]:
        """Extract financial data from HTML"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Company name
            h1 = soup.find('h1', class_='margin-0')
            company_name = h1.text.strip() if h1 else symbol
            
            # Extract tables
            tables = soup.find_all('table', class_='data-table')
            table_data = {}
            
            table_names = [
                'quarterly_results',
                'profit_loss',
                'balance_sheet',
                'cash_flow',
                'ratios'
            ]
            
            for i, table in enumerate(tables[:len(table_names)]):
                parsed = self.parse_table(table)
                if parsed:
                    table_data[table_names[i]] = {
                        'status': 'SUCCESS',
                        'data': parsed,
                        'rows': len(parsed)
                    }
            
            return {
                'symbol': symbol,
                'company_name': company_name,
                'timestamp': datetime.now().isoformat(),
                'tables': table_data,
                'status': 'SUCCESS'
            }
        
        except Exception as e:
            logger.error(f"Extraction error for {symbol}: {e}")
            return None
    
    def scrape_symbol(self, symbol: str) -> bool:
        """Scrape single symbol"""
        html = self.fetch_page(symbol)
        if not html:
            logger.warning(f"✗ {symbol:12} | FETCH FAILED")
            self.failed_symbols.append(symbol)
            self.stats['failed'] += 1
            return False
        
        data = self.extract_data(symbol, html)
        if data:
            self.scraped_data[symbol] = data
            logger.info(f"✓ {symbol:12} | SUCCESS")
            self.stats['success'] += 1
            return True
        
        logger.warning(f"✗ {symbol:12} | EXTRACTION FAILED")
        self.failed_symbols.append(symbol)
        self.stats['failed'] += 1
        return False
    
    def scrape_all(self, symbols: List[str], resume: bool = False, limit: Optional[int] = None) -> None:
        """Scrape all symbols"""
        symbols = symbols[:limit] if limit else symbols
        self.stats['total'] = len(symbols)
        self.stats['start_time'] = datetime.now()
        
        start_idx = 0
        completed = []
        
        if resume:
            completed, start_idx = self.load_checkpoint()
            self.skipped_symbols = completed
            self.stats['skipped'] = len(completed)
        
        # Print banner
        logger.info("=" * 80)
        logger.info(f"SCRAPING START | Total: {self.stats['total']} | Resume: {resume} | Skip: {start_idx}")
        logger.info("=" * 80)
        
        # Scrape
        for idx, symbol in enumerate(symbols[start_idx:], start=start_idx + 1):
            logger.info(f"[{idx}/{self.stats['total']}] {symbol}")
            self.scrape_symbol(symbol)
            
            # Save checkpoint every 10
            if idx % 10 == 0:
                all_completed = list(self.scraped_data.keys()) + self.skipped_symbols
                self.save_checkpoint(all_completed)
        
        self.stats['end_time'] = datetime.now()
    
    def save_results(self) -> None:
        """Save results to JSON and CSV"""
        # JSON
        try:
            duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds() if self.stats['end_time'] else 0
            
            output = {
                'metadata': {
                    'timestamp': datetime.now().isoformat(),
                    'total_requested': self.stats['total'],
                    'total_scraped': len(self.scraped_data),
                    'total_failed': len(self.failed_symbols),
                    'total_skipped': len(self.skipped_symbols),
                    'duration_seconds': round(duration, 2),
                    'success_rate': f"{(len(self.scraped_data) / max(self.stats['total'], 1) * 100):.1f}%"
                },
                'failed_symbols': self.failed_symbols,
                'data': self.scraped_data
            }
            
            with open(Config.OUTPUT_JSON, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            logger.info(f"✓ Saved JSON: {Config.OUTPUT_JSON}")
        except Exception as e:
            logger.error(f"Error saving JSON: {e}")
        
        # CSV
        try:
            rows = []
            for symbol, data in self.scraped_data.items():
                row = {
                    'symbol': symbol,
                    'company_name': data.get('company_name', ''),
                    'timestamp': data.get('timestamp', '')
                }
                
                # Latest quarter
                if 'quarterly_results' in data.get('tables', {}):
                    qr = data['tables']['quarterly_results'].get('data', {})
                    if 'Sales+' in qr:
                        periods = list(qr['Sales+'].keys())
                        if periods:
                            latest = periods[-1]
                            row['latest_quarter'] = latest
                            row['sales'] = qr['Sales+'].get(latest, '')
                            row['net_profit'] = qr.get('Net Profit+', {}).get(latest, '')
                            row['eps'] = qr.get('EPS in Rs', {}).get(latest, '')
                            row['opm'] = qr.get('OPM %', {}).get(latest, '')
                
                rows.append(row)
            
            if rows:
                with open(Config.OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
                logger.info(f"✓ Saved CSV: {Config.OUTPUT_CSV}")
        except Exception as e:
            logger.error(f"Error saving CSV: {e}")
    
    def print_summary(self) -> None:
        """Print execution summary"""
        logger.info("=" * 80)
        logger.info("EXECUTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total Requested:      {self.stats['total']}")
        logger.info(f"Successfully Scraped: {self.stats['success']} ✓")
        logger.info(f"Failed:               {self.stats['failed']} ✗")
        logger.info(f"Skipped:              {self.stats['skipped']}")
        
        if self.stats['end_time'] and self.stats['start_time']:
            duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
            logger.info(f"Duration:             {duration:.1f} seconds")
            if self.stats['success'] > 0:
                logger.info(f"Avg per stock:        {duration/self.stats['success']:.1f} seconds")
        
        logger.info(f"\nOutput Files:")
        logger.info(f"  JSON: {Config.OUTPUT_JSON}")
        logger.info(f"  CSV:  {Config.OUTPUT_CSV}")
        logger.info(f"  Log:  {Config.LOG_FILE}")
        logger.info("=" * 80)


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    """Main execution"""
    parser = argparse.ArgumentParser(
        description='Fetch financial data from Screener.in',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python fetch_financials_screener.py                 # Fetch all symbols
  python fetch_financials_screener.py --symbols 50    # Fetch first 50
  python fetch_financials_screener.py --resume        # Resume from last checkpoint
  python fetch_financials_screener.py --symbols 100 --resume
        """
    )
    
    parser.add_argument(
        '--symbols', type=int, default=None,
        help='Number of symbols to fetch (default: all)'
    )
    parser.add_argument(
        '--resume', action='store_true',
        help='Resume from checkpoint'
    )
    
    args = parser.parse_args()
    
    # Initialize scraper
    scraper = ScreenerFinancialsScraper()
    
    # Load symbols
    symbols = scraper.load_symbols()
    if not symbols:
        logger.error("No symbols found in unified-symbols.json")
        return 1
    
    logger.info(f"Total symbols available: {len(symbols)}")
    
    # Scrape
    scraper.scrape_all(symbols, resume=args.resume, limit=args.symbols)
    
    # Save
    scraper.save_results()
    
    # Summary
    scraper.print_summary()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
