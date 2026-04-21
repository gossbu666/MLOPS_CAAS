"""
CAAS — Streamlit Dashboard (v2, two-tab)
Public forecast + MLOps/model insights for Chiang Mai PM2.5.

Usage (local):   streamlit run dashboard.py
Usage (docker):  started by docker-compose; reads FASTAPI_URL + S3 env.
"""

import io
import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import requests
import streamlit as st

BKK = ZoneInfo("Asia/Bangkok")

# ── Config ─────────────────────────────────────────────────
FASTAPI_URL      = os.getenv("FASTAPI_URL", "http://localhost:8000")
S3_BUCKET        = os.getenv("S3_BUCKET_NAME", "caas-mlops-st126055")
AWS_REGION       = os.getenv("AWS_REGION", "ap-southeast-1")
MLFLOW_PUBLIC_URL = os.getenv("MLFLOW_PUBLIC_URL", "")

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


def freshness_badge(age_days) -> tuple[str, str, str]:
    """Return (label, color, caption) for data-freshness indicator."""
    if age_days is None:
        return "Unknown", "#666666", "No freshness signal"
    try:
        age = int(age_days)
    except (TypeError, ValueError):
        return "Unknown", "#666666", "No freshness signal"
    if age <= 0:
        return "Fresh", "#0a7c2a", "Updated today"
    if age == 1:
        return "Day-old", "#b36b00", "1 day behind"
    return "Stale", "#b30000", f"{age} days behind"


