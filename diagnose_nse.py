import os
import json
import sys
import subprocess

# --- AUTOMATIC RUNTIME DEPENDENCY MANAGEMENT ---
def bootstrap_dependencies():
    """Ensures required packages are installed programmatically before executing logic."""
    required_packages = {
        "pandas": "pandas",
        "yfinance": "yfinance"
    }
    
    missing_packages = []
    for module_name, pip_name in required_packages.items():
        try:
            __import__(module_name)
        except ImportError:
            missing_packages.append(pip_name)
            
    if missing_packages:
        print(f"Missing internal dependencies detected: {missing_packages}")
        print("Installing packages programmatically...")
        try:
            # Executes pip install silently using the current Python executable context
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", *missing_packages],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT
            )
            print("Dependencies successfully injected into runtime.")
        except subprocess.CalledProcessError as e:
            print(f"Critical error: Failed to auto-install dependencies. Context: {e}")
            sys.exit(1)

# Trigger bootstrap sequence immediately upon execution
bootstrap_dependencies()

# --- MAIN SCRIPT LOGIC (Runs safely after bootstrap) ---
import time
import random
import pandas as pd
import yfinance as yf

def get_indian_stock_data(ticker_symbol):
    if not any(ticker_symbol.endswith(ext) for ext in [".NS", ".BO"]):
        ticker_symbol += ".NS"
        
    ticker = yf.Ticker(ticker_symbol)
    
    data_payload = {
        "Ticker": ticker_symbol,
        "AsOfDate": "N/A",
        "CapEx": "N/A",
        "DebtDetail": {"ShortTermDebt": 0, "LongTermDebt": 0},
        "WorkingCapital": {"Inventory": "N/A", "AccountsReceivable": "N/A", "AccountsPayable": "N/A"},
        "ExceptionalItems": "N/A",
        "Segments": {"Business": {}, "Geographic": {}}
    }
    
    try:
        bs = ticker.balance_sheet
        cf = ticker.cashflow
        is_stmt = ticker.income_stmt
        
        if bs.empty or cf.empty or is_stmt.empty:
            return {"error": f"Incomplete financial statements for {ticker_symbol}"}
            
        latest_year = bs.columns[0]
        data_payload["AsOfDate"] = latest_year.strftime("%Y-%m-%d")
        
        def extract_field(df, match_keys, date_col):
            for key in match_keys:
                if key in df.index:
                    val = df.loc[key, date_col]
                    if isinstance(val, pd.Series): 
                        val = val.iloc[0]
                    return float(val) if pd.notna(val) else 0
            return 0

        data_payload["CapEx"] = extract_field(cf, ["Capital Expenditure", "InvestmentsInPropertyPlantAndEquipment"], latest_year)
        data_payload["DebtDetail"]["ShortTermDebt"] = extract_field(bs, ["Current Debt", "Short Long Term Debt"], latest_year)
        data_payload["DebtDetail"]["LongTermDebt"] = extract_field(bs, ["Long Term Debt"], latest_year)
        data_payload["WorkingCapital"]["Inventory"] = extract_field(bs, ["Inventory", "Inventories"], latest_year)
        data_payload["WorkingCapital"]["AccountsReceivable"] = extract_field(bs, ["Accounts Receivable"], latest_year)
        data_payload["WorkingCapital"]["AccountsPayable"] = extract_field(bs, ["Accounts Payable"], latest_year)
        
        data_payload["ExceptionalItems"] = extract_field(is_stmt, [
            "Other Non Operating Income Expenses", 
            "Special Income Charges"
        ], latest_year)

        return data_payload
    except Exception as e:
        return {"error": f"Extraction failure: {str(e)}"}

if __name__ == "__main__":
    watchlist = ["TCS", "RELIANCE"]
    combined_output = {}
    
    for symbol in watchlist:
        result = get_indian_stock_data(symbol)
        combined_output[symbol] = result
        time.sleep(random.uniform(2, 4))
        
    os.makedirs("output", exist_ok=True)
    with open("output/financial_report.json", "w") as f:
        json.dump(combined_output, f, indent=4)
        
    print(json.dumps(combined_output, indent=2))
