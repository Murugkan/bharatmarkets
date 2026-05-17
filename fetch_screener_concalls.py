import json
import logging
from pathlib import Path
from datetime import datetime
import asyncio
from playwright.async_api import async_playwright
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch
from urllib.parse import urljoin

# Configuration
DATA_DIR = Path('data')
LOGS_DIR = DATA_DIR / 'logs'
CONCALLS_DIR = DATA_DIR / 'screener-concalls'
SYMBOLS_FILE = Path('unified-symbols.json')
OUTPUT_FILE = DATA_DIR / 'screener-concalls.json'
LOG_FILE = LOGS_DIR / 'fetch-concall-history.log'

# Setup logging
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Screener credentials (use GitHub Secrets in production)
SCREENER_EMAIL = os.getenv('SCREENER_EMAIL')
SCREENER_PASSWORD = os.getenv('SCREENER_PASSWORD')

class ScreenerConcallFetcher:
    def __init__(self):
        self.concalls_data = {}
        self.load_existing_data()
    
    def load_existing_data(self):
        """Load existing concalls data if file exists"""
        if OUTPUT_FILE.exists():
            with open(OUTPUT_FILE, 'r') as f:
                self.concalls_data = json.load(f)
                logger.info(f"Loaded {len(self.concalls_data)} existing records")
    
    def save_data(self):
        """Save concalls data to JSON file"""
        DATA_DIR.mkdir(exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(self.concalls_data, f, indent=2)
        logger.info(f"Saved concalls data to {OUTPUT_FILE}")
    
    def text_to_pdf(self, text_content, output_path):
        """Convert text content to PDF"""
        try:
            doc = SimpleDocTemplate(str(output_path), pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            
            # Add content with proper styling
            for line in text_content.split('\n'):
                if line.strip():
                    story.append(Paragraph(line, styles['Normal']))
                story.append(Spacer(1, 0.2*inch))
            
            doc.build(story)
            logger.info(f"Converted text to PDF: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error converting text to PDF: {e}")
            return False
    
    def create_metadata_pdf(self, metadata, output_path):
        """Create a simple PDF from metadata"""
        try:
            doc = SimpleDocTemplate(str(output_path), pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            
            for key, value in metadata.items():
                story.append(Paragraph(f"<b>{key}:</b> {value}", styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
            
            doc.build(story)
            return True
        except Exception as e:
            logger.error(f"Error creating metadata PDF: {e}")
            return False
    
    async def download_and_convert_file(self, page, symbol, date_str, doc_type, download_link):
        """Download file and convert to PDF"""
        try:
            # Create directory structure: data/screener-concalls/{SYMBOL}/{DATE}/{TYPE}/
            safe_date = date_str.replace(' ', '-').replace('/', '-')
            file_dir = CONCALLS_DIR / symbol / safe_date / doc_type.lower()
            file_dir.mkdir(parents=True, exist_ok=True)
            
            pdf_path = file_dir / f'{doc_type.lower()}.pdf'
            
            # If already downloaded, skip
            if pdf_path.exists():
                logger.info(f"File already exists: {pdf_path}")
                return str(pdf_path.relative_to(DATA_DIR))
            
            # Click download link
            await page.click(f'text={doc_type}')
            await page.wait_for_timeout(1500)
            
            # Handle different document types
            if doc_type == 'Transcript':
                # Get transcript text and convert to PDF
                text_content = await page.text_content()
                if text_content:
                    self.text_to_pdf(text_content, pdf_path)
                    return str(pdf_path.relative_to(DATA_DIR))
            
            elif doc_type == 'AI Summary':
                # Get summary text and convert to PDF
                summary_elem = await page.query_selector('[class*="summary"]')
                if summary_elem:
                    text_content = await summary_elem.text_content()
                    if text_content:
                        self.text_to_pdf(text_content, pdf_path)
                        return str(pdf_path.relative_to(DATA_DIR))
            
            elif doc_type == 'PPT':
                # For PPT, store reference (actual conversion requires additional libs)
                # Create a placeholder PDF with metadata
                metadata = {
                    'Type': 'PowerPoint Document',
                    'Symbol': symbol,
                    'Date': date_str,
                    'Status': 'Download from Screener manually'
                }
                self.create_metadata_pdf(metadata, pdf_path)
                logger.info(f"Created placeholder for PPT: {pdf_path}")
                return str(pdf_path.relative_to(DATA_DIR))
            
            return None
            
        except Exception as e:
            logger.error(f"Error downloading {doc_type} for {symbol}/{date_str}: {e}")
            return None
    
    async def fetch_concalls_for_stock(self, page, symbol):
        """Fetch and download concall documents for a specific stock"""
        try:
            # Navigate to company page
            url = f"https://www.screener.in/company/{symbol}/"
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait for Documents tab and click it
            await page.click('text=Documents')
            await page.wait_for_timeout(2000)
            
            # Check if Concalls section exists
            concalls_section = await page.query_selector('text=Concalls')
            if not concalls_section:
                logger.warning(f"No Concalls section found for {symbol}")
                return None
            
            # Extract concall data
            concalls = []
            concall_rows = await page.query_selector_all('.concall-row, [class*="concall"]')
            
            for row in concall_rows:
                try:
                    date_elem = await row.text_content()
                    date = date_elem.strip() if date_elem else None
                    
                    files = {
                        'transcript': None,
                        'summary': None,
                        'ppt': None
                    }
                    
                    # Check for Transcript
                    transcript_btn = await row.query_selector('text=Transcript')
                    if transcript_btn:
                        path = await self.download_and_convert_file(page, symbol, date, 'Transcript', None)
                        files['transcript'] = path
                    
                    # Check for AI Summary
                    summary_btn = await row.query_selector('text=AI Summary')
                    if summary_btn:
                        path = await self.download_and_convert_file(page, symbol, date, 'AI Summary', None)
                        files['summary'] = path
                    
                    # Check for PPT
                    ppt_btn = await row.query_selector('text=PPT')
                    if ppt_btn:
                        path = await self.download_and_convert_file(page, symbol, date, 'PPT', None)
                        files['ppt'] = path
                    
                    concall_item = {
                        'date': date,
                        'files': files,
                        'downloaded_at': datetime.now().isoformat()
                    }
                    concalls.append(concall_item)
                    
                except Exception as e:
                    logger.error(f"Error parsing concall row for {symbol}: {e}")
                    continue
            
            return concalls if concalls else None
            
        except Exception as e:
            logger.error(f"Error fetching concalls for {symbol}: {e}")
            return None
    
    def load_symbols(self, sector_filter=None):
        """Load stock symbols from unified-symbols.json, optionally filtered by sector"""
        if not SYMBOLS_FILE.exists():
            logger.error(f"Symbols file not found: {SYMBOLS_FILE}")
            return []
        
        with open(SYMBOLS_FILE, 'r') as f:
            symbols_data = json.load(f)
        
        # Handle list format (no sector info)
        if isinstance(symbols_data, list):
            return symbols_data
        
        # Handle dict format with sector info
        if isinstance(symbols_data, dict):
            if not sector_filter:
                return list(symbols_data.keys())
            
            # Filter by sector
            filtered_symbols = []
            for symbol, data in symbols_data.items():
                if isinstance(data, dict) and data.get('sector') == sector_filter:
                    filtered_symbols.append(symbol)
                elif isinstance(data, str) and data == sector_filter:
                    # Handle simple sector value format
                    filtered_symbols.append(symbol)
            
            if filtered_symbols:
                logger.info(f"Filtered {len(filtered_symbols)} symbols for sector: {sector_filter}")
                return filtered_symbols
            else:
                logger.warning(f"No symbols found for sector: {sector_filter}")
                return []
        
        return []
    
    async def login_and_fetch(self, sector_filter=None):
        """Login to Screener and fetch/download concalls for symbols in specified sector"""
        if not SCREENER_EMAIL or not SCREENER_PASSWORD:
            logger.error("Screener credentials not found in environment variables")
            return
        
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            try:
                # Login to Screener
                logger.info("Logging into Screener...")
                await page.goto('https://www.screener.in/login/', wait_until='networkidle')
                
                await page.fill('input[name="username"]', SCREENER_EMAIL)
                await page.fill('input[name="password"]', SCREENER_PASSWORD)
                await page.click('button[type="submit"]')
                
                # Wait for login to complete
                await page.wait_for_timeout(3000)
                
                # Load symbols with sector filter
                symbols = self.load_symbols(sector_filter=sector_filter)
                
                if not symbols:
                    logger.error(f"No symbols found{f' for sector: {sector_filter}' if sector_filter else ''}")
                    return
                
                logger.info(f"Found {len(symbols)} symbols to fetch")
                
                # Fetch concalls for each symbol
                for i, symbol in enumerate(symbols, 1):
                    logger.info(f"[{i}/{len(symbols)}] Fetching concalls for {symbol}...")
                    
                    concalls = await self.fetch_concalls_for_stock(page, symbol)
                    
                    if concalls:
                        self.concalls_data[symbol] = {
                            'concalls': concalls,
                            'last_updated': datetime.now().isoformat(),
                            'total_count': len(concalls)
                        }
                        logger.info(f"Downloaded {len(concalls)} concalls for {symbol}")
                    else:
                        logger.warning(f"No concalls found for {symbol}")
                    
                    # Rate limiting
                    await page.wait_for_timeout(1000)
                
                # Save data
                self.save_data()
                logger.info("Concalls fetch completed successfully")
                
            except Exception as e:
                logger.error(f"Fatal error during fetch: {e}")
            finally:
                await browser.close()

async def main():
    """Main execution"""
    logger.info("=" * 50)
    logger.info("Starting Screener Concalls Fetch")
    logger.info("=" * 50)
    
    # Get sector filter from environment variable or command line
    sector_filter = os.getenv('SECTOR_FILTER')
    
    if len(sys.argv) > 1:
        sector_filter = sys.argv[1]
    
    if sector_filter:
        logger.info(f"Sector filter: {sector_filter}")
    else:
        logger.info("No sector filter - will fetch all symbols")
    
    fetcher = ScreenerConcallFetcher()
    await fetcher.login_and_fetch(sector_filter=sector_filter)

if __name__ == "__main__":
    import sys
    asyncio.run(main())
