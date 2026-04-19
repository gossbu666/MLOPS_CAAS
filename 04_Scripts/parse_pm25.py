"""
CAAS — PM2.5 Historical Data Parser
Consolidates PCD Excel files (2011–2025) into a single clean CSV.

Logic:
- 2011–2016: use 36T as primary (35T not available / too many missing)
- 2017–2025: use 35T as primary, fallback to 36T if missing
"""

import pandas as pd
import os
import numpy as np

# Paths anchored to this script's location for cross-machine reproducibility.
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, "..", "03_Data", "raw", "pm25")
OUTPUT_PATH = os.path.join(BASE_DIR, "..", "03_Data", "processed", "pm25_consolidated.csv")
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

records = []

for year in range(2011, 2026):
    path = os.path.join(DATA_DIR, f"PM2.5({year}).xlsx")
    if not os.path.exists(path):
        print(f"[SKIP] {year} — file not found")
        continue

    # Read first sheet (handles PM2.5 / Data / DATA naming)
    xl = pd.ExcelFile(path)
    sheet = xl.sheet_names[0]
    df = pd.read_excel(path, sheet_name=sheet)

    # Clean column names (remove trailing spaces)
    df.columns = [str(c).strip() for c in df.columns]

    # Parse date — drop rows with invalid dates (e.g. Thai footnotes at bottom)
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date'])
    df = df.set_index('Date')

    # Select station based on year
    if year <= 2016:
        # Use 36T as primary (35T unavailable or mostly missing)
        if '36T' in df.columns:
            pm25 = df['36T'].copy()
            source = '36T'
        else:
            print(f"[WARN] {year} — no 36T column found, skipping")
            continue
    else:
        # Use 35T as primary, fallback to 36T
        if '35T' in df.columns:
            pm25 = df['35T'].copy()
            source = '35T'
            # Fill missing with 36T backup
            if '36T' in df.columns:
                pm25 = pm25.fillna(df['36T'])
                source = '35T (fallback 36T)'
        elif '36T' in df.columns:
            pm25 = df['36T'].copy()
            source = '36T (fallback)'
            print(f"[WARN] {year} — 35T not found, using 36T")
        else:
            print(f"[WARN] {year} — neither 35T nor 36T found, skipping")
            continue

    # Build records
    year_df = pd.DataFrame({
        'date': pm25.index,
        'pm25': pm25.values,
        'station_source': source,
        'year': year
    })

    missing_count = year_df['pm25'].isna().sum()
    total = len(year_df)
    print(f"[OK] {year} | source: {source:<20} | rows: {total} | missing: {missing_count} ({missing_count/total*100:.1f}%)")

    records.append(year_df)

# Combine all years
df_all = pd.concat(records, ignore_index=True)
df_all = df_all.sort_values('date').reset_index(drop=True)

# Remove duplicate dates (just in case)
df_all = df_all.drop_duplicates(subset='date')

# Save
df_all.to_csv(OUTPUT_PATH, index=False)

print(f"\n{'='*60}")
print(f"✅ Saved: {OUTPUT_PATH}")
print(f"Total rows: {len(df_all)}")
print(f"Date range: {df_all['date'].min()} → {df_all['date'].max()}")
print(f"Missing PM2.5: {df_all['pm25'].isna().sum()} rows ({df_all['pm25'].isna().mean()*100:.1f}%)")
print(f"\nSample output:")
print(df_all.head(5).to_string(index=False))
print("...")
print(df_all.tail(3).to_string(index=False))
