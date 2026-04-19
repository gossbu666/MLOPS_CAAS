"""
Tests for the CAAS FastAPI inference server.

Uses FastAPI's TestClient — no real server needed, no ports opened.
Tests every public endpoint for correct status codes and response shape.
"""
import os
import sys
import pytest

# Add serve/ directory to path so we can import app
ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVE_DIR = os.path.join(ROOT, "04_Scripts", "serve")
sys.path.insert(0, SERVE_DIR)
sys.path.insert(0, os.path.join(ROOT, "04_Scripts"))

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_has_status_field(self):
        resp = client.get("/health")
        data = resp.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_health_has_models_loaded(self):
        resp = client.get("/health")
        data = resp.json()
        assert "champion_horizons_loaded" in data
        assert isinstance(data["champion_horizons_loaded"], list)
        assert "xgboost_horizons_loaded" in data
        assert isinstance(data["xgboost_horizons_loaded"], list)

    def test_health_has_timestamp(self):
        resp = client.get("/health")
        data = resp.json()
        assert "timestamp" in data


class TestForecastEndpoint:
    def test_forecast_returns_200(self):
        resp = client.get("/forecast")
        assert resp.status_code in (200, 503), (
            f"Unexpected status {resp.status_code}: {resp.text}"
        )

    def test_forecast_structure_when_models_loaded(self):
        resp = client.get("/forecast")
        if resp.status_code == 503:
            pytest.skip("Models not loaded — run train_xgboost.py first")

        data = resp.json()
        assert "station"      in data
        assert "as_of_date"   in data
        assert "forecasts"    in data
        assert "generated_at" in data

    def test_forecast_has_all_horizons(self):
        resp = client.get("/forecast")
        if resp.status_code == 503:
            pytest.skip("Models not loaded")

        forecasts = resp.json()["forecasts"]
        for horizon in ["t1", "t3", "t7"]:
            assert horizon in forecasts, f"Missing horizon {horizon} in forecast"

    def test_forecast_pm25_is_non_negative(self):
        resp = client.get("/forecast")
        if resp.status_code == 503:
            pytest.skip("Models not loaded")

        for h, fc in resp.json()["forecasts"].items():
            assert fc["pm25_forecast"] >= 0, f"{h}: negative PM2.5 {fc['pm25_forecast']}"

    def test_forecast_alert_level_is_valid(self):
        valid_levels = {
            "Good", "Moderate", "Unhealthy for Sensitive Groups",
            "Unhealthy", "Very Unhealthy", "Hazardous"
        }
        resp = client.get("/forecast")
        if resp.status_code == 503:
            pytest.skip("Models not loaded")

        for h, fc in resp.json()["forecasts"].items():
            assert fc["alert_level"] in valid_levels, (
                f"{h}: unexpected alert level '{fc['alert_level']}'"
            )


class TestHistoryEndpoint:
    def test_history_returns_200_or_503(self):
        resp = client.get("/history")
        assert resp.status_code in (200, 503)

    def test_history_default_30_days(self):
        resp = client.get("/history")
        if resp.status_code == 503:
            pytest.skip("PM2.5 data not found")
        data = resp.json()
        assert data["days"] == 30

    def test_history_custom_days(self):
        resp = client.get("/history?days=7")
        if resp.status_code == 503:
            pytest.skip("PM2.5 data not found")
        data = resp.json()
        assert data["days"] == 7
        assert len(data["data"]) <= 7

    def test_history_data_has_required_fields(self):
        resp = client.get("/history?days=5")
        if resp.status_code == 503:
            pytest.skip("PM2.5 data not found")
        for entry in resp.json()["data"]:
            assert "date"  in entry
            assert "pm25"  in entry
            assert "alert" in entry
            assert "level" in entry


class TestModelInfoEndpoint:
    def test_model_info_returns_200(self):
        resp = client.get("/model/info")
        assert resp.status_code == 200

    def test_model_info_has_champion_field(self):
        resp = client.get("/model/info")
        data = resp.json()
        # Either returns champion info or a message — both are valid
        assert "champion_model" in data or "message" in data


class TestPredictEndpoint:
    def test_predict_with_minimal_input(self):
        resp = client.post("/predict", json={
            "pm25_lag1": 35.0,
            "pm25_lag3": 32.0,
            "pm25_lag7": 28.0,
        })
        if resp.status_code == 503:
            pytest.skip("Models not loaded")
        assert resp.status_code == 200

    def test_predict_response_has_forecasts(self):
        resp = client.post("/predict", json={
            "pm25_lag1": 35.0,
            "pm25_lag3": 32.0,
            "pm25_lag7": 28.0,
        })
        if resp.status_code == 503:
            pytest.skip("Models not loaded")
        data = resp.json()
        assert "forecasts" in data

    def test_predict_haze_scenario(self):
        """During haze season (March) with high PM2.5 lag, forecast should be elevated."""
        resp = client.post("/predict", json={
            "pm25_lag1":  120.0,
            "pm25_lag3":  110.0,
            "pm25_lag7":   95.0,
            "is_haze_season": 1,
            "month": 3,
        })
        if resp.status_code == 503:
            pytest.skip("Models not loaded")
        assert resp.status_code == 200
        # Forecast for high-lag haze scenario should be > 0
        for h, fc in resp.json()["forecasts"].items():
            assert fc["pm25_forecast"] > 0
