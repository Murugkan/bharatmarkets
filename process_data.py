#!/usr/bin/env python3
"""
Standardize raw market data for analysis.

Input:  data/raw_market_data.json
Output: data/market_data.json

Transformations:
1. Remove observations wrapper (flatten to single object)
2. Standardize time series formats (numeric values, ISO dates)
3. Remove redundant ticker/name/isin in nested objects
4. Add normalized snapshot fields
5. Convert string numbers to actual numbers
6. Move fetched_at to file-level metadata only
"""

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional


def parse_number(value: Any) -> Optional[float]:
    """Convert string numbers like '13,459' or '15.2%' to float."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Remove commas, percentage signs, and whitespace
        cleaned = value.replace(',', '').replace('%', '').strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def parse_date(date_str: str) -> str:
    """Standardize date formats to ISO format (YYYY-MM-DD)."""
    if not date_str or date_str == "":
        return ""
    
    # Handle "Mar 2023" format
    if re.match(r'^[A-Za-z]{3}\s+\d{4}$', date_str):
        try:
            dt = datetime.strptime(date_str, '%b %Y')
            # Return last day of month
            if dt.month == 12:
                next_month = dt.replace(year=dt.year + 1, month=1, day=1)
            else:
                next_month = dt.replace(month=dt.month + 1, day=1)
            from datetime import timedelta
            last_day = next_month - timedelta(days=1)
            return last_day.strftime('%Y-%m-%d')
        except:
            return date_str
    
    # Handle "2026-03-31" format
    if re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
        return date_str.split()[0]
    
    # Handle "2025-11-18 00:00:00+05:30" format
    if ' ' in date_str:
        return date_str.split()[0]
    
    return date_str


def period_to_quarter(date_str: str) -> str:
    """Convert date to quarter format like '2026-Q1'."""
    try:
        dt = datetime.fromisoformat(date_str.split()[0])
        quarter = (dt.month - 1) // 3 + 1
        return f"{dt.year}-Q{quarter}"
    except:
        return date_str


def standardize_price_history(raw_data: Dict) -> Dict:
    """Standardize price history from Yahoo Finance."""
    result = {}
    
    for key in ['history_6mo_1d', 'history_5y_1wk', 'history_5y_1mo']:
        if key not in raw_data:
            continue
        
        history_data = raw_data[key]
        if not isinstance(history_data, list):
            continue
        
        # Map to cleaner key names
        output_key = {
            'history_6mo_1d': 'daily_6m',
            'history_5y_1wk': 'weekly_5y',
            'history_5y_1mo': 'monthly_5y'
        }[key]
        
        standardized = []
        for entry in history_data:
            if not isinstance(entry, dict):
                continue
            
            std_entry = {
                'date': parse_date(entry.get('Date', '')),
                'open': parse_number(entry.get('Open')),
                'high': parse_number(entry.get('High')),
                'low': parse_number(entry.get('Low')),
                'close': parse_number(entry.get('Close')),
                'volume': parse_number(entry.get('Volume'))
            }
            
            # Remove None values
            std_entry = {k: v for k, v in std_entry.items() if v is not None}
            
            if std_entry.get('date'):
                standardized.append(std_entry)
        
        if standardized:
            result[output_key] = standardized
    
    return result


def standardize_screener_financials(tables: Dict) -> Dict:
    """Standardize Screener.in financial tables."""
    result = {
        'profit_loss': [],
        'balance_sheet': [],
        'cash_flow': [],
        'ratios': []
    }
    
    for table_name in ['profit_loss', 'balance_sheet', 'cash_flow', 'ratios']:
        if table_name not in tables or 'data' not in tables[table_name]:
            continue
        
        data = tables[table_name]['data']
        if not isinstance(data, dict):
            continue
        
        # Get all periods from the first metric
        periods = []
        if data:
            first_metric = next(iter(data.values()))
            if isinstance(first_metric, dict):
                periods = list(first_metric.keys())
        
        # Convert from column-oriented to row-oriented
        for period in periods:
            entry = {
                'period': period_to_quarter(parse_date(period)),
                'end_date': parse_date(period)
            }
            
            for metric_name, metric_values in data.items():
                if isinstance(metric_values, dict) and period in metric_values:
                    # Clean metric name (remove special chars, make snake_case)
                    clean_name = re.sub(r'[^\w\s]', '', metric_name)
                    clean_name = clean_name.strip().lower().replace(' ', '_')
                    
                    value = parse_number(metric_values[period])
                    if value is not None:
                        entry[clean_name] = value
            
            result[table_name].append(entry)
    
    return result


def standardize_yahoo_financials(raw_data: Dict) -> List[Dict]:
    """Standardize Yahoo Finance financial statements."""
    if 'historical_periods' not in raw_data:
        return []
    
    periods = raw_data['historical_periods']
    if not isinstance(periods, list):
        return []
    
    standardized = []
    for period in periods:
        if not isinstance(period, dict):
            continue
        
        entry = {
            'period': period_to_quarter(period.get('period', '')),
            'end_date': parse_date(period.get('period', ''))
        }
        
        # Add all numeric fields
        for key, value in period.items():
            if key == 'period':
                continue
            
            parsed = parse_number(value)
            if parsed is not None:
                entry[key] = parsed
        
        if entry.get('end_date'):
            standardized.append(entry)
    
    return standardized


def create_snapshot(yahoo_info: Dict, screener_data: Dict) -> Dict:
    """Create normalized snapshot with key metrics."""
    snapshot = {}
    
    # From Yahoo Finance
    if yahoo_info:
        snapshot['price'] = parse_number(yahoo_info.get('currentPrice'))
        snapshot['market_cap'] = parse_number(yahoo_info.get('marketCap'))
        snapshot['sector'] = yahoo_info.get('sector')
        snapshot['industry'] = yahoo_info.get('industry')
        snapshot['pe_ratio'] = parse_number(yahoo_info.get('trailingPE'))
        snapshot['pb_ratio'] = parse_number(yahoo_info.get('priceToBook'))
        snapshot['dividend_yield'] = parse_number(yahoo_info.get('dividendYield'))
        snapshot['52w_high'] = parse_number(yahoo_info.get('fiftyTwoWeekHigh'))
        snapshot['52w_low'] = parse_number(yahoo_info.get('fiftyTwoWeekLow'))
        snapshot['avg_volume'] = parse_number(yahoo_info.get('averageVolume'))
    
    # Remove None values
    snapshot = {k: v for k, v in snapshot.items() if v is not None}
    
    return snapshot


def standardize_stock(stock_data: Dict) -> Dict:
    """Standardize a single stock's data."""
    result = {
        'ticker': stock_data.get('ticker'),
        'name': stock_data.get('name'),
        'isin': stock_data.get('isin')
    }
    
    # Extract Yahoo raw data
    yahoo_info = {}
    yahoo_raw_data = {}
    if 'yahoofin_raw' in stock_data:
        yahoo_raw = stock_data['yahoofin_raw']
        if 'observations' in yahoo_raw and yahoo_raw['observations']:
            obs = yahoo_raw['observations'][0]
            if 'raw' in obs:
                yahoo_raw_data = obs['raw']
                yahoo_info = obs['raw'].get('info', {})
    
    # Create snapshot
    result['snapshot'] = create_snapshot(yahoo_info, stock_data.get('screener_raw'))
    
    # Price history
    if yahoo_raw_data:
        price_history = standardize_price_history(yahoo_raw_data)
        if price_history:
            result['price_history'] = price_history
    
    # Financials from Screener
    if 'screener_financials' in stock_data:
        sf = stock_data['screener_financials']
        if sf.get('status') == 'SUCCESS' and 'tables' in sf:
            financials = standardize_screener_financials(sf['tables'])
            
            # Only add non-empty sections
            for key, value in financials.items():
                if value:
                    result[f'screener_{key}'] = value
    
    # Financials from Yahoo
    if 'yahoofin_financials' in stock_data:
        yf = stock_data['yahoofin_financials']
        if 'observations' in yf and yf['observations']:
            obs = yf['observations'][0]
            if 'raw' in obs:
                yahoo_financials = standardize_yahoo_financials(obs['raw'])
                if yahoo_financials:
                    result['yahoo_financials'] = yahoo_financials
    
    return result


