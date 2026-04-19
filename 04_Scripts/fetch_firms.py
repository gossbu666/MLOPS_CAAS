"""
CAAS — NASA FIRMS Fire Hotspot Data Fetcher
Fetches MODIS/VIIRS fire hotspot data for Northern Thailand (2011–2025)
and aggregates daily hotspot counts near Chiang Mai.

Data Source : NASA FIRMS (Fire Information for Resource Management System)
Product     : MODIS (MCD14ML) — available from 2000, global coverage
API Docs    : https://firms.modaps.eosdis.nasa.gov/api/

Station Reference: Chiang Mai City Hall area
Coordinates: 18.7883° N, 98.9853° E

Output columns:
  date           — YYYY-MM-DD
  hotspot_count  — number of fire pixels within BBOX (Chiang Mai region)
  hotspot_50km   — hotspots within 50 km radius of station
  hotspot_100km  — hotspots within 100 km radius of station
  mean_frp_50km  — mean Fire Radiative Power (MW) within 50 km (intensity proxy)

Usage:
    # Make sure .env is set up with FIRMS_MAP_KEY
    python fetch_firms.py
"""

import requests
import pandas as pd
import numpy as np
import os
import time
import random
from io import StringIO
from typing import Optional
from dotenv import load_dotenv

# ── Load API Key ──────────────────────────────────────────
load_dotenv()
MAP_KEY = os.getenv("FIRMS_MAP_KEY")
if not MAP_KEY:
    raise EnvironmentError("FIRMS_MAP_KEY not found in .env — please set it first.")

# ── Config ────────────────────────────────────────────────
# Station coordinates (Chiang Mai)
STATION_LAT = 18.7883
STATION_LON = 98.9853

# Bounding box: Northern Thailand + cross-border areas (fires often originate in Myanmar/Laos)
# W, S, E, N  (longitude_min, latitude_min, longitude_max, latitude_max)
BBOX = "97.0,17.0,101.0,21.5"

# Years to fetch
START_YEAR = int(os.getenv("FIRMS_START_YEAR", "2011"))
END_YEAR   = int(os.getenv("FIRMS_END_YEAR", "2025"))

# FIRMS product (MODIS = longer history, VIIRS = higher resolution but from 2012)
PRODUCT = "MODIS_NRT"          # Use NRT (near-real-time) endpoint — works for archive too
PRODUCT_ARCHIVE = "MODIS_SP"   # Standard product for archived years
MAX_DAYS_PER_CALL = 5           # FIRMS area API currently accepts day_range in [1..5]
MAX_RETRIES = 3
REQUEST_PAUSE_SEC = 1.2
LIMIT_COOLDOWN_SEC = 20
MAX_CONSECUTIVE_LIMIT_HITS = 5
EXTENDED_COOLDOWN_SEC = 90
MAX_RETRY_PASSES = 4
PASS_COOLDOWN_SEC = 120

OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "03_Data", "processed", "firms_consolidated.csv"
)
CACHE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "03_Data", "raw", "firms_yearly_cache"
)

# ── Haversine Distance ────────────────────────────────────
def haversine_km(lat1, lon1, lat2_arr, lon2_arr):
    """Vectorized haversine distance from (lat1, lon1) to arrays of points."""
    R = 6371.0
    dlat = np.radians(lat2_arr - lat1)
    dlon = np.radians(lon2_arr - lon1)
    a    = np.sin(dlat / 2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2_arr)) * np.sin(dlon / 2)**2
    return R * 2 * np.arcsin(np.sqrt(a))

