"""
CAAS — Streamlit Dashboard (v2, two-tab)
Public forecast + MLOps/model insights for Chiang Mai PM2.5.

Usage (local):   streamlit run dashboard.py
Usage (docker):  started by docker-compose; reads FASTAPI_URL + S3 env.
"""

import io
import json
import os
from datetime import datetime

import altair as alt
import pandas as pd
import requests
import streamlit as st

# ── Config ─────────────────────────────────────────────────
FASTAPI_URL    = os.getenv("FASTAPI_URL", "http://localhost:8000")
S3_BUCKET      = os.getenv("S3_BUCKET_NAME", "caas-mlops-st126055")
AWS_REGION     = os.getenv("AWS_REGION", "ap-southeast-1")

ALERT_THRESHOLD = 50.0   # µg/m³ — hazardous alert trigger
THAI_THRESHOLD  = 25.0   # µg/m³ — Thailand 24-hr standard
WHO_THRESHOLD   = 15.0   # µg/m³ — WHO 24-hr guideline

LEVEL_COLORS = {
    "Good":                              "#00e400",
    "Moderate":                          "#e6c000",
    "Unhealthy for Sensitive Groups":    "#ff7e00",
    "Unhealthy":                         "#e60000",
    "Very Unhealthy":                    "#8f3f97",
    "Hazardous":                         "#7e0023",
}
LEVEL_ICON = {
    "Good": "●", "Moderate": "●",
    "Unhealthy for Sensitive Groups": "●", "Unhealthy": "●",
    "Very Unhealthy": "●", "Hazardous": "●",
}

HEALTH_ADVICE = {
    "Good":                           "Air quality is safe for outdoor activities.",
    "Moderate":                       "Acceptable for most people. Sensitive groups should limit prolonged outdoor exertion.",
    "Unhealthy for Sensitive Groups": "Sensitive groups (children, elderly, respiratory conditions) should reduce prolonged outdoor activity.",
    "Unhealthy":                      "Everyone should reduce prolonged outdoor exertion. Consider wearing an N95 mask outdoors.",
    "Very Unhealthy":                 "Avoid outdoor activities. Wear an N95 mask if going outside. Keep windows closed.",
    "Hazardous":                      "Stay indoors. Use air purifiers if available. Postpone outdoor activities.",
}

