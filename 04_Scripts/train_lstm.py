"""
CAAS — LSTM Training Script (with MLflow)
Trains one LSTM model per forecast horizon (t+1, t+3, t+7).
Uses a 30-day sliding window as sequence input.

Architecture: Input(30, n_features) → LSTM(64) → Dropout(0.2)
              → LSTM(32) → Dropout(0.2) → Dense(1)

Usage:
    python train_lstm.py

Requirements: features.csv must exist (run build_features.py first)
Note: GPU optional — runs fine on CPU (~10-20 min per horizon)
"""

import os
import json
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
import mlflow
import mlflow.keras
import warnings
warnings.filterwarnings("ignore")

# ── Config ─────────────────────────────────────────────────
BASE        = os.path.dirname(os.path.abspath(__file__))
FEATURES    = os.path.join(BASE, "..", "03_Data", "processed", "features.csv")
MODELS_DIR  = os.path.join(BASE, "..", "03_Data", "models")
RESULTS_DIR = os.path.join(BASE, "..", "03_Data", "results")

TRAIN_END = "2022-12-31"
VAL_END   = "2023-12-31"

SEQUENCE_LEN     = 60    # 60-day lookback window (up from 30 — more temporal context)
ALERT_THRESHOLD  = 50.0
EPOCHS           = 150   # more room before early stopping
BATCH_SIZE       = 32
PATIENCE         = 25    # more patience to find better minima

HORIZONS = {
    "t1": ("pm25_t1", "alert_t1"),
    "t3": ("pm25_t3", "alert_t3"),
    "t7": ("pm25_t7", "alert_t7"),
}

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# ── Load features ───────────────────────────────────────────
print("📂  Loading features...")
df = pd.read_csv(FEATURES, parse_dates=["date"], index_col="date")
print(f"   Shape: {df.shape}")

target_cols  = [c for c in df.columns if c.startswith(("pm25_t", "alert_t"))]
feature_cols = [c for c in df.columns if c not in target_cols]

# ── Median imputation (training median only) ────────────────
df_train_raw = df[df.index <= TRAIN_END]
train_medians = df_train_raw[feature_cols].median()
df[feature_cols] = df[feature_cols].fillna(train_medians)
# Fallback: some features may have all-NaN in training → median is NaN too
df[feature_cols] = df[feature_cols].fillna(0)
# Remove any inf values that could explode through LSTM
df[feature_cols] = df[feature_cols].replace([float("inf"), float("-inf")], 0)

nan_left = df[feature_cols].isnull().sum().sum()
if nan_left > 0:
    print(f"   ⚠️  WARNING: {nan_left} NaN values remain after imputation — forcing to 0")
    df[feature_cols] = df[feature_cols].fillna(0)
else:
    print(f"   ✅  No NaN in features after imputation")

# ── Build sequences ─────────────────────────────────────────
def make_sequences(data_X, data_y, seq_len):
    """Create (X_seq, y) pairs with sliding window."""
    X_seq, y_seq = [], []
    for i in range(seq_len, len(data_X)):
        X_seq.append(data_X[i - seq_len:i])
        y_seq.append(data_y[i])
    return np.array(X_seq), np.array(y_seq)

# ── MLflow setup ────────────────────────────────────────────
mlflow.set_tracking_uri(os.path.join(BASE, "..", "mlruns"))
mlflow.set_experiment("CAAS-LSTM")

all_results = {}

