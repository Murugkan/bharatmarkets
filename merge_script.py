#!/usr/bin/env python3
"""
4-Dataset Merger - Ticker Level Consolidation
Merges 4 financial datasets by ticker key without any computations.

Input: data/*.json (yahoofin_raw_data, screener_raw_data, screener_financials, yahoofin_financials)
Output: data/raw_market_data.json
Log: data/logs/raw_market_data.log
"""

import json
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict


def setup_logging(repo_root=None, log_dir="data/logs", log_file="raw_market_data.log"):
    """Setup logging to file - uses current working directory for GitHub Actions compatibility"""
    if repo_root is None:
        repo_root = Path.cwd()  # Use current working directory (repo root in GitHub Actions)
    
    log_path = Path(repo_root) / log_dir
    log_path.mkdir(parents=True, exist_ok=True)
    
    log_file_path = log_path / log_file
    
    logger = logging.getLogger("MERGE-4DATASETS")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    
    fh = logging.FileHandler(log_file_path, mode='w', encoding='utf-8')
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    return logger, log_file_path


def save_json(filepath, data):
    """Save JSON file"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Error saving {filepath}: {str(e)}")
        return False


def load_json(filepath):
    """Load JSON file safely"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading {filepath}: {str(e)}")
        return None


def get_all_tickers(ds1, ds2, ds3, ds4):
    """Get union of all tickers from all 4 datasets"""
    tickers = set()
    
    if ds1:
        tickers.update(ds1.keys())
    
    if ds2:
        tickers.update(ds2.keys())
    
    if ds3 and "data" in ds3:
        tickers.update(ds3["data"].keys())
    
    if ds4:
        tickers.update(ds4.keys())
    
    return sorted(list(tickers))


def merge_datasets(ds1, ds2, ds3, ds4, output_file="data/raw_market_data.json", logger=None):
    """
    Merge 4 datasets at ticker level without computations
    
    Args:
        ds1: yahoofin_raw_data
        ds2: screener_raw_data
        ds3: screener_financials (has metadata + data structure)
        ds4: yahoofin_financials
        output_file: Path to output merged JSON
        logger: Logger instance
    
    Returns:
        tuple: (success: bool, stats: dict)
    """
    
    if logger is None:
        logger = logging.getLogger("MERGE-4DATASETS")
    
    print("=" * 90)
    print("4-DATASET TICKER-LEVEL MERGE")
    print("=" * 90)
    
    logger.info("=" * 90)
    logger.info("4-DATASET TICKER-LEVEL MERGE")
    logger.info("=" * 90)
    
    # Get all tickers
    all_tickers = get_all_tickers(ds1, ds2, ds3, ds4)
    msg = f"Total unique tickers found: {len(all_tickers)}"
    print(f"\n✓ {msg}")
    logger.info(msg)
    
    # Initialize merged structure
    merged = {
        "metadata": {
            "merged_at": datetime.now(timezone.utc).isoformat(),
            "total_tickers": len(all_tickers),
            "datasets": [
                "yahoofin_raw_data",
                "screener_raw_data",
                "screener_financials",
                "yahoofin_financials"
            ]
        },
        "data": {}
    }
    
    # Track what's available for each ticker
    ticker_stats = {
        "total": len(all_tickers),
        "with_yahoofin_raw": 0,
        "with_screener_raw": 0,
        "with_screener_fin": 0,
        "with_yahoofin_fin": 0,
        "with_all_4": 0,
        "with_at_least_1": 0,
    }
    
    # Merge by ticker
    msg = f"Merging {len(all_tickers)} tickers..."
    print(f"\n🔄 {msg}")
    logger.info(msg)
    
    for ticker in all_tickers:
        ticker_data = {"ticker": ticker}
        sources_found = 0
        
        # Add name and ISIN from first available source
        for source_data in [ds1, ds2, ds4]:
            if source_data and ticker in source_data:
                if "name" in source_data[ticker]:
                    ticker_data["name"] = source_data[ticker]["name"]
                if "isin" in source_data[ticker]:
                    ticker_data["isin"] = source_data[ticker]["isin"]
                break
        
        # Dataset 1: yahoofin_raw_data
        if ds1 and ticker in ds1:
            ticker_data["yahoofin_raw"] = ds1[ticker]
            ticker_stats["with_yahoofin_raw"] += 1
            sources_found += 1
        
        # Dataset 2: screener_raw_data
        if ds2 and ticker in ds2:
            ticker_data["screener_raw"] = ds2[ticker]
            ticker_stats["with_screener_raw"] += 1
            sources_found += 1
        
        # Dataset 3: screener_financials (nested under "data" key)
        if ds3 and "data" in ds3 and ticker in ds3["data"]:
            ticker_data["screener_financials"] = ds3["data"][ticker]
            ticker_stats["with_screener_fin"] += 1
            sources_found += 1
        
        # Dataset 4: yahoofin_financials
        if ds4 and ticker in ds4:
            ticker_data["yahoofin_financials"] = ds4[ticker]
            ticker_stats["with_yahoofin_fin"] += 1
            sources_found += 1
        
        # Add to merged data
        merged["data"][ticker] = ticker_data
        
        # Update stats
        if sources_found > 0:
            ticker_stats["with_at_least_1"] += 1
        if sources_found == 4:
            ticker_stats["with_all_4"] += 1
    
    # Add metadata about dataset-specific info
    if ds3 and "metadata" in ds3:
        merged["metadata"]["screener_financials_info"] = ds3["metadata"]
    
    if ds3 and "failed_symbols" in ds3:
        merged["metadata"]["screener_failed_symbols"] = ds3["failed_symbols"]
    
    # Save merged file
    msg = f"Saving to {output_file}..."
    print(f"\n💾 {msg}")
    logger.info(msg)
    
    if not save_json(output_file, merged):
        logger.error("Failed to save merged file")
        return False, ticker_stats
    
    # Print statistics
    print("\n" + "=" * 90)
    print("MERGE STATISTICS")
    print("=" * 90)
    logger.info("=" * 90)
    logger.info("MERGE STATISTICS")
    logger.info("=" * 90)
    
    stats_lines = [
        f"Total Tickers: {ticker_stats['total']}",
        f"With yahoofin_raw: {ticker_stats['with_yahoofin_raw']} ({ticker_stats['with_yahoofin_raw']/ticker_stats['total']*100:.1f}%)",
        f"With screener_raw: {ticker_stats['with_screener_raw']} ({ticker_stats['with_screener_raw']/ticker_stats['total']*100:.1f}%)",
        f"With screener_financials: {ticker_stats['with_screener_fin']} ({ticker_stats['with_screener_fin']/ticker_stats['total']*100:.1f}%)",
        f"With yahoofin_financials: {ticker_stats['with_yahoofin_fin']} ({ticker_stats['with_yahoofin_fin']/ticker_stats['total']*100:.1f}%)",
        f"With all 4 datasets: {ticker_stats['with_all_4']} ({ticker_stats['with_all_4']/ticker_stats['total']*100:.1f}%)",
        f"With at least 1 dataset: {ticker_stats['with_at_least_1']} ({ticker_stats['with_at_least_1']/ticker_stats['total']*100:.1f}%)",
    ]
    
    for line in stats_lines:
        print(line)
        logger.info(line)
    
    print("\n" + "=" * 90)
    print("✅ MERGE COMPLETE")
    print("=" * 90)
    logger.info("=" * 90)
    logger.info("✅ MERGE COMPLETE")
    logger.info("=" * 90)
    
    print(f"Output file: {output_file}")
    print(f"Total tickers merged: {len(all_tickers)}")
    
    logger.info(f"Output file: {output_file}")
    logger.info(f"Total tickers merged: {len(all_tickers)}")
    
    return True, ticker_stats


