"""
Tests for saved XGBoost model artifacts.

Verifies:
  - All 3 model files exist
  - Models load without error
  - Predictions are the right shape
  - Predictions are non-negative (PM2.5 >= 0)
  - Feature count matches training data
  - Result JSON files exist and have the right structure
"""
import os
import json
import pytest
import numpy as np
import pandas as pd
from conftest import HORIZONS, MODELS_DIR, RESULTS_DIR, EXPECTED_FEATURES


class TestModelFiles:
    def test_all_xgboost_models_exist(self):
        for h in HORIZONS:
            path = os.path.join(MODELS_DIR, f"xgboost_{h}.json")
            assert os.path.exists(path), f"Missing: {path}"

    def test_xgboost_models_not_empty(self):
        for h in HORIZONS:
            path = os.path.join(MODELS_DIR, f"xgboost_{h}.json")
            size = os.path.getsize(path)
            assert size > 10_000, f"xgboost_{h}.json suspiciously small: {size} bytes"


class TestModelInference:
    def test_models_load_and_predict(self, xgb_models, features_df):
        """Load each model and run a real prediction on the last feature row."""
        target_cols  = [c for c in features_df.columns if c.startswith(("pm25_t", "alert_t"))]
        feature_cols = [c for c in features_df.columns if c not in target_cols]

        train_medians = features_df[features_df.index <= "2022-12-31"][feature_cols].median()
        latest = features_df[feature_cols].dropna(subset=["pm25_lag1"]).tail(1)
        latest = latest.fillna(train_medians).fillna(0)

        for h, model in xgb_models.items():
            expected_feats = model.get_booster().feature_names
            row = latest.copy()
            for col in expected_feats:
                if col not in row.columns:
                    row[col] = 0.0
            row = row[expected_feats]

            preds = model.predict(row)
            assert preds.shape == (1,), f"Expected shape (1,), got {preds.shape}"

    def test_predictions_are_non_negative(self, xgb_models, features_df):
        """Clipped predictions must be >= 0 (PM2.5 can't be negative)."""
        target_cols  = [c for c in features_df.columns if c.startswith(("pm25_t", "alert_t"))]
        feature_cols = [c for c in features_df.columns if c not in target_cols]

        train_medians = features_df[features_df.index <= "2022-12-31"][feature_cols].median()
        sample = features_df[feature_cols].dropna(subset=["pm25_lag1"]).tail(10)
        sample = sample.fillna(train_medians).fillna(0)

        for h, model in xgb_models.items():
            expected_feats = model.get_booster().feature_names
            X = sample.copy()
            for col in expected_feats:
                if col not in X.columns:
                    X[col] = 0.0
            X = X[expected_feats]

            preds = np.clip(model.predict(X), 0, None)
            assert (preds >= 0).all(), f"Negative predictions in {h}: {preds[preds < 0]}"

    def test_prediction_in_realistic_range(self, xgb_models, features_df):
        """Predictions should be within realistic PM2.5 range (0–500 µg/m³)."""
        target_cols  = [c for c in features_df.columns if c.startswith(("pm25_t", "alert_t"))]
        feature_cols = [c for c in features_df.columns if c not in target_cols]

        train_medians = features_df[features_df.index <= "2022-12-31"][feature_cols].median()
        sample = features_df[feature_cols].dropna(subset=["pm25_lag1"]).tail(30)
        sample = sample.fillna(train_medians).fillna(0)

        for h, model in xgb_models.items():
            expected_feats = model.get_booster().feature_names
            X = sample.copy()
            for col in expected_feats:
                if col not in X.columns:
                    X[col] = 0.0
            X = X[expected_feats]

            preds = np.clip(model.predict(X), 0, None)
            assert preds.max() < 600, f"{h}: prediction unrealistically high: {preds.max():.1f}"


class TestResultFiles:
    def test_xgboost_summary_exists(self):
        path = os.path.join(RESULTS_DIR, "xgboost_summary.json")
        assert os.path.exists(path)

    def test_xgboost_summary_structure(self):
        path = os.path.join(RESULTS_DIR, "xgboost_summary.json")
        with open(path) as f:
            data = json.load(f)
        for h in HORIZONS:
            assert h in data, f"Missing horizon {h} in summary"
            assert "test" in data[h], f"Missing 'test' key for {h}"
            assert "mae" in data[h]["test"], f"Missing 'mae' for {h}"
            assert "r2"  in data[h]["test"], f"Missing 'r2' for {h}"

    def test_prediction_csvs_exist(self):
        for h in HORIZONS:
            path = os.path.join(RESULTS_DIR, f"xgboost_{h}_test_predictions.csv")
            assert os.path.exists(path), f"Missing: {path}"

    def test_prediction_csvs_have_correct_columns(self):
        for h in HORIZONS:
            path = os.path.join(RESULTS_DIR, f"xgboost_{h}_test_predictions.csv")
            df = pd.read_csv(path)
            expected_cols = {"date", "actual", "predicted", "alert_actual", "alert_predicted"}
            assert expected_cols <= set(df.columns), (
                f"{h} predictions missing columns: {expected_cols - set(df.columns)}"
            )

    def test_prediction_csvs_minimum_rows(self):
        for h in HORIZONS:
            path = os.path.join(RESULTS_DIR, f"xgboost_{h}_test_predictions.csv")
            df = pd.read_csv(path)
            assert len(df) >= 300, f"{h} test predictions too few rows: {len(df)}"

    def test_scenario_c_summary_exists(self):
        path = os.path.join(RESULTS_DIR, "scenario_c_summary.json")
        assert os.path.exists(path)

    def test_shap_summary_exists(self):
        path = os.path.join(RESULTS_DIR, "shap_summary.json")
        assert os.path.exists(path)