# ── Fetch one year of FIRMS data ─────────────────────────
def fetch_firms_year(year: int, map_key: str) -> Optional[pd.DataFrame]:
    """
    Fetch all MODIS fire hotspots for a given year within BBOX.
    Uses the FIRMS CSV area API (returns CSV with one row per hotspot detection).

    Returns DataFrame or None if request fails.
    """
    # FIRMS area API endpoint
    # Format: /api/area/csv/{MAP_KEY}/{product}/{area}/{day_range}/{date}
    # FIRMS area endpoint allows day_range in [1..5], so we fetch in 5-day chunks.

    all_dfs = []

    # Generate API-sized chunks for the year
    start = pd.Timestamp(f"{year}-01-01")
    end   = pd.Timestamp(f"{year}-12-31")

    current = start

    session = requests.Session()
    session.headers.update({"User-Agent": "CAAS-FIRMS-Fetcher/1.0"})
    adaptive_pause = REQUEST_PAUSE_SEC
    consecutive_limit_hits = 0

    chunks = []
    while current <= end:
        chunk_end = min(current + pd.Timedelta(days=MAX_DAYS_PER_CALL - 1), end)
        days_in_chunk = (chunk_end - current).days + 1
        chunks.append((current, chunk_end, days_in_chunk, current.strftime("%Y-%m-%d")))
        current = chunk_end + pd.Timedelta(days=1)

    pending_chunks = chunks
    pass_no = 1

    while pending_chunks and pass_no <= MAX_RETRY_PASSES:
        if pass_no > 1:
            print(
                f"\n   🔁 Retry pass {pass_no}/{MAX_RETRY_PASSES} for "
                f"{len(pending_chunks)} rate-limited chunks"
            )

        next_pending = []

        for current, chunk_end, days_in_chunk, date_str in pending_chunks:

            url = (
                f"https://firms.modaps.eosdis.nasa.gov/api/area/csv"
                f"/{map_key}/MODIS_SP/{BBOX}/{days_in_chunk}/{date_str}"
            )

            got_response = False
            deferred_by_limit = False
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    resp = session.get(url, timeout=30)

                    if resp.status_code == 200:
                        got_response = True
                        text = resp.text.strip()
                        consecutive_limit_hits = 0
                        adaptive_pause = max(REQUEST_PAUSE_SEC, adaptive_pause * 0.95)
                        if text and text != "acq_date" and len(text) > 50:
                            try:
                                df_chunk = pd.read_csv(StringIO(text))
                                if len(df_chunk) > 0:
                                    all_dfs.append(df_chunk)
                            except Exception:
                                pass  # Empty/unparseable chunk, skip
                        break

                    body_hint = (resp.text or "").strip().splitlines()
                    body_hint = body_hint[0] if body_hint else "(no response body)"

                    if "Exceeding allowed transaction limit" in body_hint:
                        consecutive_limit_hits += 1
                        adaptive_pause = min(adaptive_pause + 0.5, 4.0)

                        if attempt < MAX_RETRIES:
                            wait_s = LIMIT_COOLDOWN_SEC * attempt + random.uniform(0.5, 2.5)
                            print(
                                f"   ⚠️  Transaction limit hit for {date_str} "
                                f"(attempt {attempt}/{MAX_RETRIES}) — cooling down {wait_s:.1f}s"
                            )
                            time.sleep(wait_s)
                            continue

                        deferred_by_limit = True
                        print(f"   ⏭️  Deferring {date_str} to next retry pass (transaction limit)")

                        if consecutive_limit_hits >= MAX_CONSECUTIVE_LIMIT_HITS:
                            print(
                                f"   🧊  Too many consecutive limit hits ({consecutive_limit_hits}) "
                                f"— extended cooldown {EXTENDED_COOLDOWN_SEC}s"
                            )
                            time.sleep(EXTENDED_COOLDOWN_SEC)
                            consecutive_limit_hits = 0
                        break

                    # FIRMS sometimes returns transient 400/5xx for valid URLs; retry with backoff.
                    if resp.status_code in {400, 429, 500, 502, 503, 504} and attempt < MAX_RETRIES:
                        wait_s = 1.5 * attempt
                        print(
                            f"   ⚠️  HTTP {resp.status_code} for {date_str} "
                            f"(attempt {attempt}/{MAX_RETRIES}) — retrying in {wait_s:.1f}s"
                        )
                        time.sleep(wait_s)
                        continue

                    print(f"   ⚠️  HTTP {resp.status_code} for {date_str}: {body_hint}")
                    break

                except requests.RequestException as e:
                    if attempt < MAX_RETRIES:
                        wait_s = 1.5 * attempt
                        print(
                            f"   ⚠️  Request error for {date_str} "
                            f"(attempt {attempt}/{MAX_RETRIES}): {e} — retrying in {wait_s:.1f}s"
                        )
                        time.sleep(wait_s)
                    else:
                        print(f"   ⚠️  Request error for {date_str}: {e}")

            if not got_response and deferred_by_limit:
                next_pending.append((current, chunk_end, days_in_chunk, date_str))

            # Small delay to reduce transaction-limit errors from FIRMS.
            time.sleep(adaptive_pause + random.uniform(0.05, 0.35))

        pending_chunks = next_pending
        pass_no += 1

        if pending_chunks and pass_no <= MAX_RETRY_PASSES:
            cooldown = PASS_COOLDOWN_SEC * (pass_no - 1)
            print(
                f"   ⏳ Pass cooldown {cooldown}s before retrying {len(pending_chunks)} remaining chunks"
            )
            time.sleep(cooldown)

    if pending_chunks:
        print(
            f"   ⚠️  {len(pending_chunks)} chunks still rate-limited after {MAX_RETRY_PASSES} passes; "
            "continuing with available data."
        )

    if not all_dfs:
        return None

    df_year = pd.concat(all_dfs, ignore_index=True)
    return df_year


# ── Main ──────────────────────────────────────────────────
print("🔥  Fetching NASA FIRMS fire hotspot data...")
print(f"   Station  : Chiang Mai ({STATION_LAT}°N, {STATION_LON}°E)")
print(f"   BBox     : {BBOX} (Northern Thailand + border regions)")
print(f"   Period   : {START_YEAR} → {END_YEAR}")
print(f"   API Key  : {MAP_KEY[:8]}... (hidden)")
print(f"   Cache    : {CACHE_DIR}")
print()