# ── Page config ────────────────────────────────────────────
st.set_page_config(
    page_title="CAAS — Chiang Mai Air Quality Alert System",
    page_icon="🌫️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Data fetchers ──────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_forecast(model: str = "lightgbm"):
    try:
        r = requests.get(f"{FASTAPI_URL}/forecast", params={"model": model}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_history(days: int = 60):
    try:
        r = requests.get(f"{FASTAPI_URL}/history", params={"days": days}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_model_info():
    try:
        r = requests.get(f"{FASTAPI_URL}/model/info", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_s3_json(key: str):
    """Fetch a JSON object from S3 using the instance IAM role."""
    try:
        import boto3
        s3 = boto3.client("s3", region_name=AWS_REGION)
        obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
        return json.loads(obj["Body"].read())
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_s3_csv(key: str):
    try:
        import boto3
        s3 = boto3.client("s3", region_name=AWS_REGION)
        obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
        return pd.read_csv(io.BytesIO(obj["Body"].read()))
    except Exception:
        return None


# ── Helpers ────────────────────────────────────────────────
def pm25_color(val: float) -> str:
    if val <= 15:   return LEVEL_COLORS["Good"]
    if val <= 25:   return LEVEL_COLORS["Moderate"]
    if val <= 37.5: return LEVEL_COLORS["Unhealthy for Sensitive Groups"]
    if val <= 50:   return LEVEL_COLORS["Unhealthy"]
    if val <= 75:   return LEVEL_COLORS["Very Unhealthy"]
    return LEVEL_COLORS["Hazardous"]


def level_from_pm25(val: float) -> str:
    if val <= 15:   return "Good"
    if val <= 25:   return "Moderate"
    if val <= 37.5: return "Unhealthy for Sensitive Groups"
    if val <= 50:   return "Unhealthy"
    if val <= 75:   return "Very Unhealthy"
    return "Hazardous"


def worst_horizon(forecasts: dict) -> dict | None:
    if not forecasts:
        return None
    return max(forecasts.values(), key=lambda f: f.get("pm25_forecast", 0))


# ── Sidebar ────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### CAAS")
    st.caption("ChiangMai Air Quality Alert System")

    # Fetch early so sidebar can show metadata
    forecast_data = fetch_forecast("lightgbm")
    model_info    = fetch_model_info()

    st.markdown("---")
    st.markdown("**Station**")
    station_name = forecast_data.get("station", "—") if forecast_data else "—"
    st.write(station_name)

    st.markdown("**Last data date**")
    as_of = forecast_data.get("as_of_date", "—") if forecast_data else "—"
    st.write(as_of)

    st.markdown("**Champion model**")
    champion = model_info.get("champion_model", "LightGBM") if model_info else "LightGBM"
    st.write(f"{champion}")

    st.markdown("---")
    if st.button("Refresh data", width="stretch"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("**About**")
    st.caption(
        "Capstone — AT82.9002 Data Engineering & MLOps · AIT 2026\n\n"
        "Supanut Kompayak (st126055) · Shuvam Shrestha (st125975)"
    )
    st.caption("Data: PCD Thailand · Open-Meteo · NASA FIRMS")


# ── Header ─────────────────────────────────────────────────
st.title("Chiang Mai Air Quality Forecast")
st.caption(
    "Daily PM2.5 forecasts at 1-, 3-, and 7-day horizons with hazard alerts. "
    "Models tracked in MLflow; data pipeline runs daily."
)

# Degrade gracefully if API is down
if forecast_data is None:
    st.error(
        f"Cannot reach forecast API at `{FASTAPI_URL}`. "
        "Verify the FastAPI service is running."
    )
    st.stop()


# ── Tabs ───────────────────────────────────────────────────
tab_public, tab_model = st.tabs(["Public View", "Model Insights"])


# =========================================================
#  TAB 1 — PUBLIC VIEW
# =========================================================
with tab_public:
    forecasts = forecast_data.get("forecasts", {})

    # Alert banner — highest-risk horizon drives the message
    worst = worst_horizon(forecasts)
    if worst:
        worst_val   = worst["pm25_forecast"]
        worst_level = worst["alert_level"]
        worst_h     = worst["horizon_days"]

        if worst_val >= ALERT_THRESHOLD:
            st.error(
                f"**Hazard alert** — forecast peak **{worst_val:.1f} µg/m³** "
                f"in {worst_h} day(s) ({worst_level}). "
                "Limit outdoor exposure and consider wearing an N95 mask."
            )
        elif worst_val >= THAI_THRESHOLD:
            st.warning(
                f"**Elevated levels expected** — forecast peak **{worst_val:.1f} µg/m³** "
                f"in {worst_h} day(s) ({worst_level}). Sensitive groups should take precautions."
            )
        else:
            st.success(
                f"**Low risk** — forecast peak **{worst_val:.1f} µg/m³** "
                f"in {worst_h} day(s). Air quality is within healthy range."
            )

    # 3 forecast cards
    st.markdown("#### Forecast")
    cols = st.columns(3)
    for col, (hkey, label) in zip(
        cols, [("t1", "Tomorrow"), ("t3", "In 3 days"), ("t7", "In 7 days")]
    ):
        if hkey not in forecasts:
            continue
        f     = forecasts[hkey]
        pm25  = f["pm25_forecast"]
        level = f["alert_level"]
        color = pm25_color(pm25)

        with col:
            st.markdown(
                f"""
                <div style="
                    border-left: 4px solid {color};
                    padding: 12px 16px;
                    background: #fafafa;
                    border-radius: 4px;
                ">
                  <div style="font-size: 13px; color: #666; font-weight: 500;">{label}</div>
                  <div style="font-size: 34px; font-weight: 700; color: #111; line-height: 1.1;">
                    {pm25:.1f}<span style="font-size:14px; color:#666; font-weight:400;"> µg/m³</span>
                  </div>
                  <div style="font-size: 13px; color: {color}; font-weight: 600; margin-top: 2px;">
                    {level}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Combined chart — 60-day history with forecast overlay
    st.markdown("#### 60-day trend with forecast overlay")
    history_data = fetch_history(days=60)

    if history_data and history_data.get("data"):
        df_hist = pd.DataFrame(history_data["data"])
        df_hist["date"] = pd.to_datetime(df_hist["date"])
        df_hist = df_hist.sort_values("date")
        df_hist["series"] = "Observed"

        last_obs_date = df_hist["date"].max()
        forecast_rows = []
        for hkey, f in forecasts.items():
            h = f["horizon_days"]
            forecast_rows.append(
                {
                    "date": last_obs_date + pd.Timedelta(days=h),
                    "pm25": f["pm25_forecast"],
                    "series": "Forecast",
                }
            )
        df_fcst = pd.DataFrame(forecast_rows)

        history_line = (
            alt.Chart(df_hist)
            .mark_line(color="#1f77b4", strokeWidth=2)
            .encode(
                x=alt.X("date:T", title=None),
                y=alt.Y(
                    "pm25:Q",
                    title="PM2.5 (µg/m³)",
                    scale=alt.Scale(zero=True, nice=True),
                ),
                tooltip=[
                    alt.Tooltip("date:T", title="Date"),
                    alt.Tooltip("pm25:Q", title="PM2.5", format=".1f"),
                ],
            )
        )
        forecast_points = (
            alt.Chart(df_fcst)
            .mark_point(color="#d62728", size=120, filled=True, shape="diamond")
            .encode(
                x="date:T",
                y="pm25:Q",
                tooltip=[
                    alt.Tooltip("date:T", title="Forecast date"),
                    alt.Tooltip("pm25:Q", title="PM2.5", format=".1f"),
                ],
            )
        )
        # dashed link from last observed point to forecast points
        last_obs = df_hist.tail(1)[["date", "pm25"]].assign(series="link")
        link_df  = pd.concat([last_obs, df_fcst[["date", "pm25"]].assign(series="link")])
        forecast_link = (
            alt.Chart(link_df)
            .mark_line(color="#d62728", strokeDash=[4, 4], strokeWidth=1.5)
            .encode(x="date:T", y="pm25:Q")
        )
        alert_rule = (
            alt.Chart(pd.DataFrame({"y": [ALERT_THRESHOLD]}))
            .mark_rule(color="#e60000", strokeDash=[3, 3], strokeWidth=1)
            .encode(y="y:Q")
        )
        thai_rule = (
            alt.Chart(pd.DataFrame({"y": [THAI_THRESHOLD]}))
            .mark_rule(color="#ff7e00", strokeDash=[3, 3], strokeWidth=1)
            .encode(y="y:Q")
        )

        chart = (
            (history_line + forecast_link + forecast_points + alert_rule + thai_rule)
            .properties(height=320)
            .interactive()
        )
        st.altair_chart(chart, use_container_width=True)
        st.caption(
            "Solid blue = observed history · red diamonds = model forecast · "
            "red dashed = 50 µg/m³ hazard line · orange dashed = 25 µg/m³ Thai standard"
        )
    else:
        st.info("Historical data not yet available from the API.")

    # Health advice based on worst horizon
    if worst:
        with st.container():
            st.markdown("#### Health guidance")
            worst_level = worst["alert_level"]
            advice = HEALTH_ADVICE.get(worst_level, "")
            st.write(
                f"For the highest-risk horizon (**{worst_level}** at day +{worst['horizon_days']}): {advice}"
            )

    # AQI reference
    with st.expander("PM2.5 level reference (Thailand standard)"):
        legend = pd.DataFrame(
            {
                "Level": [
                    "Good", "Moderate", "Unhealthy for Sensitive Groups",
                    "Unhealthy", "Very Unhealthy", "Hazardous",
                ],
                "PM2.5 (µg/m³)": ["0 – 15", "15 – 25", "25 – 37.5", "37.5 – 50", "50 – 75", "> 75"],
            }
        )
        st.dataframe(legend, hide_index=True, width="stretch")


# =========================================================
#  TAB 2 — MODEL INSIGHTS
# =========================================================
with tab_model:
    st.markdown("#### Model selection")
    model_choice = st.radio(
        "Active model",
        options=["LightGBM (champion)", "XGBoost (fallback)"],
        index=0,
        horizontal=True,
        label_visibility="collapsed",
    )
    model_key = "lightgbm" if model_choice.startswith("LightGBM") else "xgboost"

    # Side-by-side prediction comparison
    st.markdown("#### Prediction comparison (both models)")
    fc_lgb = fetch_forecast("lightgbm")
    fc_xgb = fetch_forecast("xgboost")

    if fc_lgb and fc_xgb:
        rows = []
        for hkey, label in [("t1", "+1 day"), ("t3", "+3 days"), ("t7", "+7 days")]:
            lgb_val = fc_lgb["forecasts"].get(hkey, {}).get("pm25_forecast")
            xgb_val = fc_xgb["forecasts"].get(hkey, {}).get("pm25_forecast")
            if lgb_val is None or xgb_val is None:
                continue
            rows.append(
                {
                    "Horizon":   label,
                    "LightGBM":  f"{lgb_val:.2f}",
                    "XGBoost":   f"{xgb_val:.2f}",
                    "Δ (LGB − XGB)": f"{lgb_val - xgb_val:+.2f}",
                    "Level (champion)": level_from_pm25(lgb_val),
                }
            )
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    # Metrics table for selected model
    st.markdown(f"#### Test metrics — {model_choice}")
    if model_info:
        metrics_key = "champion_metrics" if model_key == "lightgbm" else "fallback_metrics"
        metrics = model_info.get(metrics_key, {})
        if metrics:
            rows = []
            for h, m in metrics.items():
                test  = m.get("test", {})
                alert = m.get("alert_test", {})
                rows.append(
                    {
                        "Horizon":  h.upper(),
                        "MAE":      f"{test.get('mae', float('nan')):.2f}",
                        "RMSE":     f"{test.get('rmse', float('nan')):.2f}",
                        "R²":       f"{test.get('r2', float('nan')):.3f}",
                        "Alert F1": f"{alert.get('f1', float('nan')):.3f}",
                        "Alert AUROC": f"{alert.get('auroc', float('nan')):.3f}",
                    }
                )
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        else:
            st.info("Metrics not available from `/model/info`.")
    else:
        st.info("Model metadata unavailable.")

    # Drift status — fetched from S3
    st.markdown("#### Data drift status")
    st.caption(
        f"Reads `s3://{S3_BUCKET}/results/drift_summary.json` via EC2 IAM role. "
        "Updated by the daily pipeline on GitHub Actions."
    )
    drift = fetch_s3_json("results/drift_summary.json")
    if drift:
        generated_at = drift.get("timestamp", drift.get("generated_at", "—"))

        # Top-line status chips
        core_n = drift.get("core_drift_count", 0)
        soft_n = drift.get("soft_drift_count", 0)
        retrain = drift.get("retrain_needed", False)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Report generated", str(generated_at).split("T")[0])
        c2.metric("Core drift features", core_n)
        c3.metric("Soft drift features", soft_n)
        c4.metric("Retrain triggered", "Yes" if retrain else "No")

        features = drift.get("features", [])
        if isinstance(features, list) and features:
            drift_rows = []
            for feat in features:
                name    = feat.get("feature", "—")
                psi     = feat.get("psi")
                ks_stat = feat.get("ks_stat")
                psi_flag = feat.get("psi_flag", False)
                ks_flag  = feat.get("ks_flag", False)
                triggers = feat.get("contributes_to_trigger", False)

                if triggers:
                    status = "Drift"
                elif psi_flag or ks_flag:
                    status = "Watch"
                else:
                    status = "OK"

                drift_rows.append(
                    {
                        "Feature":  name,
                        "PSI":      f"{psi:.3f}" if isinstance(psi, (int, float)) else "—",
                        "KS stat":  f"{ks_stat:.3f}" if isinstance(ks_stat, (int, float)) else "—",
                        "Status":   status,
                    }
                )

            df_drift = pd.DataFrame(drift_rows)

            def _style_status(v):
                return {
                    "OK":    "color: #0a7c2a; font-weight: 600;",
                    "Watch": "color: #b36b00; font-weight: 600;",
                    "Drift": "color: #b30000; font-weight: 600;",
                }.get(v, "")

            st.dataframe(
                df_drift.style.map(_style_status, subset=["Status"]),
                hide_index=True, width="stretch",
            )

            core_feats = drift.get("core_drift_features", [])
            soft_feats = drift.get("soft_drift_features", [])
            if core_feats or soft_feats:
                st.caption(
                    f"Core-drift flags (trigger retrain ≥ 2): {', '.join(core_feats) or 'none'} · "
                    f"Soft-drift flags (monitor): {', '.join(soft_feats) or 'none'}"
                )
        else:
            st.json(drift)
    else:
        st.info("Drift report not yet available in S3. Run the daily pipeline to populate it.")

    # Feature importance — pulled from S3
    st.markdown("#### Top features (XGBoost importance)")
    horizon_pick = st.selectbox(
        "Horizon", options=["t1", "t3", "t7"], index=0, label_visibility="collapsed"
    )
    df_imp = fetch_s3_csv(f"results/xgboost_{horizon_pick}_importance.csv")
    if df_imp is not None and not df_imp.empty:
        cols = {c.lower(): c for c in df_imp.columns}
        feat_col = cols.get("feature") or df_imp.columns[0]
        val_col  = cols.get("importance") or cols.get("gain") or df_imp.columns[1]
        top = df_imp[[feat_col, val_col]].rename(columns={feat_col: "feature", val_col: "importance"})
        top = top.sort_values("importance", ascending=False).head(10)

        imp_chart = (
            alt.Chart(top)
            .mark_bar(color="#4a6fa5")
            .encode(
                x=alt.X("importance:Q", title="Importance (gain)"),
                y=alt.Y("feature:N", sort="-x", title=None),
                tooltip=["feature:N", alt.Tooltip("importance:Q", format=".3f")],
            )
            .properties(height=260)
        )
        st.altair_chart(imp_chart, use_container_width=True)
    else:
        st.info(f"`xgboost_{horizon_pick}_importance.csv` not found in S3.")


# ── Footer ─────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "CAAS v2 · FastAPI · Streamlit · MLflow · deployed on AWS EC2 via Terraform · "
    f"API: `{FASTAPI_URL}` · Bucket: `s3://{S3_BUCKET}`"
)
