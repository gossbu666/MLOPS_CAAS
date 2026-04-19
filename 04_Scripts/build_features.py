"""
CAAS — Feature Engineering Pipeline
Merges PM2.5, weather, and FIRMS data into a single ML-ready feature matrix.

Input files (all in 03_Data/processed/):
  pm25_consolidated.csv   — daily PM2.5 (µg/m³)
    weather_consolidated.csv / weather_chiang_mai.csv — weather variables (current/legacy schema)
  firms_consolidated.csv  — daily fire hotspot counts from NASA FIRMS

Output:
  03_Data/processed/features.csv  — 44 features + 3 target columns

Feature groups (44 total):
  Lag features      (5)  : pm25_lag1 … pm25_lag7, lag14, lag30
  Rolling stats     (6)  : roll3/7/14/30 mean + roll7/14 std
  Temporal          (8)  : month, week, doy, sin/cos month, sin/cos doy, is_haze_season
  Meteorological    (11) : temp_max/min/mean, humidity_max/min, precip, wind_speed,
                           wind_dir_sin/cos, pressure, cloud_cover
  Fire hotspot      (6)  : hotspot_50km, hotspot_100km, mean_frp_50km,
                           hotspot_7d_roll, hotspot_14d_roll, fire_flag
  Alert flags       (3)  : pm25_lag1>50, pm25_lag3>50, pm25_lag7>50
  Cross features    (5)  : lag1×temp_max, lag1×wind_speed, roll7×fire_flag,
                           precip_flag, humidity_wind

Target columns (3):
  pm25_t1, pm25_t3, pm25_t7  — PM2.5 at t+1, t+3, t+7 days ahead

Usage:
    python build_features.py
"""

import pandas as pd
import numpy as np
import os

# ── Paths ──────────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "..", "03_Data", "processed")

PM25_PATH    = os.path.join(DATA, "pm25_consolidated.csv")
WEATHER_PATHS = [
    os.path.join(DATA, "weather_consolidated.csv"),
    os.path.join(DATA, "weather_chiang_mai.csv"),
]
FIRMS_PATH   = os.path.join(DATA, "firms_consolidated.csv")
OUTPUT_PATH  = os.path.join(DATA, "features.csv")

# ── Load data ──────────────────────────────────────────────
print("📂  Loading data sources...")

df_pm25 = pd.read_csv(PM25_PATH, parse_dates=["date"])
df_pm25 = df_pm25[["date", "pm25"]].set_index("date").sort_index()
print(f"   PM2.5  : {len(df_pm25):,} rows  ({df_pm25['pm25'].isna().mean()*100:.1f}% missing)")

# ── Weather (optional — gracefully skip if not yet downloaded) ──
weather_path = next((p for p in WEATHER_PATHS if os.path.exists(p)), None)
has_weather = weather_path is not None
if has_weather:
    df_weather = pd.read_csv(weather_path, parse_dates=["date"])
    df_weather = df_weather.set_index("date").sort_index()
    print(f"   Weather: {len(df_weather):,} rows  ({os.path.basename(weather_path)})")
else:
    print("   ⚠️  weather_consolidated.csv / weather_chiang_mai.csv not found — weather features will be NaN placeholders")
    df_weather = None

# ── FIRMS (optional) ──────────────────────────────────────
has_firms = os.path.exists(FIRMS_PATH)
if has_firms:
    df_firms = pd.read_csv(FIRMS_PATH, parse_dates=["date"])
    df_firms = df_firms.set_index("date").sort_index()
    print(f"   FIRMS  : {len(df_firms):,} rows")
else:
    print("   ⚠️  firms_consolidated.csv not found — fire features will be 0 placeholders")
    df_firms = None

# ── Build feature matrix ───────────────────────────────────
print("\n🔧  Building feature matrix...")

# Start from full date range (same as PM2.5)
full_range = pd.date_range(
    start=df_pm25.index.min(),
    end=df_pm25.index.max(),
    freq="D"
)
df = pd.DataFrame(index=full_range)
df.index.name = "date"

# Raw PM2.5
df["pm25"] = df_pm25["pm25"]

# ── Group 1: Lag features ──────────────────────────────────
for lag in [1, 3, 7, 14, 30]:
    df[f"pm25_lag{lag}"] = df["pm25"].shift(lag)

