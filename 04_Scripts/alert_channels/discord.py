"""Discord webhook alert channel for CAAS forecast alerts.

The webhook URL is read from the DISCORD_WEBHOOK_URL env var. When unset,
send_discord_alert() logs and returns silently — the pipeline does not
fail just because a notification channel is offline.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Mapping

import requests

log = logging.getLogger(__name__)

ALERT_COLORS = {
    "Very Unhealthy": 0xE74C3C,
    "Unhealthy":      0xE67E22,
    "Unhealthy for Sensitive Groups": 0xF1C40F,
    "Moderate":       0x2ECC71,
    "Good":           0x27AE60,
}


def _build_embed(forecast: Mapping[str, Any]) -> dict:
    horizons = forecast["forecasts"]
    worst_level = max(
        (h["alert_level"] for h in horizons.values()),
        key=lambda lvl: list(ALERT_COLORS).index(lvl) if lvl in ALERT_COLORS else 99,
    )
    color = ALERT_COLORS.get(worst_level, 0x95A5A6)

    fields = []
    for key, label in [("t1", "Tomorrow (t+1)"), ("t3", "In 3 days (t+3)"), ("t7", "In 7 days (t+7)")]:
        h = horizons[key]
        flag = "⚠️" if h["alert"] else "·"
        fields.append({
            "name":   f"{flag} {label}",
            "value":  f"**{h['pm25_forecast']} µg/m³** — {h['alert_level']}",
            "inline": True,
        })

    return {
        "title":       f"CAAS — Chiang Mai Air Quality Alert",
        "description": f"Forecast generated {forecast.get('generated_at_local', forecast.get('generated_at', ''))}",
        "color":       color,
        "fields":      fields,
        "footer":      {"text": f"as_of {forecast.get('latest_pm25_date', '?')} · model: {horizons['t1'].get('model', 'lightgbm')}"},
    }


def send_discord_alert(forecast: Mapping[str, Any], *, webhook_url: str | None = None) -> bool:
    """Post a formatted forecast embed to Discord.

    Returns True on 2xx, False on any failure (logged, never raised).
    """
    url = webhook_url or os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        log.info("DISCORD_WEBHOOK_URL not set — skipping Discord alert")
        return False

    any_alert = any(h["alert"] for h in forecast["forecasts"].values())
    content = "🚨 **Hazard alert** — PM2.5 forecast exceeds threshold." if any_alert else None

    payload = {"embeds": [_build_embed(forecast)]}
    if content:
        payload["content"] = content

    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        log.info("Discord alert sent (status=%d)", r.status_code)
        return True
    except requests.RequestException as exc:
        log.warning("Discord alert failed: %s", exc)
        return False


if __name__ == "__main__":
    # Manual smoke test: python -m alert_channels.discord
    import json
    from pathlib import Path

    forecast_path = Path(__file__).resolve().parents[2] / "03_Data" / "results" / "latest_forecast.json"
    forecast = json.loads(forecast_path.read_text())
    ok = send_discord_alert(forecast)
    print(f"Sent: {ok}")
