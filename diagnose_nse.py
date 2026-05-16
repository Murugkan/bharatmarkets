import os
import json
import sys
import subprocess
import time
import random
from datetime import datetime
from abc import ABC, abstractmethod

# --- AUTOMATIC DEPENDENCY BOOTSTRAP ---
def bootstrap_dependencies():
    """Install required packages"""
    required = {"pandas": "pandas", "yfinance": "yfinance"}
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

# ==================== SECTOR DEFINITIONS ====================

SECTOR_MAPPING = {
    "HDFC": "Banking",
    "COFORGE": "IT Services",
    "AZAD": "Manufacturing",
    "IGIL": "Infrastructure",
    "KAYNES": "Technology"
}

# ==================== SECTOR HANDLERS ====================

class SectorHandler(ABC):
    """Base class for sector-specific handlers"""
    
    @abstractmethod
    def extract_metrics(self, ticker_obj, latest_year):
        """Extract sector-specific metrics"""
        pass
    
    def extract_field(self, df, match_keys, date_col):
        """Safe field extraction"""
        for key in match_keys:
            if key in df.index:
                val = df.loc[key, date_col]
                if isinstance(val, pd.Series):
                    val = val.iloc[0]
                return float(val) if pd.notna(val) else 0
        return 0

class BankingHandler(SectorHandler):
    """Handler for Banking/Financial Services"""
    
    def extract_metrics(self, ticker_obj, latest_year):
        """Extract banking-specific metrics"""
        try:
            bs = ticker_obj.balance_sheet
            is_stmt = ticker_obj.income_stmt
            
            if bs.empty or is_stmt.empty:
                return {"status": "Incomplete data"}
            
            metrics = {
                "sector": "Banking",
                "sector_specific_metrics": {
                    "deposits": self.extract_field(bs, ["Total Deposits", "Customer Deposits"], latest_year),
                    "advances": self.extract_field(bs, ["Advances", "Net Advances"], latest_year),
                    "npl_gross": self.extract_field(bs, ["Gross NPA", "Non Performing Assets"], latest_year),
                    "net_profit": self.extract_field(is_stmt, ["Net Income", "Net Profit"], latest_year),
                    "total_assets": self.extract_field(bs, ["Total Assets"], latest_year),
                    "capital": self.extract_field(bs, ["Total Equity", "Shareholders Equity"], latest_year)
                },
                "note": "Banking metrics: deposits, advances, NPA, profitability"
            }
            
            return metrics
        except Exception as e:
            return {"error": str(e)}

class ManufacturingHandler(SectorHandler):
    """Handler for Manufacturing"""
    
    def extract_metrics(self, ticker_obj, latest_year):
        """Extract manufacturing-specific metrics"""
        try:
            bs = ticker_obj.balance_sheet
            cf = ticker_obj.cashflow
            is_stmt = ticker_obj.income_stmt
            
            if bs.empty or cf.empty or is_stmt.empty:
                return {"status": "Incomplete data"}
            
            metrics = {
                "sector": "Manufacturing",
                "sector_specific_metrics": {
                    "capex": self.extract_field(cf, ["Capital Expenditure", "InvestmentsInPropertyPlantAndEquipment"], latest_year),
                    "inventory": self.extract_field(bs, ["Inventory", "Inventories"], latest_year),
                    "ppe_gross": self.extract_field(bs, ["Property Plant Equipment"], latest_year),
                    "raw_materials": self.extract_field(bs, ["Raw Materials"], latest_year),
                    "wip": self.extract_field(bs, ["Work In Progress"], latest_year),
                    "finished_goods": self.extract_field(bs, ["Finished Goods"], latest_year),
                    "revenue": self.extract_field(is_stmt, ["Total Revenue", "Operating Revenue"], latest_year),
                    "cogs": self.extract_field(is_stmt, ["Cost Of Revenue", "Cost of Goods Sold"], latest_year)
                },
                "note": "Manufacturing metrics: CapEx, inventory breakdown, production capacity"
            }
            
            return metrics
        except Exception as e:
            return {"error": str(e)}