# ── Group 2: Rolling statistics ───────────────────────────
for window in [3, 7, 14, 30]:
    df[f"pm25_roll{window}_mean"] = df["pm25"].shift(1).rolling(window).mean()
for window in [7, 14]:
    df[f"pm25_roll{window}_std"]  = df["pm25"].shift(1).rolling(window).std()

# ── Group 3: Temporal features ────────────────────────────
df["month"]          = df.index.month
df["week"]           = df.index.isocalendar().week.astype(int)
df["day_of_year"]    = df.index.day_of_year
df["sin_month"]      = np.sin(2 * np.pi * df.index.month / 12)
df["cos_month"]      = np.cos(2 * np.pi * df.index.month / 12)
df["sin_doy"]        = np.sin(2 * np.pi * df.index.day_of_year / 365)
df["cos_doy"]        = np.cos(2 * np.pi * df.index.day_of_year / 365)
df["is_haze_season"] = df.index.month.isin([1, 2, 3, 4]).astype(int)

# ── Group 4: Weather features ─────────────────────────────
# Support both legacy Open-Meteo raw names and current consolidated names.
WEATHER_SOURCE_MAP = [
    ("temp_max", "temp_max"),
    ("temp_min", "temp_min"),
    ("temp_mean", "temp_mean"),
    ("humidity_max", "humidity_max"),
    ("humidity_min", "humidity_min"),
    ("precipitation", "precipitation"),
    ("wind_speed_max", "wind_speed"),
    ("wind_direction", "wind_dir_raw"),
    ("pressure_mean", "pressure"),
    ("cloud_cover", "cloud_cover"),
    ("evapotranspiration", "evapotranspiration"),
    ("temperature_2m_max", "temp_max"),
    ("temperature_2m_min", "temp_min"),
    ("temperature_2m_mean", "temp_mean"),
    ("relative_humidity_2m_max", "humidity_max"),
    ("relative_humidity_2m_min", "humidity_min"),
    ("precipitation_sum", "precipitation"),
    ("wind_speed_10m_max", "wind_speed"),
    ("wind_direction_10m_dominant", "wind_dir_raw"),
    ("surface_pressure_mean", "pressure"),
    ("cloud_cover_mean", "cloud_cover"),
    ("et0_fao_evapotranspiration", "evapotranspiration"),
]
WEATHER_BASE_COLS = [
    "temp_max", "temp_min", "temp_mean",
    "humidity_max", "humidity_min", "precipitation",
    "wind_speed", "pressure", "cloud_cover", "evapotranspiration",
]

if has_weather:
    for source_col, target_col in WEATHER_SOURCE_MAP:
        if target_col in df.columns:
            continue
        if source_col in df_weather.columns:
            df[target_col] = df_weather[source_col].reindex(df.index)

    # Wind direction: encode as sin/cos
    if "wind_dir_raw" in df.columns:
        df["wind_dir_sin"] = np.sin(np.radians(df["wind_dir_raw"]))
        df["wind_dir_cos"] = np.cos(np.radians(df["wind_dir_raw"]))
        df.drop(columns=["wind_dir_raw"], inplace=True)
    else:
        df["wind_dir_sin"] = np.nan
        df["wind_dir_cos"] = np.nan

    # Keep schema stable even when some weather columns are missing.
    for col in [*WEATHER_BASE_COLS, "wind_dir_sin", "wind_dir_cos"]:
        if col not in df.columns:
            df[col] = np.nan

    missing_or_empty = [c for c in [*WEATHER_BASE_COLS, "wind_dir_sin", "wind_dir_cos"] if df[c].isna().all()]
    if missing_or_empty:
        print(f"   ⚠️  Weather columns missing/empty: {missing_or_empty}")
else:
    # Placeholder columns so model schema is stable
    for col in [*WEATHER_BASE_COLS, "wind_dir_sin", "wind_dir_cos"]:
        df[col] = np.nan