def format_local_timestamp(ts: str | None) -> str:
    """Normalize the FastAPI `generated_at_local` field for display."""
    if not ts:
        return "—"
    # FastAPI returns "YYYY-MM-DD HH:MM:SS Asia/Bangkok"; trim to "HH:MM · DD MMM"
    try:
        # Drop trailing tz name if present
        parts = ts.split(" ")
        if len(parts) >= 2:
            dt = datetime.strptime(" ".join(parts[:2]), "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%H:%M · %d %b %Y")
    except Exception:
        pass
    return ts


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

    # Data freshness — proves the daily pipeline is live
    as_of     = forecast_data.get("as_of_date", "—") if forecast_data else "—"
    age_days  = forecast_data.get("data_age_days") if forecast_data else None
    label, color, caption = freshness_badge(age_days)
    st.markdown("**Last data date**")
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:8px; line-height:1.4;">
          <span style="font-weight:600; color:#111;">{as_of}</span>
          <span style="
              font-size:11px; font-weight:600; padding:2px 8px; border-radius:999px;
              background:{color}1a; color:{color}; border:1px solid {color}40;
              letter-spacing:0.02em; text-transform:uppercase;
          ">{label}</span>
        </div>
        <div style="font-size:12px; color:#666; margin-top:2px;">{caption}</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("**Champion model**")
    champion = model_info.get("champion_model", "LightGBM") if model_info else "LightGBM"
    st.write(f"{champion}")

    st.markdown("---")
    if st.button("Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if MLFLOW_PUBLIC_URL:
        st.link_button("Open MLflow ↗", MLFLOW_PUBLIC_URL, use_container_width=True)

    st.markdown("---")
    st.markdown("**About**")
    st.caption(
        "Capstone — AT82.9002 Data Engineering & MLOps · AIT 2026\n\n"
        "Supanut Kompayak (st126055) · Shuvam Shrestha (st125975)"
    )
    st.caption("Data: PCD Thailand · Open-Meteo · NASA FIRMS")


# ── Header ─────────────────────────────────────────────────
title_col, meta_col = st.columns([3, 1])
with title_col:
    st.title("Chiang Mai Air Quality Forecast")
    st.caption(
        "Daily PM2.5 forecasts at 1-, 3-, and 7-day horizons with hazard alerts. "
        "Models tracked in MLflow; data pipeline runs daily."
    )
with meta_col:
    generated_local = forecast_data.get("generated_at_local") if forecast_data else None
    stamp           = format_local_timestamp(generated_local)
    st.markdown(
        f"""
        <div style="text-align:right; padding-top:18px;">
          <div style="font-size:11px; color:#888; letter-spacing:0.06em; text-transform:uppercase;">Updated</div>
          <div style="font-size:14px; color:#111; font-weight:600;">{stamp}</div>
          <div style="font-size:11px; color:#888;">Asia/Bangkok</div>
        </div>
        """,
        unsafe_allow_html=True,
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

    # Grid: Today (observed) + 3 forecast cards
    st.markdown("#### Today & forecast")
    history_data = fetch_history(days=60)

    latest_obs_val  = None
    latest_obs_date = None
    if history_data and history_data.get("data"):
        last = history_data["data"][-1]
        latest_obs_val  = last.get("pm25")
        latest_obs_date = last.get("date")

    def _card_html(label: str, sublabel: str, pm25: float, level: str, color: str, emphasis: bool = False) -> str:
        bg       = "#ffffff" if emphasis else "#fafafa"
        shadow   = (
            "box-shadow: 0 1px 2px rgba(16,24,40,0.04), 0 2px 6px rgba(16,24,40,0.06);"
            if emphasis
            else "box-shadow: 0 1px 2px rgba(16,24,40,0.04);"
        )
        return f"""
            <div style="
                border-left: 4px solid {color};
                padding: 14px 16px;
                background: {bg};
                border-radius: 6px;
                {shadow}
                height: 100%;
            ">
              <div style="display:flex; justify-content:space-between; align-items:baseline;">
                <div style="font-size: 12px; color: #666; font-weight: 600; text-transform: uppercase; letter-spacing:0.04em;">{label}</div>
                <div style="font-size: 11px; color: #888;">{sublabel}</div>
              </div>
              <div style="font-size: 34px; font-weight: 700; color: #111; line-height: 1.15; margin-top: 4px;">
                {pm25:.1f}<span style="font-size:14px; color:#666; font-weight:400;"> µg/m³</span>
              </div>
              <div style="font-size: 13px; color: {color}; font-weight: 600; margin-top: 2px;">
                {level}
              </div>
            </div>
        """

    cols = st.columns(4)
    # Today (observed)
    with cols[0]:
        if latest_obs_val is not None:
            lv = level_from_pm25(latest_obs_val)
            st.markdown(
                _card_html("Today", f"Observed · {latest_obs_date}", latest_obs_val, lv, pm25_color(latest_obs_val), emphasis=True),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div style="
                    border-left:4px solid #ccc; padding:14px 16px; background:#fafafa;
                    border-radius:6px; height:100%;
                ">
                  <div style="font-size:12px; color:#666; font-weight:600; text-transform:uppercase;">Today</div>
                  <div style="font-size:14px; color:#888; margin-top:8px;">Observed reading unavailable</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # 3 forecast horizons
    for col, (hkey, label, sub) in zip(
        cols[1:],
        [("t1", "Tomorrow", "+1 day"), ("t3", "In 3 days", "+3 days"), ("t7", "In 7 days", "+7 days")],
    ):
        if hkey not in forecasts:
            continue
        f     = forecasts[hkey]
        pm25  = f["pm25_forecast"]
        level = f["alert_level"]
        color = pm25_color(pm25)
        with col:
            st.markdown(_card_html(label, sub, pm25, level, color), unsafe_allow_html=True)

    # Combined chart — 60-day history with forecast overlay
    st.markdown("#### 60-day trend with forecast overlay")

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
        st.caption(
            "Data sources: PCD Chiang Mai station 35T (primary) with 36T fallback. "
            "Jan–Apr 2026 values backfilled from Open-Meteo CAMS reanalysis, "
            "bias-corrected against PCD 35T (n=92, MAE=5.39, r=0.531)."
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
        st.dataframe(legend, hide_index=True, use_container_width=True)


# =========================================================
#  TAB 2 — MODEL INSIGHTS
# =========================================================
with tab_model:
    # ── Section: Performance ──────────────────────────────
    st.markdown("### Performance")
    st.caption(
        "LightGBM is the production champion (selected via Optuna tuning + validation gate). "
        "XGBoost is kept as a fallback for A/B comparison."
    )

    # Side-by-side prediction comparison
    st.markdown("##### Prediction comparison — LightGBM vs XGBoost")
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
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else:
        st.info("Prediction comparison unavailable — one or both models not loaded.")

    # Champion metrics (always LightGBM); XGBoost metrics tucked in expander
    def _metrics_rows(metrics_dict: dict) -> list:
        out = []
        for h, m in metrics_dict.items():
            test  = m.get("test", {})
            alert = m.get("alert_test", {})
            out.append(
                {
                    "Horizon":      h.upper(),
                    "MAE":          f"{test.get('mae', float('nan')):.2f}",
                    "RMSE":         f"{test.get('rmse', float('nan')):.2f}",
                    "R²":           f"{test.get('r2', float('nan')):.3f}",
                    "Alert F1":     f"{alert.get('f1', float('nan')):.3f}",
                    "Alert AUROC":  f"{alert.get('auroc', float('nan')):.3f}",
                }
            )
        return out

    st.markdown("##### Test metrics — LightGBM (champion)")
    if model_info:
        champ_metrics = model_info.get("champion_metrics", {})
        if champ_metrics:
            st.dataframe(pd.DataFrame(_metrics_rows(champ_metrics)), hide_index=True, use_container_width=True)
        else:
            st.info("Champion metrics not available from `/model/info`.")

        fb_metrics = model_info.get("fallback_metrics", {})
        if fb_metrics:
            with st.expander("Show XGBoost (fallback) test metrics"):
                st.dataframe(pd.DataFrame(_metrics_rows(fb_metrics)), hide_index=True, use_container_width=True)
    else:
        st.info("Model metadata unavailable.")

    st.markdown("---")
    # ── Section: Drift ────────────────────────────────────
    st.markdown("### Data drift")
    st.caption(
        "Snapshot from the most recent Evidently run. "
        f"Source: `s3://{S3_BUCKET}/results/drift_summary.json` (written by the daily GitHub Actions pipeline, read via EC2 IAM role)."
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
                hide_index=True, use_container_width=True,
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

    st.markdown("---")
    # ── Section: Explainability ──────────────────────────
    st.markdown("### Explainability")

    # Fire-feature contribution across horizons
    st.markdown("##### Fire signal contribution across horizons")
    st.caption(
        "Summed XGBoost gain of all NASA FIRMS-derived features "
        "(hotspot_50km, hotspot_100km, hotspot_7d_roll, hotspot_14d_roll, fire_flag, roll7_x_fire) "
        "at each forecast horizon. Rising contribution at longer horizons reflects "
        "biomass-burning as a persistent driver when lag-based signals weaken."
    )
    fire_keywords = ("hotspot", "fire", "firms")
    fire_rows = []
    for h in ["t1", "t3", "t7"]:
        df_h = fetch_s3_csv(f"results/xgboost_{h}_importance.csv")
        if df_h is None or df_h.empty:
            continue
        feat_col = "feature" if "feature" in df_h.columns else df_h.columns[0]
        imp_col = (
            "importance" if "importance" in df_h.columns
            else "gain" if "gain" in df_h.columns
            else df_h.columns[1]
        )
        fire_mask = df_h[feat_col].str.lower().str.contains("|".join(fire_keywords), regex=True)
        fire_sum  = float(df_h.loc[fire_mask, imp_col].sum())
        total     = float(df_h[imp_col].sum())
        fire_rows.append(
            {
                "horizon":      h,
                "share":        fire_sum / total if total > 0 else 0.0,
                "fire_sum":     fire_sum,
                "non_fire":     total - fire_sum,
            }
        )

    if fire_rows:
        df_fire = pd.DataFrame(fire_rows)
        fire_chart = (
            alt.Chart(df_fire)
            .mark_bar(color="#c1423b")
            .encode(
                x=alt.X("horizon:N", title="Forecast horizon", sort=["t1", "t3", "t7"]),
                y=alt.Y("share:Q", title="FIRMS share of total gain", axis=alt.Axis(format="%")),
                tooltip=[
                    alt.Tooltip("horizon:N", title="Horizon"),
                    alt.Tooltip("share:Q", title="FIRMS share", format=".1%"),
                    alt.Tooltip("fire_sum:Q", title="Fire gain sum", format=".3f"),
                    alt.Tooltip("non_fire:Q", title="Non-fire gain sum", format=".3f"),
                ],
            )
            .properties(height=240)
        )
        text = fire_chart.mark_text(
            align="center", baseline="bottom", dy=-4, fontWeight="bold"
        ).encode(text=alt.Text("share:Q", format=".1%"))
        st.altair_chart(fire_chart + text, use_container_width=True)

        # Horizon labels with friendlier names
        labels = {"t1": "+1 day", "t3": "+3 days", "t7": "+7 days"}
        df_summary = df_fire.assign(
            Horizon=df_fire["horizon"].map(labels),
            **{"FIRMS share": df_fire["share"].map(lambda v: f"{v:.1%}")},
            **{"Fire gain sum": df_fire["fire_sum"].map(lambda v: f"{v:.3f}")},
            **{"Non-fire gain sum": df_fire["non_fire"].map(lambda v: f"{v:.3f}")},
        )[["Horizon", "FIRMS share", "Fire gain sum", "Non-fire gain sum"]]
        st.dataframe(df_summary, hide_index=True, use_container_width=True)
    else:
        st.info("Importance CSVs not yet available in S3 — run the training pipeline to populate them.")

    # Feature importance — pulled from S3
    st.markdown("##### Top features (XGBoost importance)")
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
    "CAAS · FastAPI · Streamlit · MLflow · deployed on AWS EC2 via Terraform · "
    "data pipeline in GitHub Actions"
)
st.caption(
    f"API: `{FASTAPI_URL}`  ·  Bucket: `s3://{S3_BUCKET}`  ·  "
    "Capstone AT82.9002 · AIT 2026"
)