class ITServicesHandler(SectorHandler):
    """Handler for IT Services"""
    
    def extract_metrics(self, ticker_obj, latest_year):
        """Extract IT-specific metrics"""
        try:
            bs = ticker_obj.balance_sheet
            is_stmt = ticker_obj.income_stmt
            cf = ticker_obj.cashflow
            
            if bs.empty or is_stmt.empty or cf.empty:
                return {"status": "Incomplete data"}
            
            metrics = {
                "sector": "IT Services",
                "sector_specific_metrics": {
                    "revenue": self.extract_field(is_stmt, ["Total Revenue", "Operating Revenue"], latest_year),
                    "ebitda": self.extract_field(is_stmt, ["EBITDA"], latest_year),
                    "net_profit": self.extract_field(is_stmt, ["Net Income", "Net Profit"], latest_year),
                    "operating_cash_flow": self.extract_field(cf, ["Operating Cash Flow"], latest_year),
                    "accounts_receivable": self.extract_field(bs, ["Accounts Receivable"], latest_year),
                    "employee_benefits": self.extract_field(bs, ["Employee Benefits Payable"], latest_year),
                    "software_assets": self.extract_field(bs, ["Intangible Assets"], latest_year),
                    "cash": self.extract_field(bs, ["Cash And Cash Equivalents"], latest_year)
                },
                "note": "IT Services metrics: revenue, EBITDA, cash flow, AR, employee costs"
            }
            
            return metrics
        except Exception as e:
            return {"error": str(e)}

class TechnologyHandler(SectorHandler):
    """Handler for Technology companies"""
    
    def extract_metrics(self, ticker_obj, latest_year):
        """Extract technology-specific metrics"""
        try:
            bs = ticker_obj.balance_sheet
            is_stmt = ticker_obj.income_stmt
            cf = ticker_obj.cashflow
            
            if bs.empty or is_stmt.empty or cf.empty:
                return {"status": "Incomplete data"}
            
            metrics = {
                "sector": "Technology",
                "sector_specific_metrics": {
                    "revenue": self.extract_field(is_stmt, ["Total Revenue", "Operating Revenue"], latest_year),
                    "gross_profit": self.extract_field(is_stmt, ["Gross Profit"], latest_year),
                    "rd_expense": self.extract_field(is_stmt, ["Research And Development"], latest_year),
                    "net_profit": self.extract_field(is_stmt, ["Net Income", "Net Profit"], latest_year),
                    "free_cash_flow": self.extract_field(cf, ["Free Cash Flow"], latest_year),
                    "inventory": self.extract_field(bs, ["Inventory", "Inventories"], latest_year),
                    "capex": self.extract_field(cf, ["Capital Expenditure"], latest_year),
                    "debt": self.extract_field(bs, ["Total Debt"], latest_year)
                },
                "note": "Technology metrics: revenue, R&D, margins, cash flow"
            }
            
            return metrics
        except Exception as e:
            return {"error": str(e)}

class InfrastructureHandler(SectorHandler):
    """Handler for Infrastructure companies"""
    
    def extract_metrics(self, ticker_obj, latest_year):
        """Extract infrastructure-specific metrics"""
        try:
            bs = ticker_obj.balance_sheet
            is_stmt = ticker_obj.income_stmt
            cf = ticker_obj.cashflow
            
            if bs.empty or is_stmt.empty or cf.empty:
                return {"status": "Incomplete data"}
            
            metrics = {
                "sector": "Infrastructure",
                "sector_specific_metrics": {
                    "revenue": self.extract_field(is_stmt, ["Total Revenue", "Operating Revenue"], latest_year),
                    "capex": self.extract_field(cf, ["Capital Expenditure"], latest_year),
                    "debt": self.extract_field(bs, ["Total Debt"], latest_year),
                    "operating_cash_flow": self.extract_field(cf, ["Operating Cash Flow"], latest_year),
                    "fixed_assets": self.extract_field(bs, ["Property Plant Equipment"], latest_year),
                    "work_in_progress": self.extract_field(bs, ["Work In Progress"], latest_year),
                    "accounts_receivable": self.extract_field(bs, ["Accounts Receivable"], latest_year),
                    "project_liabilities": self.extract_field(bs, ["Advance From Customers"], latest_year)
                },
                "note": "Infrastructure metrics: CapEx, debt, asset composition, project receivables"
            }
            
            return metrics
        except Exception as e:
            return {"error": str(e)}

