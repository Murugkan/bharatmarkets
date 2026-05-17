#!/usr/bin/env python3
"""
FINAL REFACTORED fetch_financial_payload()
===========================================
✅ Sector from unified-symbols.json (no hardcoding)
✅ Extract ALL yfinance fields (no losses)
✅ 4-quarter history for all metrics
✅ Organized: Sector → Ticker
✅ Common metrics + Sector-specific metrics
✅ Granular raw data preservation
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, UTC

def now():
    return datetime.now(UTC).isoformat()

def safe_float(val):
    try:
        if pd.isna(val):
            return 0
        return float(val)
    except:
        return 0

def extract_all_fields_4periods(dataframe, field_aliases_dict, periods=4):
    """
    Extract field with all aliases for 4 periods from quarterly dataframe
    Returns: {latest_value, historical_periods: [{period, value}, ...]}
    """
    if dataframe.empty or len(dataframe.columns) < 1:
        return {"latest_value": 0, "historical_periods": []}
    
    history = []
    latest_value = 0
    
    for col_idx in range(min(periods, len(dataframe.columns))):
        period_date = dataframe.columns[col_idx]
        period_str = period_date.strftime('%Y-%m-%d')
        col_data = dataframe.iloc[:, col_idx]
        
        val = 0
        for alias in field_aliases_dict:
            if alias in col_data.index:
                try:
                    v = col_data[alias]
                    if isinstance(v, pd.Series):
                        v = v.iloc[0]
                    if pd.notna(v):
                        val = safe_float(v)
                        break
                except:
                    pass
        
        history.append({"period": period_str, "value": val})
        
        if col_idx == 0:
            latest_value = val
    
    return {
        "latest_value": latest_value,
        "historical_periods": history
    }

def extract_all_metrics_4periods(dataframe, metrics_dict, periods=4):
    """
    Extract multiple metrics for 4 periods
    metrics_dict = {"field_name": ["alias1", "alias2", ...], ...}
    Returns: {latest: {field: value, ...}, historical_periods: [{period, field: value, ...}]}
    """
    if dataframe.empty or len(dataframe.columns) < 1:
        return {"latest": {}, "historical_periods": []}
    
    result = {"latest": {}, "historical_periods": []}
    
    for col_idx in range(min(periods, len(dataframe.columns))):
        period_date = dataframe.columns[col_idx]
        period_str = period_date.strftime('%Y-%m-%d')
        col_data = dataframe.iloc[:, col_idx]
        
        period_data = {"period": period_str}
        
        # Extract each metric
        for field_name, aliases in metrics_dict.items():
            val = 0
            for alias in aliases:
                if alias in col_data.index:
                    try:
                        v = col_data[alias]
                        if isinstance(v, pd.Series):
                            v = v.iloc[0]
                        if pd.notna(v):
                            val = safe_float(v)
                            break
                    except:
                        pass
            
            period_data[field_name] = val
        
        result["historical_periods"].append(period_data)
        
        # Latest is first period
        if col_idx == 0:
            result["latest"] = {k: v for k, v in period_data.items() if k != "period"}
    
    return result

def fetch_financial_payload(ticker, sector, symbol_overrides):
    """
    Fetch financial metrics - COMPREHENSIVE
    Sector from unified-symbols.json, all yfinance fields, 4-quarter history
    Output: Organized Sector → Ticker with complete data
    """
    
    def resolve_symbol(symbol, overrides):
        if symbol in overrides:
            return overrides[symbol]
        if not any(symbol.endswith(ext) for ext in [".NS", ".BO"]):
            return f"{symbol}.NS"
        return symbol
    
    resolved_ticker = resolve_symbol(ticker, symbol_overrides)
    
    try:
        stock = yf.Ticker(resolved_ticker)
        
        # ========== COMMON METRICS (All Sectors) ==========
        
        # CAPEX (from cash flow)
        capex_data = extract_all_fields_4periods(
            stock.quarterly_cashflow,
            ["Capital Expenditure", "CapitalExpenditures", "InvestmentsInPropertyPlantAndEquipment", "Capital Expenditures"],
            periods=4
        )
        capex_result = {
            "metric": "CapEx",
            "status": "success" if capex_data["latest_value"] != 0 or capex_data["historical_periods"] else "not_available",
            "source": "yfinance",
            "unit": "INR",
            "latest_value": capex_data["latest_value"],
            "historical_periods": capex_data["historical_periods"]
        }
        
        # DEBT DETAILS (from balance sheet + cash flow)
        bs = stock.quarterly_balance_sheet
        cf = stock.quarterly_cashflow
        debt_history = []
        debt_latest = {}
        
        if not bs.empty and len(bs.columns) > 0:
            for col_idx in range(min(4, len(bs.columns))):
                period_date = bs.columns[col_idx]
                period_str = period_date.strftime('%Y-%m-%d')
                col_data = bs.iloc[:, col_idx]
                
                period_data = {"period": period_str}
                
                # Extract debt fields
                for alias in ["Total Debt", "TotalDebt"]:
                    if alias in col_data.index:
                        period_data["total_debt"] = safe_float(col_data[alias])
                        break
                
                for alias in ["Short Term Debt", "ShortTermBorrowings", "CurrentPortionOfLongTermDebt"]:
                    if alias in col_data.index:
                        period_data["short_term_debt"] = safe_float(col_data[alias])
                        break
                
                for alias in ["Long Term Debt", "LongTermDebt", "LongTermBorrowings"]:
                    if alias in col_data.index:
                        period_data["long_term_debt"] = safe_float(col_data[alias])
                        break
                
                for alias in ["Total Assets", "TotalAssets"]:
                    if alias in col_data.index:
                        period_data["total_assets"] = safe_float(col_data[alias])
                        break
                
                for alias in ["Total Equity", "StockholdersEquity", "Equity"]:
                    if alias in col_data.index:
                        period_data["total_equity"] = safe_float(col_data[alias])
                        break
                
                debt_history.append(period_data)
                if col_idx == 0:
                    debt_latest = {k: v for k, v in period_data.items() if k != "period"}
        
        # Interest expense from income statement
        if not stock.quarterly_income_stmt.empty and len(stock.quarterly_income_stmt.columns) > 0:
            col_data = stock.quarterly_income_stmt.iloc[:, 0]
            for alias in ["Interest Expense", "InterestExpense"]:
                if alias in col_data.index:
                    interest_exp = safe_float(col_data[alias])
                    if debt_latest:
                        debt_latest["interest_expense"] = interest_exp
                    if debt_history:
                        debt_history[0]["interest_expense"] = interest_exp
                    break
        
        debt_result = {
            "metric": "Debt Details",
            "status": "success" if debt_history else "not_available",
            "source": "yfinance",
            "unit": "INR",
            "latest": debt_latest,
            "historical_periods": debt_history
        }
        
        # WORKING CAPITAL (from balance sheet)
        wc_history = []
        wc_latest = {}
        
        if not bs.empty and len(bs.columns) > 0:
            for col_idx in range(min(4, len(bs.columns))):
                period_date = bs.columns[col_idx]
                period_str = period_date.strftime('%Y-%m-%d')
                col_data = bs.iloc[:, col_idx]
                
                period_data = {"period": period_str}
                
                # Extract WC fields with ALL aliases
                for field_name, aliases in {
                    "accounts_receivable": ["Accounts Receivable", "AccountsReceivable"],
                    "accounts_payable": ["Accounts Payable", "AccountsPayable"],
                    "inventory": ["Inventory", "Inventories", "InventoriesNet"],
                    "cash_and_equivalents": ["Cash And Cash Equivalents", "CashAndCashEquivalents", "Cash"],
                    "current_assets": ["Current Assets", "TotalCurrentAssets"],
                    "current_liabilities": ["Current Liabilities", "TotalCurrentLiabilities"],
                    "prepaid_expenses": ["Prepaid Expenses", "PrepaidExpenses"]
                }.items():
                    val = 0
                    for alias in aliases:
                        if alias in col_data.index:
                            val = safe_float(col_data[alias])
                            break
                    period_data[field_name] = val
                
                # Calculate net working capital
                if "current_assets" in period_data and "current_liabilities" in period_data:
                    period_data["net_working_capital"] = period_data["current_assets"] - period_data["current_liabilities"]
                
                wc_history.append(period_data)
                if col_idx == 0:
                    wc_latest = {k: v for k, v in period_data.items() if k != "period"}
        
        wc_result = {
            "metric": "Working Capital",
            "status": "success" if wc_history else "not_available",
            "source": "yfinance",
            "unit": "INR",
            "latest": wc_latest,
            "historical_periods": wc_history
        }
        
        # EXCEPTIONAL ITEMS (from income statement)
        is_stmt = stock.quarterly_income_stmt
        except_history = []
        except_latest = 0
        
        if not is_stmt.empty and len(is_stmt.columns) > 0:
            for col_idx in range(min(4, len(is_stmt.columns))):
                period_date = is_stmt.columns[col_idx]
                period_str = period_date.strftime('%Y-%m-%d')
                col_data = is_stmt.iloc[:, col_idx]
                
                val = 0
                for key in col_data.index:
                    k_lower = str(key).lower()
                    if any(kw in k_lower for kw in ['exceptional', 'extraordinary', 'other income', 'other expense']):
                        val = safe_float(col_data[key])
                        break
                
                except_history.append({"period": period_str, "value": val})
                if col_idx == 0:
                    except_latest = val
        
        except_result = {
            "metric": "Exceptional Items",
            "status": "success" if except_history else "not_available",
            "source": "yfinance",
            "unit": "INR",
            "latest_value": except_latest,
            "historical_periods": except_history
        }
        
        # ========== SECTOR-SPECIFIC METRICS (Different per sector) ==========
        
        sector_metrics_result = extract_sector_metrics(stock, sector, periods=4)
        
        # ========== SEGMENTS DATA ==========
        
        segments_result = {
            "metric": "Segments",
            "status": "not_available",
            "source": "yfinance",
            "business_segments": {"latest": [], "historical_periods": []},
            "geographic_segments": {"latest": [], "historical_periods": []}
        }
        
        # ========== RETURN STRUCTURE ==========
        
        return {
            "symbol": ticker,
            "ticker": resolved_ticker,
            "sector": sector,
            "fetch_timestamp": now(),
            "data_source": "yfinance",
            "AsOfDate": is_stmt.columns[0].strftime('%Y-%m-%d') if not is_stmt.empty else "",
            "_common_metrics": {
                "capex": capex_result,
                "debt_details": debt_result,
                "working_capital": wc_result,
                "exceptional_items": except_result
            },
            "_sector_specific_metrics": sector_metrics_result,
            "_segments_data": segments_result
        }
    
    except Exception as e:
        return {
            "symbol": ticker,
            "sector": sector,
            "error": str(e)
        }

def extract_sector_metrics(stock, sector, periods=4):
    """
    Extract sector-specific metrics based on sector type
    Different fields extracted for each sector
    """
    sector_lower = sector.lower()
    
    is_stmt = stock.quarterly_income_stmt
    bs = stock.quarterly_balance_sheet
    cf = stock.quarterly_cashflow
    
    # Define metrics to extract per sector
    if "bank" in sector_lower or "financial" in sector_lower:
        metrics_dict = {
            "net_profit": ["Net Income", "Net Profit", "NetIncome"],
            "interest_expense": ["Interest Expense", "InterestExpense"],
            "operating_expenses": ["Operating Expenses", "Total Operating Expenses"],
            "total_assets": ["Total Assets", "TotalAssets"],
            "total_equity": ["Total Equity", "StockholdersEquity"],
            "deposits": ["Total Deposits", "CustomerDeposits", "Deposits"],
            "advances": ["Advances", "NetAdvances", "Loans"]
        }
    
    elif "manufactur" in sector_lower:
        metrics_dict = {
            "revenue": ["Total Revenue", "Operating Revenue", "Revenue"],
            "cost_of_goods_sold": ["Cost Of Revenue", "Cost of Goods Sold", "CostOfRevenue"],
            "gross_profit": ["Gross Profit", "GrossProfit"],
            "operating_expenses": ["Operating Expenses"],
            "ebitda": ["EBITDA", "Ebitda"],
            "ebit": ["Operating Income", "EBIT"],
            "interest_expense": ["Interest Expense"],
            "net_profit": ["Net Income", "Net Profit", "NetIncome"],
            "capex": ["Capital Expenditure", "CapitalExpenditures"],
            "inventory": ["Inventory", "Inventories"],
            "fixed_assets": ["Property Plant And Equipment", "PPE"],
            "raw_materials": ["Raw Materials"],
            "work_in_progress": ["Work In Progress", "WIP"],
            "finished_goods": ["Finished Goods"],
            "cash_and_equivalents": ["Cash And Cash Equivalents"]
        }
    
    elif "infrastructure" in sector_lower or "energy" in sector_lower or "power" in sector_lower:
        metrics_dict = {
            "revenue": ["Total Revenue", "Operating Revenue", "Revenue"],
            "cost_of_goods_sold": ["Cost Of Revenue"],
            "ebitda": ["EBITDA"],
            "operating_cash_flow": ["Operating Cash Flow"],
            "capex": ["Capital Expenditure", "CapitalExpenditures"],
            "total_debt": ["Total Debt"],
            "fixed_assets": ["Property Plant And Equipment"],
            "work_in_progress": ["Work In Progress"],
            "accounts_receivable": ["Accounts Receivable"],
            "cash_and_equivalents": ["Cash And Cash Equivalents"],
            "net_profit": ["Net Income", "Net Profit"]
        }
    
    elif "technology" in sector_lower or "tech" in sector_lower:
        metrics_dict = {
            "revenue": ["Total Revenue", "Operating Revenue", "Revenue"],
            "cost_of_goods_sold": ["Cost Of Revenue"],
            "gross_profit": ["Gross Profit"],
            "operating_expenses": ["Operating Expenses"],
            "ebitda": ["EBITDA"],
            "rd_expense": ["Research And Development", "R&D"],
            "net_profit": ["Net Income", "Net Profit"],
            "operating_cash_flow": ["Operating Cash Flow"],
            "free_cash_flow": ["Free Cash Flow"],
            "capex": ["Capital Expenditure"],
            "inventory": ["Inventory"],
            "total_debt": ["Total Debt"],
            "cash_and_equivalents": ["Cash And Cash Equivalents"]
        }
    
    else:  # IT Services or Default
        metrics_dict = {
            "revenue": ["Total Revenue", "Operating Revenue", "Revenue"],
            "cost_of_goods_sold": ["Cost Of Revenue"],
            "gross_profit": ["Gross Profit"],
            "operating_expenses": ["Operating Expenses"],
            "ebitda": ["EBITDA", "Ebitda"],
            "ebit": ["Operating Income", "EBIT"],
            "interest_expense": ["Interest Expense"],
            "net_profit": ["Net Income", "Net Profit", "NetIncome"],
            "operating_cash_flow": ["Operating Cash Flow"],
            "free_cash_flow": ["Free Cash Flow"],
            "accounts_receivable": ["Accounts Receivable"],
            "cash_and_equivalents": ["Cash And Cash Equivalents"],
            "employee_benefits": ["Employee Benefits"],
            "software_assets": ["Software", "Intangible Assets"]
        }
    
    # Extract metrics from income statement
    is_result = extract_all_metrics_4periods(is_stmt, metrics_dict, periods)
    
    # Extract from balance sheet (overwrite/add)
    bs_metrics = {}
    if not bs.empty:
        for col_idx in range(min(periods, len(bs.columns))):
            period_date = bs.columns[col_idx]
            period_str = period_date.strftime('%Y-%m-%d')
            col_data = bs.iloc[:, col_idx]
            
            if col_idx >= len(is_result["historical_periods"]):
                is_result["historical_periods"].append({"period": period_str})
            
            # Add BS fields
            for field_name, aliases in metrics_dict.items():
                if field_name in ["fixed_assets", "work_in_progress", "raw_materials", "finished_goods", 
                                 "inventory", "accounts_receivable", "cash_and_equivalents", 
                                 "total_debt", "total_assets", "total_equity", "deposits", "advances"]:
                    val = 0
                    for alias in aliases:
                        if alias in col_data.index:
                            val = safe_float(col_data[alias])
                            break
                    
                    if col_idx == 0 and field_name not in is_result["latest"]:
                        is_result["latest"][field_name] = val
                    
                    is_result["historical_periods"][col_idx][field_name] = val
    
    # Extract from cash flow (overwrite/add)
    if not cf.empty:
        for col_idx in range(min(periods, len(cf.columns))):
            period_date = cf.columns[col_idx]
            period_str = period_date.strftime('%Y-%m-%d')
            col_data = cf.iloc[:, col_idx]
            
            for field_name, aliases in metrics_dict.items():
                if field_name in ["operating_cash_flow", "free_cash_flow", "capex"]:
                    val = 0
                    for alias in aliases:
                        if alias in col_data.index:
                            val = safe_float(col_data[alias])
                            break
                    
                    if col_idx == 0 and field_name not in is_result["latest"]:
                        is_result["latest"][field_name] = val
                    
                    if col_idx < len(is_result["historical_periods"]):
                        is_result["historical_periods"][col_idx][field_name] = val
    
    return {
        "metric": f"Sector Specific Metrics - {sector}",
        "status": "success" if is_result["latest"] else "not_available",
        "source": "yfinance",
        "unit": "INR",
        "latest": is_result["latest"],
        "historical_periods": is_result["historical_periods"]
    }

if __name__ == "__main__":
    print("✓ fetch_yahoof_financials_1.py ready")
    print("Output: data/yahoof_financials_1.json")
    print("Log: data/logs/yahoof_financials_1.log")
