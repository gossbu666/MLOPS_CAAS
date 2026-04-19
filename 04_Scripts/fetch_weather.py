"""
CAAS — Open-Meteo Historical Weather Data Fetcher
Fetches daily weather data for Chiang Mai (2011–2025)
No API key required!

Station: Chiang Mai City Hall area
Coordinates: 18.7883° N, 98.9853° E

Usage:
    python fetch_weather.py
"""

import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry
from pathlib import Path

# ── Config ────────────────────────────────────────────────
LAT = 18.7883
LON = 98.9853
START_DATE = "2011-01-01"
END_DATE   = "2025-12-31"

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = BASE_DIR / "03_Data" / "processed" / "weather_consolidated.csv"

# Weather variables to fetch
DAILY_VARS = [
    "temperature_2m_max",       # Max temp (°C)
    "temperature_2m_min",       # Min temp (°C)
    "temperature_2m_mean",      # Mean temp (°C)
    "relative_humidity_2m_max", # Max humidity (%)
    "relative_humidity_2m_min", # Min humidity (%)
    "precipitation_sum",        # Total rain (mm)
    "wind_speed_10m_max",       # Max wind speed (km/h)
    "wind_direction_10m_dominant", # Dominant wind direction (°)
    "surface_pressure_mean",    # Mean pressure (hPa) -- helps trap particulates
    "cloud_cover_mean",         # Mean cloud cover (%)
    "et0_fao_evapotranspiration",  # Evapotranspiration (mm) -- proxy for dry conditions
]

# ── Setup API client with cache + retry ──────────────────
cache_session = requests_cache.CachedSession('.cache', expire_after=-1)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

print("🌤️  Fetching weather data from Open-Meteo...")
print(f"   Location: Chiang Mai ({LAT}°N, {LON}°E)")
print(f"   Period  : {START_DATE} → {END_DATE}")
print(f"   Variables: {len(DAILY_VARS)} daily variables")
print()

# ── API Request ──────────────────────────────────────────
url = "https://archive-api.open-meteo.com/v1/archive"
params = {
    "latitude": LAT,
    "longitude": LON,
    "start_date": START_DATE,
    "end_date": END_DATE,
    "daily": DAILY_VARS,
    "timezone": "Asia/Bangkok",
}

responses = openmeteo.weather_api(url, params=params)
response = responses[0]

print(f"✅ Data received!")
print(f"   Coordinates : {response.Latitude():.4f}°N, {response.Longitude():.4f}°E")
print(f"   Timezone    : {response.Timezone()} ({response.TimezoneAbbreviation()})")
print(f"   Elevation   : {response.Elevation()}m")
print()

# ── Parse Response ───────────────────────────────────────
daily = response.Daily()

data = {
    "date": pd.date_range(
        start=pd.to_datetime(daily.Time(), unit="s", utc=True),
        end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=daily.Interval()),
        inclusive="left"
    ).tz_convert("Asia/Bangkok").date,
}

# Map each variable
for i, var in enumerate(DAILY_VARS):
    data[var] = daily.Variables(i).ValuesAsNumpy()

df = pd.DataFrame(data)
df['date'] = pd.to_datetime(df['date'])

# ── Rename columns for clarity ───────────────────────────
df = df.rename(columns={
    "temperature_2m_max":              "temp_max",
    "temperature_2m_min":              "temp_min",
    "temperature_2m_mean":             "temp_mean",
    "relative_humidity_2m_max":        "humidity_max",
    "relative_humidity_2m_min":        "humidity_min",
    "precipitation_sum":               "precipitation",
    "wind_speed_10m_max":              "wind_speed_max",
    "wind_direction_10m_dominant":     "wind_direction",
    "surface_pressure_mean":           "pressure_mean",
    "cloud_cover_mean":                "cloud_cover",
    "et0_fao_evapotranspiration":      "evapotranspiration",
})

# ── Summary ──────────────────────────────────────────────
print(f"{'='*55}")
print(f"Total rows    : {len(df)}")
print(f"Date range    : {df['date'].min().date()} → {df['date'].max().date()}")
print(f"Missing values:")
for col in df.columns[1:]:
    miss = df[col].isna().sum()
    if miss > 0:
        print(f"  {col:<30}: {miss} ({miss/len(df)*100:.1f}%)")
    else:
        print(f"  {col:<30}: ✅ complete")

# ── Save ─────────────────────────────────────────────────
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUTPUT_PATH, index=False)
print(f"\n✅ Saved: {OUTPUT_PATH}")
print(f"\nSample:")
print(df.head(3).to_string(index=False))