# ── Group 5: Fire hotspot features ────────────────────────
if has_firms:
    df["hotspot_50km"]      = df_firms["hotspot_50km"].reindex(df.index).fillna(0)
    df["hotspot_100km"]     = df_firms["hotspot_100km"].reindex(df.index).fillna(0)
    df["mean_frp_50km"]     = df_firms["mean_frp_50km"].reindex(df.index)
    df["hotspot_7d_roll"]   = df["hotspot_50km"].shift(1).rolling(7).mean()
    df["hotspot_14d_roll"]  = df["hotspot_50km"].shift(1).rolling(14).mean()
    df["fire_flag"]         = (df["hotspot_50km"] > 0).astype(int)
else:
    for col in ["hotspot_50km","hotspot_100km","mean_frp_50km",
                "hotspot_7d_roll","hotspot_14d_roll","fire_flag"]:
        df[col] = 0 if col != "mean_frp_50km" else np.nan

# ── Group 6: Alert lag flags ──────────────────────────────
df["alert_lag1"] = (df["pm25_lag1"] > 50).astype(int)
df["alert_lag3"] = (df["pm25_lag3"] > 50).astype(int)
df["alert_lag7"] = (df["pm25_lag7"] > 50).astype(int)

# ── Group 7: Cross features ───────────────────────────────
df["lag1_x_temp"]    = df["pm25_lag1"] * df.get("temp_max", np.nan)
df["lag1_x_wind"]    = df["pm25_lag1"] * df.get("wind_speed", np.nan)
df["roll7_x_fire"]   = df["pm25_roll7_mean"] * df["fire_flag"]
df["precip_flag"]    = (df.get("precipitation", pd.Series(np.nan, index=df.index)) > 1).astype(int)
df["humidity_wind"]  = df.get("humidity_max", np.nan) * df.get("wind_speed", np.nan)

# ── Targets ───────────────────────────────────────────────
df["pm25_t1"] = df["pm25"].shift(-1)
df["pm25_t3"] = df["pm25"].shift(-3)
df["pm25_t7"] = df["pm25"].shift(-7)

# Alert targets (binary)
df["alert_t1"] = (df["pm25_t1"] > 50).astype("Int64")
df["alert_t3"] = (df["pm25_t3"] > 50).astype("Int64")
df["alert_t7"] = (df["pm25_t7"] > 50).astype("Int64")

# ── Drop rows that have no PM2.5 at all (unusable) ────────
df = df.drop(columns=["pm25"])   # raw pm25 not a feature — only lags
df = df.dropna(subset=["pm25_lag1"])   # need at least lag1

# ── Summary ───────────────────────────────────────────────
feature_cols = [c for c in df.columns if not c.startswith(("pm25_t","alert_t"))]
target_cols  = [c for c in df.columns if c.startswith(("pm25_t","alert_t"))]

print(f"\n   Total rows    : {len(df):,}")
print(f"   Feature cols  : {len(feature_cols)}")
print(f"   Target cols   : {len(target_cols)}")
print(f"   Date range    : {df.index.min().date()} → {df.index.max().date()}")
print(f"\n   Feature groups:")
print(f"     Lag (5)          : pm25_lag1/3/7/14/30")
print(f"     Rolling (6)      : roll3/7/14/30_mean, roll7/14_std")
print(f"     Temporal (8)     : month, week, doy, sin/cos_month, sin/cos_doy, is_haze_season")
print(f"     Weather (12)     : temp×3, humidity×2, precip, wind_speed, wind_dir_sin/cos, pressure, cloud, evap")
print(f"     Fire (6)         : hotspot_50/100km, frp_50km, hotspot_7/14d_roll, fire_flag")
print(f"     Alert flags (3)  : alert_lag1/3/7")
print(f"     Cross (5)        : lag1×temp, lag1×wind, roll7×fire, precip_flag, humidity_wind")
print(f"     Total: {len(feature_cols)}")

# ── Missing values summary ────────────────────────────────
missing = df[feature_cols].isna().mean() * 100
if missing.max() > 0:
    print(f"\n   Features with >5% missing:")
    print(missing[missing > 5].round(1).to_string())
else:
    print(f"\n   ✅ No features with >5% missing")

# ── Save ──────────────────────────────────────────────────
df.to_csv(OUTPUT_PATH)
print(f"\n✅  Saved: {OUTPUT_PATH}")
print(f"   Columns: {list(df.columns)}")
