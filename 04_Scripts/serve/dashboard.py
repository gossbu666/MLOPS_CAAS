"""
CAAS — Streamlit Dashboard
Public-facing PM2.5 forecast and alert dashboard for Chiang Mai.

Usage (local):
    streamlit run dashboard.py

Usage (production):
    streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0

Requires FastAPI server running at FASTAPI_URL (default: http://localhost:8000)
"""

import os
import requests
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime

# ── Config ─────────────────────────────────────────────────
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8000")

LEVEL_COLORS = {
    "Good":                              "#00e400",
    "Moderate":                          "#ffff00",
    "Unhealthy for Sensitive Groups":    "#ff7e00",
    "Unhealthy":                         "#ff0000",
    "Very Unhealthy":                    "#8f3f97",
    "Hazardous":                         "#7e0023",
}
LEVEL_EMOJI = {
    "Good":                              "🟢",
    "Moderate":                          "🟡",
    "Unhealthy for Sensitive Groups":    "🟠",
    "Unhealthy":                         "🔴",
    "Very Unhealthy":                    "🟣",
    "Hazardous":                         "🚨",
}
WHO_THRESHOLD   = 15.0
THAI_THRESHOLD  = 25.0
ALERT_THRESHOLD = 50.0

# ── Page config ────────────────────────────────────────────
st.set_page_config(
    page_title="CAAS — Chiang Mai Air Quality Alert System",
    page_icon="🌫️",
    layout="wide",
)

