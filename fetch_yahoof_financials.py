#!/usr/bin/env python3
"""
Debug script to inspect actual yfinance field names
Shows what columns/rows are actually available in yfinance dataframes
"""

import yfinance as yf
import pandas as pd
import json

# Test with a few companies
tickers = ["ABCAPITAL.NS", "INFY.NS", "RELIANCE.NS"]

for ticker in tickers:
    print(f"\n{'='*80}")
    print(f"TICKER: {ticker}")
    print(f"{'='*80}")
    
    try:
        stock = yf.Ticker(ticker)
        
        # Income Statement
        print("\n### QUARTERLY INCOME STATEMENT ###")
        is_stmt = stock.quarterly_income_stmt
        if not is_stmt.empty:
            print(f"Shape: {is_stmt.shape}")
            print(f"\nIndex (row names):")
            for idx, row in enumerate(is_stmt.index[:20]):
                print(f"  [{idx}] {row}")
        else:
            print("EMPTY")
        
        # Balance Sheet
        print("\n### QUARTERLY BALANCE SHEET ###")
        bs = stock.quarterly_balance_sheet
        if not bs.empty:
            print(f"Shape: {bs.shape}")
            print(f"\nIndex (row names):")
            for idx, row in enumerate(bs.index[:20]):
                print(f"  [{idx}] {row}")
        else:
            print("EMPTY")
        
        # Cash Flow
        print("\n### QUARTERLY CASH FLOW ###")
        cf = stock.quarterly_cashflow
        if not cf.empty:
            print(f"Shape: {cf.shape}")
            print(f"\nIndex (row names):")
            for idx, row in enumerate(cf.index[:20]):
                print(f"  [{idx}] {row}")
        else:
            print("EMPTY")
            
    except Exception as e:
        print(f"ERROR: {e}")

print(f"\n{'='*80}")
print("INSPECTION COMPLETE")
print(f"{'='*80}")