# ==================== HANDLER MAPPING ====================

SECTOR_HANDLERS = {
    "Banking": BankingHandler(),
    "Manufacturing": ManufacturingHandler(),
    "IT Services": ITServicesHandler(),
    "Technology": TechnologyHandler(),
    "Infrastructure": InfrastructureHandler()
}

# ==================== SECTOR-AWARE FETCHER ====================

class SectorAwareFetcher:
    """Fetch data with sector-specific handlers"""
    
    def __init__(self):
        self.results = {}
        self.sector_results = {}
    
    def fetch_by_sector(self, stock_symbol, sector):
        """Fetch using sector-specific handler"""
        
        if not any(stock_symbol.endswith(ext) for ext in [".NS", ".BO"]):
            stock_symbol += ".NS"
        
        ticker = yf.Ticker(stock_symbol)
        
        payload = {
            "symbol": stock_symbol.replace(".NS", ""),
            "ticker": stock_symbol,
            "sector": sector,
            "fetch_timestamp": datetime.now().isoformat(),
            "data_source": "yfinance"
        }
        
        try:
            # Check if data exists
            bs = ticker.balance_sheet
            if bs.empty:
                return {"error": f"No data for {stock_symbol}"}
            
            latest_year = bs.columns[0]
            payload["AsOfDate"] = latest_year.strftime("%Y-%m-%d")
            
            # Get sector handler
            if sector not in SECTOR_HANDLERS:
                return {"error": f"Unknown sector: {sector}"}
            
            handler = SECTOR_HANDLERS[sector]
            sector_data = handler.extract_metrics(ticker, latest_year)
            
            payload.update(sector_data)
            return payload
            
        except Exception as e:
            return {"error": f"Failed: {str(e)}"}
    
    def load_sector_by_sector(self):
        """Load and process sector by sector"""
        
        # Group stocks by sector
        sectors_dict = {}
        for symbol, sector in SECTOR_MAPPING.items():
            if sector not in sectors_dict:
                sectors_dict[sector] = []
            sectors_dict[sector].append(symbol)
        
        # Process each sector
        for sector, symbols in sectors_dict.items():
            print(f"\n{'='*70}")
            print(f"SECTOR: {sector}")
            print(f"{'='*70}")
            
            self.sector_results[sector] = {}
            
            for symbol in symbols:
                print(f"  Fetching {symbol}...", end=" ", flush=True)
                try:
                    data = self.fetch_by_sector(symbol, sector)
                    self.results[symbol] = data
                    self.sector_results[sector][symbol] = data
                    print("✓")
                    time.sleep(random.uniform(1, 2))
                except Exception as e:
                    print(f"✗")
                    self.results[symbol] = {"error": str(e)}
    
    def save_results(self):
        """Save results"""
        os.makedirs("stock_data", exist_ok=True)
        
        # Combined results
        with open("stock_data/financial_report.json", "w") as f:
            json.dump(self.results, f, indent=2)
        
        # Sector-wise results
        with open("stock_data/sector_report.json", "w") as f:
            json.dump(self.sector_results, f, indent=2)
        
        return "stock_data/financial_report.json"

# ==================== MAIN ====================

def main():
    print("\n" + "="*70)
    print("SECTOR-AWARE FINANCIAL DATA FETCHER")
    print("="*70)
    print("Stocks: " + ", ".join(SECTOR_MAPPING.keys()))
    print("Sectors: " + ", ".join(set(SECTOR_MAPPING.values())))
    print("="*70)
    
    fetcher = SectorAwareFetcher()
    
    # Load sector by sector
    fetcher.load_sector_by_sector()
    
    # Save results
    filepath = fetcher.save_results()
    
    # Summary
    print("\n" + "="*70)
    print("EXECUTION COMPLETE")
    print("="*70)
    print(f"\nCombined results: {filepath}")
    print(f"Sector results: stock_data/sector_report.json")
    
    print("\n" + "="*70)
    print("RESULTS SUMMARY")
    print("="*70)
    print(json.dumps(fetcher.results, indent=2))

if __name__ == "__main__":
    main()
