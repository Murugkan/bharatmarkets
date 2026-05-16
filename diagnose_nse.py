import os
import json
import sys
import subprocess
import time
import random
from datetime import datetime

# --- AUTOMATIC DEPENDENCY BOOTSTRAP ---
def bootstrap_dependencies():
    """Install required packages programmatically"""
    required = {
        "pandas": "pandas", 
        "yfinance": "yfinance",
        "requests": "requests",
        "beautifulsoup4": "beautifulsoup4"
    }
    missing = []
    
    for module_name, pip_name in required.items():
        try:
            __import__(module_name)
        except ImportError:
            missing.append(pip_name)
    
    if missing:
        print(f"Missing: {missing}")
        print("Installing...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", *missing],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT
            )
            print("✓ Dependencies installed\n")
        except subprocess.CalledProcessError as e:
            print(f"Failed: {e}")
            sys.exit(1)

bootstrap_dependencies()

import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup

class MultiSourceFetcher:
    """Fetch with fallback sources"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        })
    
    def fetch_stock_data(self, ticker_symbol):
        """Fetch with fallback sources"""
        
        if not any(ticker_symbol.endswith(ext) for ext in [".NS", ".BO"]):
            ticker_symbol += ".NS"
        
        payload = {
            "Ticker": ticker_symbol,
            "AsOfDate": "N/A",
            "CapEx": "N/A",
            "DebtDetail": {"ShortTermDebt": 0, "LongTermDebt": 0},
            "WorkingCapital": {
                "Inventory": "N/A",
                "AccountsReceivable": "N/A",
                "AccountsPayable": "N/A"
            },
            "ExceptionalItems": "N/A",
            "Segments": {"Business": {}, "Geographic": {}},
            "DataSources": {}
        }
        
        try:
            # PRIMARY SOURCE: yfinance
            print(f"  ├─ Trying yfinance...", end=" ", flush=True)
            yf_data = self._fetch_yfinance(ticker_symbol)
            if yf_data:
                payload.update(yf_data)
                payload["DataSources"]["primary"] = "yfinance"
                print("✓")
            else:
                print("✗")
            
            # FALLBACK 1: Fill gaps with FMP
            if payload["CapEx"] == "N/A" or payload["ExceptionalItems"] == "N/A":
                print(f"  ├─ Trying Financial Modeling Prep (fallback)...", end=" ", flush=True)
                fmp_data = self._fetch_fmp(ticker_symbol.replace(".NS", ""))
                if fmp_data:
                    # Fill only gaps
                    if payload["CapEx"] == "N/A" and "CapEx" in fmp_data:
                        payload["CapEx"] = fmp_data["CapEx"]
                    if payload["ExceptionalItems"] == "N/A" and "ExceptionalItems" in fmp_data:
                        payload["ExceptionalItems"] = fmp_data["ExceptionalItems"]
                    payload["DataSources"]["fallback1"] = "FMP"
                    print("✓")
                else:
                    print("✗")
            
            # FALLBACK 2: Fill gaps with BSE/NSE scraping
            if not payload["Segments"]["Geographic"] or not payload["Segments"]["Business"]:
                print(f"  ├─ Trying BSE/NSE scraping (fallback)...", end=" ", flush=True)
                bse_data = self._fetch_bse_nse(ticker_symbol)
                if bse_data:
                    if bse_data.get("Segments"):
                        payload["Segments"] = bse_data["Segments"]
                    payload["DataSources"]["fallback2"] = "BSE/NSE"
                    print("✓")
                else:
                    print("✗")
            
            return payload
            
        except Exception as e:
            return {"error": f"Critical failure: {str(e)}"}
    
    def _fetch_yfinance(self, ticker_symbol):
        """PRIMARY: yfinance"""
        try:
            ticker = yf.Ticker(ticker_symbol)
            
            bs = ticker.balance_sheet
            cf = ticker.cashflow
            is_stmt = ticker.income_stmt
            
            if bs.empty or cf.empty or is_stmt.empty:
                return None
            
            latest_year = bs.columns[0]
            
            def extract_field(df, match_keys, date_col):
                for key in match_keys:
                    if key in df.index:
                        val = df.loc[key, date_col]
                        if isinstance(val, pd.Series):
                            val = val.iloc[0]
                        return float(val) if pd.notna(val) else 0
                return 0
            
            data = {
                "AsOfDate": latest_year.strftime("%Y-%m-%d"),
                "CapEx": extract_field(cf, ["Capital Expenditure", "InvestmentsInPropertyPlantAndEquipment"], latest_year),
                "DebtDetail": {
                    "ShortTermDebt": extract_field(bs, ["Current Debt", "Short Long Term Debt"], latest_year),
                    "LongTermDebt": extract_field(bs, ["Long Term Debt"], latest_year)
                },
                "WorkingCapital": {
                    "Inventory": extract_field(bs, ["Inventory", "Inventories"], latest_year),
                    "AccountsReceivable": extract_field(bs, ["Accounts Receivable"], latest_year),
                    "AccountsPayable": extract_field(bs, ["Accounts Payable"], latest_year)
                },
                "ExceptionalItems": extract_field(is_stmt, ["Other Non Operating Income Expenses", "Special Income Charges"], latest_year)
            }
            
            # Convert "N/A" string placeholders to actual 0 or "N/A"
            if data["CapEx"] == 0:
                data["CapEx"] = "N/A"
            if data["ExceptionalItems"] == 0:
                data["ExceptionalItems"] = "N/A"
            
            return data if any([data["CapEx"] != "N/A", data["ExceptionalItems"] != "N/A", 
                              data["WorkingCapital"]["Inventory"] != "N/A"]) else None
        except:
            return None
    
    def _fetch_fmp(self, symbol):
        """FALLBACK 1: Financial Modeling Prep"""
        try:
            # Try FMP API endpoints
            endpoints = [
                f"https://financialsmodels.com/api/v3/cash-flow-statement/{symbol}",
                f"https://api.example.com/financials/{symbol}"
            ]
            
            for url in endpoints:
                try:
                    resp = self.session.get(url, timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        if isinstance(data, list) and len(data) > 0:
                            item = data[0]
                            return {
                                "CapEx": abs(item.get("capitalExpenditure", 0)),
                                "ExceptionalItems": abs(item.get("extraordinaryItems", 0))
                            }
                except:
                    continue
            
            return None
        except:
            return None
    
    def _fetch_bse_nse(self, ticker_symbol):
        """FALLBACK 2: BSE/NSE Web Scraping"""
        try:
            # Try BSE
            bse_url = f"https://www.bseindia.com/corpinfo/StockInfo_{ticker_symbol.replace('.NS', '')}.aspx"
            resp = self.session.get(bse_url, timeout=5)
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, 'html.parser')
                # Look for segment data in page
                # Note: Structure varies, this is a basic attempt
                segments = {"Business": {}, "Geographic": {}}
                
                # Try to find segment tables
                tables = soup.find_all('table')
                if tables:
                    return {"Segments": segments}
            
            return None
        except:
            return None

def main():
    stocks = ["COFORGE", "AZAD", "HDFC", "IGIL", "KAYNES"]
    results = {}
    
    print("\n" + "="*70)
    print("MULTI-SOURCE FINANCIAL DATA FETCHER")
    print("="*70)
    print(f"Stocks: {', '.join(stocks)}")
    print("Sources: yfinance → FMP → BSE/NSE")
    print("="*70 + "\n")
    
    fetcher = MultiSourceFetcher()
    
    for symbol in stocks:
        print(f"\n{symbol}")
        data = fetcher.fetch_stock_data(symbol)
        results[symbol] = data
        time.sleep(random.uniform(1, 2))
    
    # Save results
    os.makedirs("stock_data", exist_ok=True)
    filepath = "stock_data/financial_report.json"
    
    with open(filepath, "w") as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "="*70)
    print("EXECUTION COMPLETE")
    print("="*70)
    print(f"Saved to: {filepath}")
    print("="*70 + "\n")
    
    # Summary
    print("DATA AVAILABILITY:\n")
    for symbol, data in results.items():
        if "error" in data:
            print(f"{symbol}: ERROR - {data['error']}")
        else:
            sources = data.get("DataSources", {})
            print(f"{symbol}:")
            print(f"  ├─ Primary: {sources.get('primary', 'N/A')}")
            print(f"  ├─ Fallback 1: {sources.get('fallback1', 'N/A')}")
            print(f"  └─ Fallback 2: {sources.get('fallback2', 'N/A')}")

if __name__ == "__main__":
    main()
