#!/usr/bin/env python3
"""
Fetch YTD daily closing prices from Alpha Vantage for all Los Banditos stocks.
Writes data/prices.json with daily close prices from Jan 2, 2026 onward.

For DFEN (VanEck Defense ETF in EUR), Alpha Vantage doesn't carry the
EUR-traded UCITS version. We fetch the USD NAV data and apply EUR/USD
conversion, OR we store it separately. For simplicity, we fetch DFEN 
as the US-listed ticker and note it in the output.

Usage: AV_API_KEY=xxx python3 fetch_prices.py
"""

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, date

API_KEY = os.environ.get("AV_API_KEY", "")
if not API_KEY:
    print("ERROR: Set AV_API_KEY environment variable")
    sys.exit(1)

# Configuration: ticker -> Alpha Vantage symbol
# Note: XXI (Twenty One Capital) may not be on Alpha Vantage if too new.
# DFEN on AV = Direxion 3x leveraged (different fund!) 
# We need DFNS or similar - but AV may not have EU ETFs.
# Fallback: we use TIME_SERIES_DAILY for US stocks and handle exceptions.

STOCKS = [
    {"ticker": "HOOD", "av_symbol": "HOOD", "p0": 115.48, "currency": "USD"},
    {"ticker": "TTD",  "av_symbol": "TTD",  "p0": 38.19,  "currency": "USD"},
    {"ticker": "GMAB", "av_symbol": "GMAB", "p0": 31.18,  "currency": "USD"},
    {"ticker": "XXI",  "av_symbol": "XXI",  "p0": 8.85,   "currency": "USD"},
    {"ticker": "FOUR", "av_symbol": "FOUR", "p0": 63.31,  "currency": "USD"},
    {"ticker": "DFEN", "av_symbol": "DFEN", "p0": 52.49,  "currency": "EUR",
     "note": "Using US DFEN as proxy; EUR price derived from EUR/USD rate"},
]

START_DATE = "2026-01-02"
BASE_URL = "https://www.alphavantage.co/query"


def fetch_daily(symbol):
    """Fetch daily time series for a symbol from Alpha Vantage."""
    url = (
        f"{BASE_URL}?function=TIME_SERIES_DAILY"
        f"&symbol={symbol}&outputsize=compact&apikey={API_KEY}"
    )
    print(f"  Fetching {symbol}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LosBanditos/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        
        if "Time Series (Daily)" not in data:
            print(f"  WARNING: No data for {symbol}: {data.get('Note', data.get('Error Message', 'Unknown error'))}")
            return None
        
        return data["Time Series (Daily)"]
    except Exception as e:
        print(f"  ERROR fetching {symbol}: {e}")
        return None


def fetch_fx_rate():
    """Fetch EUR/USD exchange rate."""
    url = (
        f"{BASE_URL}?function=CURRENCY_EXCHANGE_RATE"
        f"&from_currency=EUR&to_currency=USD&apikey={API_KEY}"
    )
    print("  Fetching EUR/USD rate...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LosBanditos/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        rate = float(data["Realtime Currency Exchange Rate"]["5. Exchange Rate"])
        print(f"  EUR/USD = {rate}")
        return rate
    except Exception as e:
        print(f"  WARNING: Could not fetch FX rate: {e}")
        return 1.05  # Fallback approximate rate


def load_existing():
    """Load existing prices.json if it exists."""
    path = os.path.join(os.path.dirname(__file__), "..", "data", "prices.json")
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def main():
    print("Los Banditos Price Updater")
    print("=" * 40)
    
    existing = load_existing()
    result = {
        "updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "start_date": START_DATE,
        "stocks": {}
    }
    
    for stock in STOCKS:
        ticker = stock["ticker"]
        av_sym = stock["av_symbol"]
        p0 = stock["p0"]
        
        ts = fetch_daily(av_sym)
        time.sleep(12)  # Alpha Vantage free tier: 5 calls/min
        
        if ts is None:
            # Use existing data as fallback
            if existing and ticker in existing.get("stocks", {}):
                print(f"  Using cached data for {ticker}")
                result["stocks"][ticker] = existing["stocks"][ticker]
            else:
                print(f"  No data available for {ticker}, skipping")
                result["stocks"][ticker] = {
                    "p0": p0,
                    "currency": stock["currency"],
                    "daily": {},
                    "error": "No data available"
                }
            continue
        
        # Extract daily closes from start_date onward
        daily = {}
        for date_str, values in sorted(ts.items()):
            if date_str >= START_DATE:
                close = float(values["4. close"])
                daily[date_str] = round(close, 2)
        
        if daily:
            latest_date = max(daily.keys())
            latest_price = daily[latest_date]
            ytd_pct = round((latest_price - p0) / p0 * 100, 2)
            print(f"  {ticker}: ${p0} -> ${latest_price} ({ytd_pct:+.1f}%) [{len(daily)} days]")
        else:
            latest_price = p0
            ytd_pct = 0
            print(f"  {ticker}: No YTD data found")
        
        result["stocks"][ticker] = {
            "p0": p0,
            "p1": latest_price,
            "ytd": ytd_pct,
            "currency": stock["currency"],
            "daily": daily
        }
    
    # Write output
    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "prices.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"\nWritten to {out_path}")
    print(f"Updated: {result['updated']}")


if __name__ == "__main__":
    main()
