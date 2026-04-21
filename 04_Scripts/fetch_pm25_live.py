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
from datetime import datetime

# ── Config ─────────────────────────────────────────────────
BASE       = os.path.dirname(os.path.abspath(__file__))
PM25_CSV   = os.path.join(BASE, "..", "03_Data", "processed", "pm25_consolidated.csv")

# air4thai station IDs for Chiang Mai (API expects lowercase).
# 35t = Chiang Mai City Hall (primary), 36t = Yupparaj School (backup).
STATION_IDS = ["35t", "36t"]

# Public endpoint — returns the latest AQI reading for every station when called
# without parameters. The query-parameter form (sdate/edate/type=daily) returns
# empty bodies as of 2026-04, so we fetch the snapshot and filter in-memory.
API_BASE = "http://air4thai.pcd.go.th/services/getNewAQI_JSON.php"

ALERT_THRESHOLD = 50.0


def fetch_latest_pm25() -> tuple[datetime.date, float, str] | None:
    """
    Fetch the latest PM2.5 reading for Chiang Mai from air4thai.
    Returns (reading_date, pm25_value, station_id) or None if unavailable.
    """
    try:
        resp = requests.get(API_BASE, timeout=15)
        resp.raise_for_status()
        stations = resp.json().get("stations", [])
    except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
        print(f"   ⚠️   air4thai endpoint failed: {e}")
        return None

    by_id = {s.get("stationID", "").lower(): s for s in stations}

    for station_id in STATION_IDS:
        station = by_id.get(station_id)
        if not station:
            print(f"   ⚠️   Station {station_id} not found in feed")
            continue

        aqi_last = station.get("AQILast", {})
        pm25_entry = aqi_last.get("PM25", {})
        raw_value = pm25_entry.get("value")
        reading_date_str = aqi_last.get("date", "")

        if raw_value in (None, "-", "-1") or not reading_date_str:
            print(f"   ⚠️   Station {station_id} has no current PM2.5 reading")
            continue

        try:
            pm25_val = float(raw_value)
            reading_date = datetime.strptime(reading_date_str, "%Y-%m-%d").date()
        except ValueError as e:
            print(f"   ⚠️   Station {station_id} returned bad data: {e}")
            continue

        print(f"   ✅  Station {station_id}: PM2.5 = {pm25_val:.1f} µg/m³ "
              f"on {reading_date} (time {aqi_last.get('time', '?')})")
        return reading_date, pm25_val, station_id

    return None


def append_to_csv(date: datetime.date, pm25: float, station_id: str, csv_path: str):
    """Append a new row to pm25_consolidated.csv, skip if date already exists."""
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    date_ts = pd.Timestamp(date)
    new_row = pd.DataFrame([{
        "date":           date_ts,
        "pm25":           round(pm25, 2),
        "station_source": station_id.upper(),
        "year":           date.year,
    }])

    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, parse_dates=["date"])

        if date_ts in df["date"].values:
            print(f"   ℹ️   {date} already in CSV — skipping append")
            return False

        df = pd.concat([df, new_row], ignore_index=True)
        df = df.sort_values("date").reset_index(drop=True)
    else:
        df = new_row

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    df.to_csv(csv_path, index=False)
    print(f"   ✅  Appended {date} → {csv_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Fetch live PM2.5 from air4thai")
    parser.add_argument("--date", type=str, default=None,
                        help="(Ignored) API returns the latest snapshot; kept for backward compat.")
    args = parser.parse_args()
    if args.date:
        print(f"   ℹ️   --date {args.date} ignored; air4thai only serves the latest snapshot.")

    print("📡  Fetching latest PM2.5 for Chiang Mai from air4thai...")

    result = fetch_latest_pm25()

    if result is None:
        print("❌  Could not retrieve PM2.5 from any station. Pipeline will continue with existing data.")
        # Exit 0 so the pipeline doesn't hard-fail on a single missing day
        sys.exit(0)

    reading_date, pm25, station_id = result

    appended = append_to_csv(reading_date, pm25, station_id, PM25_CSV)
    if not appended:
        sys.exit(0)

    print(f"✅  Done — PM2.5 on {reading_date} (station {station_id}): {pm25:.1f} µg/m³  "
          f"({'ALERT' if pm25 > ALERT_THRESHOLD else 'OK'})")


if __name__ == "__main__":
    main()