def main():
    """Main execution - GitHub Actions compatible with root-relative paths"""
    
    # Get repository root - use current working directory for GitHub Actions
    repo_root = Path.cwd()  # This will be repo root in GitHub Actions
    
    # Setup logging
    logger, log_file = setup_logging(repo_root=repo_root)
    logger.info("=" * 90)
    logger.info("4-DATASET MERGER - START")
    logger.info("=" * 90)
    logger.info(f"Repository root: {repo_root}")
    logger.info(f"Current working directory: {Path.cwd()}")
    
    # File paths (relative to repository root)
    data_dir = repo_root / "data"
    yahoofin_raw_file = data_dir / "yahoofin_raw_data.json"
    screener_raw_file = data_dir / "screener_raw_data.json"
    screener_fin_file = data_dir / "screener_financials.json"
    yahoofin_fin_file = data_dir / "yahoofin_financials.json"
    output_file = data_dir / "raw_market_data.json"
    
    logger.info(f"Output file: {output_file}")
    logger.info(f"Log file: {log_file}")
    
    # Verify files exist
    print("📁 Checking source files...")
    print(f"📍 Repository root: {repo_root}\n")
    logger.info(f"Checking source files from root: {repo_root}")
    
    files_to_check = [
        (yahoofin_raw_file, "Yahoo Finance Raw"),
        (screener_raw_file, "Screener Raw"),
        (screener_fin_file, "Screener Financials"),
        (yahoofin_fin_file, "Yahoo Finance Financials"),
    ]
    
    for filepath, name in files_to_check:
        if filepath.exists():
            size = filepath.stat().st_size / (1024*1024)
            msg = f"✓ {name}: {filepath.relative_to(repo_root)} ({size:.1f} MB)"
            print(msg)
            logger.info(msg)
        else:
            msg = f"❌ {name}: {filepath.relative_to(repo_root)} - NOT FOUND"
            print(msg)
            logger.error(msg)
            return False
    
    # Load datasets
    print("\n📥 Loading datasets...")
    logger.info("Loading datasets...")
    
    ds1 = load_json(yahoofin_raw_file)
    ds2 = load_json(screener_raw_file)
    ds3 = load_json(screener_fin_file)
    ds4 = load_json(yahoofin_fin_file)
    
    if not all([ds1, ds2, ds3, ds4]):
        msg = "Failed to load one or more datasets"
        print(f"❌ {msg}")
        logger.error(msg)
        return False
    
    print("✓ All datasets loaded successfully")
    logger.info("All datasets loaded successfully")
    
    # Perform merge
    success, stats = merge_datasets(ds1, ds2, ds3, ds4, str(output_file), logger)
    
    if success:
        logger.info("=" * 90)
        logger.info("MERGE SUCCESSFUL")
        logger.info("=" * 90)
        logger.info(f"Output: {output_file.relative_to(repo_root)}")
        logger.info(f"Total tickers: {stats['total']}")
        logger.info(f"Coverage: {stats['with_all_4']} companies with all 4 datasets ({stats['with_all_4']/stats['total']*100:.1f}%)")
    else:
        logger.error("Merge failed")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
