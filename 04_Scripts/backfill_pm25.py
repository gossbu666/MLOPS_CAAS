"""
CAAS — PM2.5 Gap Backfill (Open-Meteo CAMS)
Fills missing dates in pm25_consolidated.csv using Open-Meteo's air quality
reanalysis (CAMS). Intended for recovering periods when the live pipeline
was offline (e.g. 2026-01-01 → 2026-04-20 before CI was running on schedule).

Provenance notes:
  - Open-Meteo exposes CAMS (Copernicus Atmosphere Monitoring Service)
    hourly PM2.5 at regional resolution. This is NOT a co-located point
    measurement at station 35T, so daily means differ from PCD readings.
  - Calibrated against 2025-10-01 → 2025-12-31 overlap with air4thai 35T:
      n=92 days, MAE=5.39, Pearson r=0.531, mean bias=+3.56 µg/m³
  - A constant offset correction (subtract +3.56) is applied by default
    so backfilled values share the same baseline as PCD 35T.

Station source label: "open-meteo-cams-cal" (distinguishes from PCD rows).

Usage:
    python backfill_pm25.py --start 2026-01-01 --end 2026-04-20
    python backfill_pm25.py --start 2026-01-01 --end 2026-04-20 --no-correction
"""

import os
import sys
import argparse
import requests
import pandas as pd
from datetime import date, datetime

# ── Config ─────────────────────────────────────────────────
BASE     = os.path.dirname(os.path.abspath(__file__))
PM25_CSV = os.path.join(BASE, "..", "03_Data", "processed", "pm25_consolidated.csv")

# Chiang Mai City Hall area (matches station 35T). Open-Meteo snaps to
# nearest grid cell (18.8N, 99.0E, elevation 313 m).
CHIANG_MAI_LAT = 18.7883
CHIANG_MAI_LON = 98.9853

OPEN_METEO_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
STATION_SOURCE = "open-meteo-cams-cal"

# Bias correction from overlap study (see docstring)
BIAS_OFFSET = 3.56


def fetch_open_meteo(start: date, end: date) -> pd.Series:
    """Fetch hourly PM2.5 for Chiang Mai and return daily mean."""
    resp = requests.get(
        OPEN_METEO_URL,
        params={
            "latitude":   CHIANG_MAI_LAT,
            "longitude":  CHIANG_MAI_LON,
            "hourly":     "pm2_5",
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date":   end.strftime("%Y-%m-%d"),
            "timezone":   "Asia/Bangkok",
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    times = pd.to_datetime(data["hourly"]["time"])
    vals  = pd.Series(data["hourly"]["pm2_5"], index=times, dtype="float64")
    daily = vals.resample("1D").mean().round(2)
    return daily


def main():
    parser = argparse.ArgumentParser(description="Backfill PM2.5 gaps from Open-Meteo")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD (inclusive)")
    parser.add_argument("--end",   required=True, help="End date YYYY-MM-DD (inclusive)")
    parser.add_argument("--no-correction", action="store_true",
                        help="Skip bias correction (emit raw Open-Meteo values)")
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end   = datetime.strptime(args.end,   "%Y-%m-%d").date()

    if end < start:
        print("❌  --end must be >= --start")
        sys.exit(2)

    print(f"📡  Fetching Open-Meteo PM2.5 for Chiang Mai: {start} → {end}")
    daily = fetch_open_meteo(start, end)
    if daily.empty:
        print("❌  Open-Meteo returned no data for this range")
        sys.exit(1)

    if not args.no_correction:
        daily = (daily - BIAS_OFFSET).clip(lower=0).round(2)
        print(f"   Applied bias correction (−{BIAS_OFFSET} µg/m³ offset vs PCD 35T)")
    else:
        print("   Bias correction skipped (raw CAMS values)")

    # Load existing CSV and figure out which dates need appending
    df = pd.read_csv(PM25_CSV, parse_dates=["date"])
    existing_dates = set(df["date"].dt.date)

    new_rows = []
    for ts, val in daily.items():
        d = ts.date()
        if d < start or d > end:
            continue
        if d in existing_dates:
            continue
        if pd.isna(val):
            continue
        new_rows.append({
            "date":           pd.Timestamp(d),
            "pm25":           float(val),
            "station_source": STATION_SOURCE,
            "year":           d.year,
        })

    if not new_rows:
        print("ℹ️   No new dates to append — range already covered")
        return

    print(f"   {len(new_rows)} new row(s) to append")
    new_df = pd.DataFrame(new_rows)
    df = pd.concat([df, new_df], ignore_index=True)
    df = df.sort_values("date").reset_index(drop=True)
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    df.to_csv(PM25_CSV, index=False)

    print(f"✅  Appended {len(new_rows)} rows → {PM25_CSV}")
    print(f"   Range added: {new_rows[0]['date'].date()} → {new_rows[-1]['date'].date()}")
    print(f"   Sample values: "
          f"{new_rows[0]['date'].date()}={new_rows[0]['pm25']:.1f}, "
          f"{new_rows[len(new_rows)//2]['date'].date()}={new_rows[len(new_rows)//2]['pm25']:.1f}, "
          f"{new_rows[-1]['date'].date()}={new_rows[-1]['pm25']:.1f}")


if __name__ == "__main__":
    main()
