"""
CAAS — Daily PM2.5 Fetch (Live)
Fetches yesterday's PM2.5 for Chiang Mai from air4thai API and
appends it to pm25_consolidated.csv.

Called by: .github/workflows/daily_pipeline.yml  step [1/5]

Usage:
    python fetch_pm25_live.py
    python fetch_pm25_live.py --date 2026-04-08
"""

import os
import sys
import json
import argparse
import requests
import pandas as pd
from datetime import datetime, timedelta

# ── Config ─────────────────────────────────────────────────
BASE       = os.path.dirname(os.path.abspath(__file__))
PM25_CSV   = os.path.join(BASE, "..", "03_Data", "processed", "pm25_consolidated.csv")

# air4thai station IDs for Chiang Mai
# 35T = Chiang Mai Municipal area, 36T = backup station
STATION_IDS = ["35T", "36T"]

# air4thai API endpoint (public, no key needed)
API_BASE = "http://air4thai.pcd.go.th/services/getNewAQI_JSON.php"

ALERT_THRESHOLD = 50.0


def fetch_yesterday_pm25(target_date: datetime.date) -> float | None:
    """
    Fetch daily average PM2.5 for Chiang Mai from air4thai.
    Returns the value or None if unavailable.
    """
    date_str = target_date.strftime("%Y-%m-%d")

    for station_id in STATION_IDS:
        try:
            params = {
                "stationID": station_id,
                "param":     "PM25",
                "type":      "daily",
                "sdate":     date_str,
                "edate":     date_str,
            }
            resp = requests.get(API_BASE, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            # Parse air4thai response format
            stations = data.get("stations", [])
            if not stations:
                continue

            station_data = stations[0]
            aqiData = station_data.get("AQILast", {})

            # Try PM2.5 value
            pm25_entry = aqiData.get("PM25", {})
            value = pm25_entry.get("value", None)

            if value is not None and value != "-":
                pm25_val = float(value)
                print(f"   ✅  Station {station_id}: PM2.5 = {pm25_val:.1f} µg/m³ on {date_str}")
                return pm25_val

        except (requests.RequestException, json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"   ⚠️   Station {station_id} failed: {e}")
            continue

    return None


def append_to_csv(date: datetime.date, pm25: float, csv_path: str):
    """Append a new row to pm25_consolidated.csv, skip if date already exists."""
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    new_row = pd.DataFrame([{
        "date":  date.strftime("%Y-%m-%d"),
        "pm25":  round(pm25, 2),
        "alert": int(pm25 > ALERT_THRESHOLD),
    }])

    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, parse_dates=["date"])
        date_ts = pd.Timestamp(date)

        if date_ts in df["date"].values:
            print(f"   ℹ️   {date} already in CSV — skipping append")
            return False

        df = pd.concat([df, new_row], ignore_index=True)
        df = df.sort_values("date").reset_index(drop=True)
    else:
        df = new_row

    df.to_csv(csv_path, index=False)
    print(f"   ✅  Appended {date} → {csv_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Fetch live PM2.5 from air4thai")
    parser.add_argument("--date", type=str, default=None,
                        help="Date to fetch (YYYY-MM-DD). Defaults to yesterday.")
    args = parser.parse_args()

    target_date = (
        datetime.strptime(args.date, "%Y-%m-%d").date()
        if args.date
        else (datetime.now() - timedelta(days=1)).date()
    )

    print(f"📡  Fetching PM2.5 for {target_date} from air4thai...")

    pm25 = fetch_yesterday_pm25(target_date)

    if pm25 is None:
        print(f"❌  Could not retrieve PM2.5 for {target_date}. Pipeline will continue with existing data.")
        # Exit 0 so the pipeline doesn't hard-fail on a single missing day
        sys.exit(0)

    appended = append_to_csv(target_date, pm25, PM25_CSV)
    if not appended:
        sys.exit(0)

    print(f"✅  Done — PM2.5 on {target_date}: {pm25:.1f} µg/m³  "
          f"({'ALERT' if pm25 > ALERT_THRESHOLD else 'OK'})")


if __name__ == "__main__":
    main()