for horizon, (reg_target, cls_target) in HORIZONS.items():
    print(f"\n{'='*60}")
    print(f"🎯  Horizon {horizon.upper()} — target: {reg_target}")

    # Drop rows without target
    df_h = df[[*feature_cols, reg_target, cls_target]].dropna(subset=[reg_target])

    # Split
    df_tr = df_h[df_h.index <= TRAIN_END]
    df_vl = df_h[(df_h.index > TRAIN_END) & (df_h.index <= VAL_END)]
    df_te = df_h[df_h.index > VAL_END]

    # Scale features (fit on train only)
    scaler = StandardScaler()
    X_tr_sc = scaler.fit_transform(df_tr[feature_cols])
    X_vl_sc = scaler.transform(df_vl[feature_cols])
    X_te_sc = scaler.transform(df_te[feature_cols])

    y_tr = df_tr[reg_target].values
    y_vl = df_vl[reg_target].values
    y_te = df_te[reg_target].values

    y_cls_tr = df_tr[cls_target].astype(int).values
    y_cls_vl = df_vl[cls_target].astype(int).values
    y_cls_te = df_te[cls_target].astype(int).values

    # Build sequences
    X_tr_seq, y_tr_seq = make_sequences(X_tr_sc, y_tr, SEQUENCE_LEN)
    X_vl_seq, y_vl_seq = make_sequences(X_vl_sc, y_vl, SEQUENCE_LEN)
    X_te_seq, y_te_seq = make_sequences(X_te_sc, y_te, SEQUENCE_LEN)

    # Alert targets aligned with sequence offset
    y_cls_vl_seq = y_cls_vl[SEQUENCE_LEN:]
    y_cls_te_seq = y_cls_te[SEQUENCE_LEN:]

    print(f"   Train sequences: {len(X_tr_seq):,}  Val: {len(X_vl_seq):,}  Test: {len(X_te_seq):,}")
    print(f"   Sequence shape : {X_tr_seq.shape}")

    # ── Build LSTM model ────────────────────────────────────
    try:
        import tensorflow as tf
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import LSTM, Dense, Dropout
        from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
        from tensorflow.keras.optimizers import Adam
    except ImportError:
        print("   ⚠️  TensorFlow not installed. Run: pip install tensorflow")
        continue

    tf.random.set_seed(42)
    np.random.seed(42)

    # Deeper architecture: 3 LSTM layers + BatchNorm for stable training
    # lr=0.0005 (slower, avoids overshooting) + stronger ReduceLROnPlateau
    from tensorflow.keras.layers import BatchNormalization

    model = Sequential([
        LSTM(128, return_sequences=True,
             input_shape=(SEQUENCE_LEN, len(feature_cols))),
        BatchNormalization(),
        Dropout(0.2),
        LSTM(64, return_sequences=True),
        BatchNormalization(),
        Dropout(0.2),
        LSTM(32, return_sequences=False),
        Dropout(0.2),
        Dense(16, activation="relu"),
        Dense(1, activation="linear"),
    ])

    model.compile(
        optimizer=Adam(learning_rate=0.0005),  # slower lr for better convergence
        loss="huber",      # Huber loss: robust to outliers (PM2.5 spikes)
        metrics=["mae"],
    )

    callbacks = [
        EarlyStopping(patience=PATIENCE, restore_best_weights=True,
                      monitor="val_mae", verbose=0),
        ReduceLROnPlateau(patience=10, factor=0.5, min_lr=1e-6,
                          monitor="val_mae", verbose=0),
    ]

    with mlflow.start_run(run_name=f"LSTM-{horizon}"):
        mlflow.log_params({
            "horizon":       horizon,
            "sequence_len":  SEQUENCE_LEN,
            "lstm_units":    [128, 64, 32],
            "dropout":       0.2,
            "batch_size":    BATCH_SIZE,
            "optimizer":     "Adam",
            "lr":            0.0005,
            "loss":          "huber",
            "early_stopping_patience": PATIENCE,
            "n_features":    len(feature_cols),
        })

        history = model.fit(
            X_tr_seq, y_tr_seq,
            validation_data=(X_vl_seq, y_vl_seq),
            epochs=EPOCHS,
            batch_size=BATCH_SIZE,
            callbacks=callbacks,
            verbose=1,
        )

        # Predict
        pred_val  = model.predict(X_vl_seq, verbose=0).flatten()
        pred_test = model.predict(X_te_seq, verbose=0).flatten()
        pred_val  = np.clip(pred_val, 0, None)
        pred_test = np.clip(pred_test, 0, None)

        # Regression metrics
        def reg_m(pred, actual):
            return {
                "mae":  mean_absolute_error(actual, pred),
                "rmse": np.sqrt(mean_squared_error(actual, pred)),
                "r2":   r2_score(actual, pred),
            }

        metrics_val  = reg_m(pred_val,  y_vl_seq)
        metrics_test = reg_m(pred_test, y_te_seq)

        # Alert metrics
        def alert_m(pred, y_cls):
            pred_cls = (pred > ALERT_THRESHOLD).astype(int)
            if y_cls.sum() == 0:
                return {}
            return {
                "precision": precision_score(y_cls, pred_cls, zero_division=0),
                "recall":    recall_score(y_cls, pred_cls, zero_division=0),
                "f1":        f1_score(y_cls, pred_cls, zero_division=0),
                "auroc":     roc_auc_score(y_cls, pred),
            }

        alert_val  = alert_m(pred_val,  y_cls_vl_seq)
        alert_test = alert_m(pred_test, y_cls_te_seq)

        # Log metrics
        for k, v in metrics_val.items():
            mlflow.log_metric(f"val_{k}", v)
        for k, v in metrics_test.items():
            mlflow.log_metric(f"test_{k}", v)
        for k, v in alert_test.items():
            mlflow.log_metric(f"test_alert_{k}", v)

        mlflow.log_metric("epochs_trained", len(history.history["loss"]))

        print(f"\n   📊 Validation  — MAE: {metrics_val['mae']:.2f}  RMSE: {metrics_val['rmse']:.2f}  R²: {metrics_val['r2']:.3f}")
        print(f"   📊 Test        — MAE: {metrics_test['mae']:.2f}  RMSE: {metrics_test['rmse']:.2f}  R²: {metrics_test['r2']:.3f}")
        if alert_test:
            print(f"   🚨 Test Alert  — Precision: {alert_test['precision']:.3f}  Recall: {alert_test['recall']:.3f}  F1: {alert_test['f1']:.3f}")

        # Save model
        model_path = os.path.join(MODELS_DIR, f"lstm_{horizon}.keras")
        model.save(model_path)
        mlflow.keras.log_model(model, f"model_{horizon}")

        # Save scaler (needed for inference)
        import joblib
        scaler_path = os.path.join(MODELS_DIR, f"lstm_{horizon}_scaler.pkl")
        joblib.dump(scaler, scaler_path)

        # Save predictions
        # Align dates with sequence offset
        test_dates = df_te.index[SEQUENCE_LEN:]
        pred_df = pd.DataFrame({
            "date":           test_dates,
            "actual":         y_te_seq,
            "predicted":      pred_test,
            "alert_actual":   y_cls_te_seq,
            "alert_predicted":(pred_test > ALERT_THRESHOLD).astype(int),
        })
        pred_path = os.path.join(RESULTS_DIR, f"lstm_{horizon}_test_predictions.csv")
        pred_df.to_csv(pred_path, index=False)
        mlflow.log_artifact(pred_path)

        all_results[horizon] = {
            "val":        metrics_val,
            "test":       metrics_test,
            "alert_test": alert_test,
            "epochs":     len(history.history["loss"]),
        }

# ── Final summary ───────────────────────────────────────────
print(f"\n{'='*60}")
print("📋  FINAL RESULTS SUMMARY — LSTM")
print(f"{'='*60}")
print(f"{'Horizon':<10} {'Split':<8} {'MAE':>7} {'RMSE':>7} {'R²':>7} {'F1':>7}")
print("-" * 50)
for h, res in all_results.items():
    for split in ["val", "test"]:
        m = res[split]
        f1 = res.get("alert_test", {}).get("f1", float("nan")) if split == "test" else float("nan")
        print(f"{h:<10} {split:<8} {m['mae']:>7.2f} {m['rmse']:>7.2f} {m['r2']:>7.3f} {f1:>7.3f}")

results_path = os.path.join(RESULTS_DIR, "lstm_summary.json")
with open(results_path, "w") as f:
    json.dump(all_results, f, indent=2)
print(f"\n✅  Results saved: {results_path}")
print("✅  MLflow runs logged — run 'mlflow ui' to explore")