all_raw = []
os.makedirs(CACHE_DIR, exist_ok=True)

for year in range(START_YEAR, END_YEAR + 1):
    year_cache_path = os.path.join(CACHE_DIR, f"firms_raw_{year}.csv")

    if os.path.exists(year_cache_path):
        print(f"📅  Fetching {year}... ♻️  Using cache", flush=True)
        try:
            df_year_cache = pd.read_csv(year_cache_path)
            if len(df_year_cache) > 0:
                all_raw.append(df_year_cache)
                print(f"   ✅ {len(df_year_cache):,} hotspot detections (cached)")
                continue
            print("   ⚠️  Cache empty — refetching")
        except Exception as e:
            print(f"   ⚠️  Cache read failed ({e}) — refetching")

    print(f"📅  Fetching {year}...", end="", flush=True)
    df_year = fetch_firms_year(year, MAP_KEY)

    if df_year is None or len(df_year) == 0:
        print(f" ⚠️  No data returned")
        continue

    print(f" ✅ {len(df_year):,} hotspot detections")
    try:
        df_year.to_csv(year_cache_path, index=False)
    except Exception as e:
        print(f"   ⚠️  Could not write cache for {year}: {e}")
    all_raw.append(df_year)

if not all_raw:
    print("\n❌ No data fetched at all. Check your API key and internet connection.")
    exit(1)

# ── Combine raw data ──────────────────────────────────────
print(f"\n🔧  Processing {sum(len(d) for d in all_raw):,} total hotspot records...")

df_raw = pd.concat(all_raw, ignore_index=True)

# Parse date and coordinates
df_raw['acq_date'] = pd.to_datetime(df_raw['acq_date'], errors='coerce')
df_raw = df_raw.dropna(subset=['acq_date', 'latitude', 'longitude'])
df_raw['latitude']  = pd.to_numeric(df_raw['latitude'],  errors='coerce')
df_raw['longitude'] = pd.to_numeric(df_raw['longitude'], errors='coerce')
df_raw = df_raw.dropna(subset=['latitude', 'longitude'])

# Compute distance from Chiang Mai station
df_raw['dist_km'] = haversine_km(
    STATION_LAT, STATION_LON,
    df_raw['latitude'].values,
    df_raw['longitude'].values
)

# FRP column (Fire Radiative Power, MW) — may be named 'frp'
frp_col = 'frp' if 'frp' in df_raw.columns else None

# ── Aggregate to daily ────────────────────────────────────
print("📊  Aggregating to daily counts...")

daily_records = []

for date, grp in df_raw.groupby('acq_date'):
    grp_50  = grp[grp['dist_km'] <= 50]
    grp_100 = grp[grp['dist_km'] <= 100]

    mean_frp_50 = np.nan
    if frp_col and len(grp_50) > 0:
        mean_frp_50 = pd.to_numeric(grp_50[frp_col], errors='coerce').mean()

    daily_records.append({
        'date'          : date.date(),
        'hotspot_count' : len(grp),             # Total in BBOX
        'hotspot_50km'  : len(grp_50),           # Within 50 km
        'hotspot_100km' : len(grp_100),          # Within 100 km
        'mean_frp_50km' : round(mean_frp_50, 2) if not np.isnan(mean_frp_50) else np.nan,
    })

df_daily = pd.DataFrame(daily_records)
df_daily['date'] = pd.to_datetime(df_daily['date'])
df_daily = df_daily.sort_values('date').reset_index(drop=True)

# ── Fill missing dates with 0 hotspots ───────────────────
# Fires = 0 on days not in the dataset (no NaN gaps)
full_range = pd.date_range(
    start=f"{START_YEAR}-01-01",
    end=f"{END_YEAR}-12-31",
    freq="D"
)
df_daily = (
    df_daily
    .set_index('date')
    .reindex(full_range)
    .rename_axis('date')
    .reset_index()
)
# Fill count columns with 0 (no fire detected)
for col in ['hotspot_count', 'hotspot_50km', 'hotspot_100km']:
    df_daily[col] = df_daily[col].fillna(0).astype(int)
# mean_frp_50km stays NaN on days with 0 hotspots

# ── Summary ──────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"Total days      : {len(df_daily)}")
print(f"Date range      : {df_daily['date'].min().date()} → {df_daily['date'].max().date()}")
print(f"Days with fire  : {(df_daily['hotspot_50km'] > 0).sum()} (within 50 km)")
print(f"Max hotspot/day : {df_daily['hotspot_50km'].max()} (within 50 km)")
print(f"\nHotspot stats (50km radius):")
print(df_daily['hotspot_50km'].describe().round(2))

# ── Save ─────────────────────────────────────────────────
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
df_daily.to_csv(OUTPUT_PATH, index=False)
print(f"\n✅  Saved: {OUTPUT_PATH}")
print(f"\nSample (fire season):")
fire_days = df_daily[df_daily['hotspot_50km'] > 0].head(5)
print(fire_days.to_string(index=False))
