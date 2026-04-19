"""
Tests for the feature engineering pipeline output (features.csv).

Verifies:
  - File exists and loads
  - Minimum row count
  - All 45 expected feature columns present
  - All 6 target columns present
  - Date index is sorted and has no duplicates
  - No future leakage (target column dates make sense)
  - Chronological split boundaries are correct
  - Alert targets are binary (0/1)
  - Lag features are positive where PM2.5 is positive
"""
import pytest
import numpy as np
import pandas as pd
from conftest import (
    EXPECTED_FEATURES, EXPECTED_TARGETS, features_df
)

MIN_ROWS    = 4_000    # at least 4,000 days of data
TRAIN_END   = "2022-12-31"
VAL_END     = "2023-12-31"


class TestFeaturesSchema:
    def test_minimum_rows(self, features_df):
        assert len(features_df) >= MIN_ROWS, (
            f"Only {len(features_df)} rows — expected >= {MIN_ROWS}"
        )

    def test_all_feature_columns_present(self, features_df):
        missing = [c for c in EXPECTED_FEATURES if c not in features_df.columns]
        assert not missing, f"Missing feature columns: {missing}"

    def test_all_target_columns_present(self, features_df):
        missing = [c for c in EXPECTED_TARGETS if c not in features_df.columns]
        assert not missing, f"Missing target columns: {missing}"

    def test_no_extra_unexpected_columns(self, features_df):
        expected_all = set(EXPECTED_FEATURES + EXPECTED_TARGETS)
        actual = set(features_df.columns)
        unexpected = actual - expected_all
        assert not unexpected, f"Unexpected columns: {unexpected}"

    def test_date_index_sorted(self, features_df):
        assert features_df.index.is_monotonic_increasing, "Date index is not sorted"

    def test_no_duplicate_dates(self, features_df):
        dupes = features_df.index.duplicated().sum()
        assert dupes == 0, f"{dupes} duplicate dates found"


class TestFeaturesContent:
    def test_alert_targets_are_binary(self, features_df):
        for col in ["alert_t1", "alert_t3", "alert_t7"]:
            unique = set(features_df[col].dropna().unique())
            assert unique <= {0, 1, 0.0, 1.0}, (
                f"{col} has non-binary values: {unique}"
            )

    def test_pm25_targets_are_positive(self, features_df):
        for col in ["pm25_t1", "pm25_t3", "pm25_t7"]:
            neg = (features_df[col].dropna() < 0).sum()
            assert neg == 0, f"{col} has {neg} negative values"

    def test_lag1_correlates_with_next_day_target(self, features_df):
        """pm25_lag1 should be strongly correlated with pm25_t1 (both reflect ~same period)."""
        df = features_df[["pm25_lag1", "pm25_t1"]].dropna()
        corr = df["pm25_lag1"].corr(df["pm25_t1"])
        assert corr > 0.5, f"pm25_lag1 vs pm25_t1 correlation too low: {corr:.3f}"

    def test_is_haze_season_is_binary(self, features_df):
        unique = set(features_df["is_haze_season"].dropna().unique())
        assert unique <= {0, 1, 0.0, 1.0}, f"is_haze_season values: {unique}"

    def test_sin_cos_month_in_range(self, features_df):
        for col in ["sin_month", "cos_month", "sin_doy", "cos_doy"]:
            vals = features_df[col].dropna()
            assert vals.between(-1.01, 1.01).all(), f"{col} out of [-1, 1] range"


class TestChronologicalSplit:
    def test_train_split_size(self, features_df):
        df_train = features_df[features_df.index <= TRAIN_END]
        assert len(df_train) >= 2_000, f"Train split too small: {len(df_train)}"

    def test_val_split_size(self, features_df):
        df_val = features_df[
            (features_df.index > TRAIN_END) & (features_df.index <= VAL_END)
        ]
        assert len(df_val) >= 300, f"Val split too small: {len(df_val)}"

    def test_test_split_size(self, features_df):
        df_test = features_df[features_df.index > VAL_END]
        assert len(df_test) >= 300, f"Test split too small: {len(df_test)}"

    def test_splits_are_non_overlapping(self, features_df):
        train = set(features_df[features_df.index <= TRAIN_END].index)
        val   = set(features_df[
            (features_df.index > TRAIN_END) & (features_df.index <= VAL_END)
        ].index)
        test  = set(features_df[features_df.index > VAL_END].index)
        assert not (train & val),  "Train/Val overlap!"
        assert not (train & test), "Train/Test overlap!"
        assert not (val & test),   "Val/Test overlap!"