# ── Helper functions ───────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_forecast():
    try:
        resp = requests.get(f"{FASTAPI_URL}/forecast", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return None

@st.cache_data(ttl=3600)
def fetch_history(days=60):
    try:
        resp = requests.get(f"{FASTAPI_URL}/history?days={days}", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return None

@st.cache_data(ttl=3600)
def fetch_model_info():
    try:
        resp = requests.get(f"{FASTAPI_URL}/model/info", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None

def pm25_color(val):
    if val <= 15:   return LEVEL_COLORS["Good"]
    if val <= 25:   return LEVEL_COLORS["Moderate"]
    if val <= 37.5: return LEVEL_COLORS["Unhealthy for Sensitive Groups"]
    if val <= 50:   return LEVEL_COLORS["Unhealthy"]
    if val <= 75:   return LEVEL_COLORS["Very Unhealthy"]
    return LEVEL_COLORS["Hazardous"]

# ── Header ─────────────────────────────────────────────────
st.markdown("""
<h1 style='text-align:center; color:#1a1a2e;'>
🌫️ ChiangMai Air Quality Alert System
</h1>
<p style='text-align:center; color:#555; font-size:16px;'>
Real-time PM2.5 forecasting & early warning — Chiang Mai, Thailand
</p>
<hr/>
""", unsafe_allow_html=True)

# ── Fetch data ─────────────────────────────────────────────
forecast_data = fetch_forecast()
history_data  = fetch_history(days=60)
model_info    = fetch_model_info()

# ── API status warning ─────────────────────────────────────
if forecast_data is None:
    st.warning("⚠️ Cannot connect to CAAS API. Make sure FastAPI server is running: `uvicorn app:app --reload`")
    st.info("Showing sample data for demonstration purposes.")
    # Demo fallback
    forecast_data = {
        "station": "Chiang Mai (35T)",
        "as_of_date": datetime.now().strftime("%Y-%m-%d"),
        "forecasts": {
            "t1": {"horizon_days": 1, "pm25_forecast": 42.3, "alert": False, "alert_level": "Unhealthy"},
            "t3": {"horizon_days": 3, "pm25_forecast": 55.1, "alert": True,  "alert_level": "Very Unhealthy"},
            "t7": {"horizon_days": 7, "pm25_forecast": 38.7, "alert": False, "alert_level": "Unhealthy"},
        }
    }

# ── Section 1: Forecast cards ──────────────────────────────
st.subheader("📅 PM2.5 Forecast")
as_of = forecast_data.get("as_of_date", "N/A")
st.caption(f"Based on data as of: **{as_of}** | Station: {forecast_data.get('station', 'Chiang Mai')}")

forecasts = forecast_data.get("forecasts", {})
col1, col2, col3 = st.columns(3)

for col, (hkey, label) in zip([col1, col2, col3],
                               [("t1","Tomorrow"), ("t3","In 3 Days"), ("t7","In 7 Days")]):
    if hkey not in forecasts:
        continue
    f = forecasts[hkey]
    pm25 = f["pm25_forecast"]
    level = f["alert_level"]
    emoji = LEVEL_EMOJI.get(level, "⚪")
    color = pm25_color(pm25)
    alert_badge = "⚠️ ALERT" if f["alert"] else ""

    with col:
        st.markdown(f"""
        <div style='
            background:{color}22;
            border:2px solid {color};
            border-radius:12px;
            padding:20px;
            text-align:center;
        '>
            <div style='font-size:14px; color:#555; font-weight:600;'>{label}</div>
            <div style='font-size:42px; font-weight:700; color:{color};'>{pm25}</div>
            <div style='font-size:13px; color:#333;'>µg/m³</div>
            <div style='font-size:16px; margin-top:8px;'>{emoji} {level}</div>
            <div style='font-size:14px; color:#c0392b; font-weight:700;'>{alert_badge}</div>
        </div>
        """, unsafe_allow_html=True)

# ── Section 2: AQI Legend ──────────────────────────────────
with st.expander("📋 PM2.5 Level Reference (Thailand Standard)", expanded=False):
    legend_data = {
        "Level":     ["Good", "Moderate", "Unhealthy (Sensitive)", "Unhealthy", "Very Unhealthy", "Hazardous"],
        "PM2.5 (µg/m³)": ["0–15", "15–25", "25–37.5", "37.5–50", "50–75", ">75"],
        "Color":     ["🟢", "🟡", "🟠", "🔴", "🟣", "🚨"],
    }
    st.table(pd.DataFrame(legend_data))

# ── Section 3: PM2.5 History Chart ────────────────────────
st.subheader("📈 PM2.5 History (Last 60 Days)")

if history_data and history_data.get("data"):
    df_hist = pd.DataFrame(history_data["data"])
    df_hist["date"] = pd.to_datetime(df_hist["date"])
    df_hist = df_hist.sort_values("date")

    # Build chart data
    import altair as alt

    line = alt.Chart(df_hist).mark_line(color="#2980b9", strokeWidth=2).encode(
        x=alt.X("date:T", title="Date"),
        y=alt.Y("pm25:Q", title="PM2.5 (µg/m³)", scale=alt.Scale(zero=False)),
        tooltip=["date:T", "pm25:Q", "level:N"],
    )

    alert_rule = alt.Chart(pd.DataFrame({"y": [ALERT_THRESHOLD]})).mark_rule(
        color="red", strokeDash=[4,4], strokeWidth=1.5
    ).encode(y="y:Q")

    thai_rule = alt.Chart(pd.DataFrame({"y": [THAI_THRESHOLD]})).mark_rule(
        color="orange", strokeDash=[4,4], strokeWidth=1.5
    ).encode(y="y:Q")

    chart = (line + alert_rule + thai_rule).properties(height=280).interactive()
    st.altair_chart(chart, use_container_width=True)
    st.caption("🔴 Red dashed = 50 µg/m³ hazard threshold | 🟠 Orange dashed = 25 µg/m³ Thai standard")
else:
    st.info("Historical data not available. Make sure the API and data files are in place.")

# ── Section 4: Stats summary ───────────────────────────────
if history_data and history_data.get("data"):
    df_hist = pd.DataFrame(history_data["data"])
    st.subheader("📊 Last 60 Days Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Average PM2.5",  f"{df_hist['pm25'].mean():.1f} µg/m³")
    c2.metric("Maximum PM2.5",  f"{df_hist['pm25'].max():.1f} µg/m³")
    c3.metric("Alert Days (>50)", int((df_hist["pm25"] > ALERT_THRESHOLD).sum()))
    c4.metric("WHO Exceedance (>15)", f"{(df_hist['pm25'] > WHO_THRESHOLD).mean()*100:.0f}%")

# ── Section 5: Model info ──────────────────────────────────
if model_info and "champion_metrics" in model_info:
    with st.expander("🤖 Model Information", expanded=False):
        st.markdown(f"**Champion model:** {model_info.get('champion_model','LightGBM')}")
        metrics = model_info["champion_metrics"]
        rows = []
        for h, m in metrics.items():
            test = m.get("test", {})
            alert = m.get("alert_test", {})
            rows.append({
                "Horizon": h.upper(),
                "MAE":  f"{test.get('mae','—'):.2f}" if isinstance(test.get('mae'), float) else "—",
                "RMSE": f"{test.get('rmse','—'):.2f}" if isinstance(test.get('rmse'), float) else "—",
                "R²":   f"{test.get('r2','—'):.3f}" if isinstance(test.get('r2'), float) else "—",
                "Alert F1": f"{alert.get('f1','—'):.3f}" if isinstance(alert.get('f1'), float) else "—",
            })
        if rows:
            st.table(pd.DataFrame(rows))

# ── Footer ─────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<p style='text-align:center; color:#999; font-size:12px;'>
CAAS — ChiangMai Air Quality Alert System | AT82.9002 MLOps Project<br>
Supanut Kompayak (st126055) · Shuvam Shrestha (st125975) | AIT, 2026<br>
Data sources: PCD Thailand · Open-Meteo · NASA FIRMS
</p>
""", unsafe_allow_html=True)
