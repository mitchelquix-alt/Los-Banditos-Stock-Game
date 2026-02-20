#!/usr/bin/env python3
"""
Fetch YTD daily closing prices from Alpha Vantage for all Los Banditos stocks.
Writes data/prices.json AND updates the embedded PRICES in index.html.

Usage: AV_API_KEY=xxx python3 fetch_prices.py
"""

import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime

API_KEY = os.environ.get("AV_API_KEY", "")
if not API_KEY:
    print("ERROR: Set AV_API_KEY environment variable")
    sys.exit(1)

STOCKS = [
    {"ticker": "HOOD", "av_symbol": "HOOD", "p0": 115.48, "currency": "USD"},
    {"ticker": "TTD",  "av_symbol": "TTD",  "p0": 38.19,  "currency": "USD"},
    {"ticker": "GMAB", "av_symbol": "GMAB", "p0": 31.18,  "currency": "USD"},
    {"ticker": "XXI",  "av_symbol": "XXI",  "p0": 8.85,   "currency": "USD"},
    {"ticker": "FOUR", "av_symbol": "FOUR", "p0": 63.31,  "currency": "USD"},
    {"ticker": "DFEN", "av_symbol": "DFEN", "p0": 52.49,  "currency": "EUR"},
]

START_DATE = "2026-01-02"
BASE_URL = "https://www.alphavantage.co/query"
ROOT = os.path.join(os.path.dirname(__file__), "..")


def fetch_daily(symbol):
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
            print(f"  WARNING: No data for {symbol}: {data.get('Note', data.get('Information', data.get('Error Message', 'Unknown')))}")
            return None
        return data["Time Series (Daily)"]
    except Exception as e:
        print(f"  ERROR fetching {symbol}: {e}")
        return None


def load_existing():
    path = os.path.join(ROOT, "data", "prices.json")
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def update_index_html(stocks_data):
    """Replace the embedded PRICES object in index.html with fresh data."""
    html_path = os.path.join(ROOT, "index.html")
    try:
        with open(html_path, "r") as f:
            html = f.read()
    except FileNotFoundError:
        print("  WARNING: index.html not found, skipping embedded update")
        return

    # Build the new PRICES JS object
    lines = ["const PRICES = {"]
    for ticker, sd in stocks_data.items():
        daily_str = json.dumps(sd.get("daily", {}), separators=(",", ":"))
        lines.append(f'  "{ticker}": {{')
        lines.append(f'    "p0": {sd["p0"]}, "p1": {sd.get("p1", sd["p0"])}, "currency": "{sd["currency"]}",')
        lines.append(f'    "daily": {daily_str}')
        lines.append("  },")
    lines.append("};")
    new_prices = "\n".join(lines)

    # Replace existing PRICES block
    pattern = r"const PRICES = \{[\s\S]*?\n\};"
    if re.search(pattern, html):
        html = re.sub(pattern, new_prices, html, count=1)
        with open(html_path, "w") as f:
            f.write(html)
        print("  Updated embedded PRICES in index.html")
    else:
        print("  WARNING: Could not find PRICES block in index.html")


def main():
    print("Los Banditos Price Updater")
    print("=" * 40)

    existing = load_existing()
    result = {
        "updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "start_date": START_DATE,
        "stocks": {}
    }

    for i, stock in enumerate(STOCKS):
        ticker = stock["ticker"]
        p0 = stock["p0"]

        ts = fetch_daily(stock["av_symbol"])
        # Rate limit: wait 13s between calls (5 calls/min limit)
        if i < len(STOCKS) - 1:
            time.sleep(13)

        if ts is None:
            if existing and ticker in existing.get("stocks", {}):
                print(f"  Using cached data for {ticker}")
                result["stocks"][ticker] = existing["stocks"][ticker]
            else:
                result["stocks"][ticker] = {
                    "p0": p0, "p1": p0, "currency": stock["currency"],
                    "daily": {}, "error": "No data available"
                }
            continue

        daily = {}
        for date_str, values in sorted(ts.items()):
            if date_str >= START_DATE:
                daily[date_str] = round(float(values["4. close"]), 2)

        if daily:
            latest_date = max(daily.keys())
            latest_price = daily[latest_date]
            ytd = round((latest_price - p0) / p0 * 100, 2)
            print(f"  {ticker}: ${p0} -> ${latest_price} ({ytd:+.1f}%) [{len(daily)} days]")
        else:
            latest_price = p0
            ytd = 0
            print(f"  {ticker}: No YTD data found")

        result["stocks"][ticker] = {
            "p0": p0, "p1": latest_price, "ytd": ytd,
            "currency": stock["currency"], "daily": daily
        }

    # Write prices.json
    out_path = os.path.join(ROOT, "data", "prices.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nWritten to {out_path}")

    # Also update embedded data in index.html
    update_index_html(result["stocks"])

    print(f"Done! Updated: {result['updated']}")


if __name__ == "__main__":
    main()