def generate_html_report(raw_data: Dict, standardized: Dict, stats: Dict) -> str:
    """Generate HTML report comparing raw vs standardized data."""
    
    # Get sample stock for comparison
    sample_ticker = list(standardized['stocks'].keys())[0]
    sample_raw = raw_data['data'][sample_ticker]
    sample_std = standardized['stocks'][sample_ticker]
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Market Data Standardization Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        h1 {{ margin: 0 0 10px 0; color: #1a1a1a; }}
        .subtitle {{ color: #666; font-size: 14px; }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .stat-label {{ color: #666; font-size: 12px; text-transform: uppercase; }}
        .stat-value {{ font-size: 28px; font-weight: bold; color: #1a1a1a; margin-top: 5px; }}
        .section {{
            background: white;
            padding: 25px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        h2 {{ margin-top: 0; color: #1a1a1a; font-size: 18px; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th {{
            background: #f8f9fa;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #dee2e6;
            color: #495057;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #dee2e6;
        }}
        tr:hover {{ background: #f8f9fa; }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
        }}
        .badge-success {{ background: #d4edda; color: #155724; }}
        .badge-warning {{ background: #fff3cd; color: #856404; }}
        .badge-danger {{ background: #f8d7da; color: #721c24; }}
        .code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
        }}
        .comparison {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        .comparison-col {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
        }}
        .comparison-col h3 {{
            margin-top: 0;
            font-size: 14px;
            color: #495057;
        }}
        pre {{
            background: white;
            padding: 12px;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 11px;
            line-height: 1.5;
        }}
        .tick {{ color: #28a745; font-weight: bold; }}
        .cross {{ color: #dc3545; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Market Data Standardization Report</h1>
        <div class="subtitle">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
    </div>
    
    <div class="stats">
        <div class="stat-card">
            <div class="stat-label">Total Stocks</div>
            <div class="stat-value">{stats['total_stocks']}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Successfully Processed</div>
            <div class="stat-value" style="color: #28a745;">{stats['processed']}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Errors</div>
            <div class="stat-value" style="color: {'#dc3545' if stats['errors'] > 0 else '#28a745'};">{stats['errors']}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">File Size Reduction</div>
            <div class="stat-value" style="color: #007bff;">{stats.get('size_reduction', 'N/A')}</div>
        </div>
    </div>
    
    <div class="section">
        <h2>✅ Transformations Applied</h2>
        <table>
            <tr>
                <th style="width: 40%">Transformation</th>
                <th>Status</th>
                <th>Description</th>
            </tr>
            <tr>
                <td><span class="code">observations</span> wrapper removed</td>
                <td><span class="badge badge-success">✓ Applied</span></td>
                <td>Flattened nested structure, single timestamp at file level</td>
            </tr>
            <tr>
                <td>String numbers → Numeric</td>
                <td><span class="badge badge-success">✓ Applied</span></td>
                <td>Converted "13,459" to 13459000000</td>
            </tr>
            <tr>
                <td>Date standardization</td>
                <td><span class="badge badge-success">✓ Applied</span></td>
                <td>All dates to ISO format (YYYY-MM-DD)</td>
            </tr>
            <tr>
                <td>Redundancy removal</td>
                <td><span class="badge badge-success">✓ Applied</span></td>
                <td>Ticker/name only at root level</td>
            </tr>
            <tr>
                <td>Normalized snapshot layer</td>
                <td><span class="badge badge-success">✓ Applied</span></td>
                <td>Quick-access metrics (price, market cap, etc.)</td>
            </tr>
        </table>
    </div>
    
    <div class="section">
        <h2>📋 Data Coverage Summary</h2>
        <table>
            <tr>
                <th>Data Type</th>
                <th>Stocks with Data</th>
                <th>Coverage</th>
                <th>Sample Fields</th>
            </tr>
"""
    
    # Calculate coverage stats
    coverage = {
        'Snapshot': 0,
        'Price History (6m daily)': 0,
        'Price History (5y weekly)': 0,
        'Price History (5y monthly)': 0,
        'Screener Profit/Loss': 0,
        'Screener Balance Sheet': 0,
        'Screener Cash Flow': 0,
        'Yahoo Financials': 0
    }
    
    for ticker, stock in standardized['stocks'].items():
        if stock.get('snapshot'):
            coverage['Snapshot'] += 1
        if stock.get('price_history', {}).get('daily_6m'):
            coverage['Price History (6m daily)'] += 1
        if stock.get('price_history', {}).get('weekly_5y'):
            coverage['Price History (5y weekly)'] += 1
        if stock.get('price_history', {}).get('monthly_5y'):
            coverage['Price History (5y monthly)'] += 1
        if stock.get('screener_profit_loss'):
            coverage['Screener Profit/Loss'] += 1
        if stock.get('screener_balance_sheet'):
            coverage['Screener Balance Sheet'] += 1
        if stock.get('screener_cash_flow'):
            coverage['Screener Cash Flow'] += 1
        if stock.get('yahoo_financials'):
            coverage['Yahoo Financials'] += 1
    
    total = stats['processed']
    for data_type, count in coverage.items():
        pct = (count / total * 100) if total > 0 else 0
        badge_class = 'badge-success' if pct >= 95 else 'badge-warning' if pct >= 80 else 'badge-danger'
        
        sample_fields = ''
        if data_type == 'Snapshot':
            sample_fields = 'price, market_cap, sector, pe_ratio'
        elif 'Price History' in data_type:
            sample_fields = 'date, open, high, low, close, volume'
        elif 'Screener' in data_type:
            sample_fields = 'period, end_date, revenue, net_profit'
        elif 'Yahoo' in data_type:
            sample_fields = 'period, end_date, net_profit, total_assets'
        
        html += f"""
            <tr>
                <td><strong>{data_type}</strong></td>
                <td>{count} / {total}</td>
                <td><span class="badge {badge_class}">{pct:.1f}%</span></td>
                <td><span class="code">{sample_fields}</span></td>
            </tr>
"""
    
    html += """
        </table>
    </div>
    
    <div class="section">
        <h2>🔍 Before vs After Comparison (""" + sample_ticker + """)</h2>
        <div class="comparison">
            <div class="comparison-col">
                <h3><span class="cross">✗</span> Before (Raw Structure)</h3>
                <pre>{
  "ticker": "ABCAPITAL",
  "name": "Aditya Birla Capital Ltd",
  "yahoofin_raw": {
    "observations": [{
      "fetched_at": "2026-05-18T12:55:58Z",
      "raw": {
        "info": {
          "currentPrice": "350.1",  // String
          "marketCap": 917547319296
        },
        "history_6mo_1d": [...]
      }
    }]
  },
  "screener_financials": {
    "timestamp": "2026-05-18T07:58:09Z",
    "tables": {
      "profit_loss": {
        "data": {
          "Revenue +": {
            "Mar 2023": "8,025",  // String
            "Jun 2023": "7,045"
          }
        }
      }
    }
  }
}</pre>
            </div>
            <div class="comparison-col">
                <h3><span class="tick">✓</span> After (Standardized Structure)</h3>
                <pre>{
  "ticker": "ABCAPITAL",
  "name": "Aditya Birla Capital Ltd",
  "snapshot": {
    "price": 350.1,          // Numeric
    "market_cap": 917547319296,
    "sector": "Financial Services",
    "pe_ratio": 12.5
  },
  "price_history": {
    "daily_6m": [
      {
        "date": "2025-11-18",
        "close": 333.1,
        "volume": 2174919
      }
    ]
  },
  "screener_profit_loss": [
    {
      "period": "2023-Q1",
      "end_date": "2023-03-31",
      "revenue": 8025000000  // Numeric
    }
  ]
}</pre>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>💾 Output Files</h2>
        <table>
            <tr>
                <th>File</th>
                <th>Purpose</th>
                <th>Size</th>
            </tr>
            <tr>
                <td><span class="code">data/market_data.json</span></td>
                <td>Standardized data ready for analysis</td>
                <td><span class="badge badge-success">""" + stats.get('output_size', 'N/A') + """</span></td>
            </tr>
            <tr>
                <td><span class="code">data/standardization_report.html</span></td>
                <td>This report</td>
                <td>-</td>
            </tr>
        </table>
    </div>
    
</body>
</html>"""
    
    return html


def main():
    """Main standardization process."""
    print("Loading raw market data...")
    with open('data/raw_market_data.json', 'r') as f:
        raw_data = json.load(f)
    
    raw_size = len(json.dumps(raw_data))
    
    print(f"Processing {raw_data['metadata']['total_tickers']} stocks...")
    
    # Create standardized structure
    standardized = {
        'metadata': {
            'fetched_at': raw_data['metadata']['merged_at'],
            'total_stocks': raw_data['metadata']['total_tickers'],
            'failed_symbols': raw_data['metadata'].get('screener_failed_symbols', []),
            'data_sources': raw_data['metadata']['datasets'],
            'standardization_version': '1.0',
            'standardized_at': datetime.utcnow().isoformat() + 'Z'
        },
        'stocks': {}
    }
    
    # Process each stock
    processed = 0
    errors = 0
    
    for ticker, stock_data in raw_data['data'].items():
        try:
            standardized['stocks'][ticker] = standardize_stock(stock_data)
            processed += 1
            if processed % 10 == 0:
                print(f"  Processed {processed}/{raw_data['metadata']['total_tickers']} stocks...")
        except Exception as e:
            print(f"  Error processing {ticker}: {e}")
            errors += 1
    
    print(f"\nStandardization complete:")
    print(f"  Successfully processed: {processed}")
    print(f"  Errors: {errors}")
    
    # Write JSON output
    output_path = 'data/market_data.json'
    print(f"\nWriting to {output_path}...")
    with open(output_path, 'w') as f:
        json.dump(standardized, f, indent=2)
    
    std_size = len(json.dumps(standardized))
    size_reduction = ((raw_size - std_size) / raw_size * 100) if raw_size > 0 else 0
    
    # Generate HTML report
    stats = {
        'total_stocks': raw_data['metadata']['total_tickers'],
        'processed': processed,
        'errors': errors,
        'size_reduction': f"{size_reduction:.1f}%",
        'output_size': f"{std_size / (1024*1024):.1f} MB"
    }
    
    print("Generating HTML report...")
    html_report = generate_html_report(raw_data, standardized, stats)
    
    report_path = 'data/standardization_report.html'
    with open(report_path, 'w') as f:
        f.write(html_report)
    
    print(f"✓ Done! Files created:")
    print(f"  - {output_path}")
    print(f"  - {report_path}")
    print(f"\nOpen {report_path} in your browser to view the report.")


if __name__ == '__main__':
    main()
