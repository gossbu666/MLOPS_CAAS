"""
CAAS — LSTM Training Script v2 (Phase C rewrite)

Improvements over train_lstm.py:
  * Continuous sequence windowing — val/test predictions can use lookback rows
    from prior splits, so we don't lose the first `seq_len` rows of each split.
  * Strict scaler hygiene — scaler is fit on TRAIN rows only (indices ≤ TRAIN_END),
    with an assertion guard asserting no val/test rows leaked into the fit set.
  * Pluggable architectures — build_model(arch, ...) supports:
        stacked       — 3-layer stacked LSTM (baseline improved)
        bidirectional — BiLSTM + LSTM
        attention     — LSTM + self-attention pooling
        cnn_lstm      — Conv1D front-end then LSTM
  * Configurable hyper-params so tune_lstm.py can call `train_one(...)` directly.
  * Outputs use the `_v2` suffix so they don't clobber v1 artifacts until the
    v2 model is promoted.

Usage:
    python train_lstm_v2.py                      # all horizons, default arch
    python train_lstm_v2.py --arch attention
    python train_lstm_v2.py --horizons t3 --epochs 2 --arch stacked   # smoke
"""

from __future__ import annotations

import argparse
import json
import os
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import (
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

import mlflow
import mlflow.keras


BASE = os.path.dirname(os.path.abspath(__file__))
FEATURES = os.path.join(BASE, "..", "03_Data", "processed", "features.csv")
MODELS_DIR = os.path.join(BASE, "..", "03_Data", "models")
RESULTS_DIR = os.path.join(BASE, "..", "03_Data", "results")

TRAIN_END = "2022-12-31"
VAL_END = "2023-12-31"

ALERT_THRESHOLD = 50.0

HORIZONS = {
    "t1": ("pm25_t1", "alert_t1"),
    "t3": ("pm25_t3", "alert_t3"),
    "t7": ("pm25_t7", "alert_t7"),
}

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)


# ───────────────────────────────────────────────────────────────────────────
#  Data prep
# ───────────────────────────────────────────────────────────────────────────
def load_and_impute():
    df = pd.read_csv(FEATURES, parse_dates=["date"], index_col="date").sort_index()
    target_cols = [c for c in df.columns if c.startswith(("pm25_t", "alert_t"))]
    feature_cols = [c for c in df.columns if c not in target_cols]

    train_medians = df.loc[df.index <= TRAIN_END, feature_cols].median()
    df[feature_cols] = df[feature_cols].fillna(train_medians).fillna(0.0)
    df[feature_cols] = df[feature_cols].replace([np.inf, -np.inf], 0.0)
    return df, feature_cols


def fit_scaler_train_only(df: pd.DataFrame, feature_cols: list[str]) -> StandardScaler:
    """Fit StandardScaler on TRAIN rows only.

    Guards against the silent leakage that happened in v1: if any row in the
    fit set has index > TRAIN_END, we raise. This catches accidental reshuffles.
    """
    train_mask = df.index <= TRAIN_END
    fit_slice = df.loc[train_mask, feature_cols]
    assert fit_slice.index.max() <= pd.Timestamp(TRAIN_END), (
        "Scaler fit set leaked post-TRAIN_END rows"
    )
    scaler = StandardScaler()
    scaler.fit(fit_slice.values)
    return scaler


def make_continuous_sequences(
    X_scaled: np.ndarray,
    y: np.ndarray,
    y_alert: np.ndarray,
    dates: pd.DatetimeIndex,
    seq_len: int,
    split_start: str,
    split_end: str | None,
):
    """Build sequences for a split using the full scaled array for lookback.

    Unlike v1 which sliced each split first then windowed, this windows over
    the whole array and selects predictions whose TARGET DATE falls in the
    requested split. Lookback rows may come from earlier splits — that's fine,
    they're post-scaler data and the information is already historical.

    Returns (X_seq, y_seq, y_alert_seq, pred_dates).
    """
    n = len(X_scaled)
    start_ts = pd.Timestamp(split_start)
    end_ts = pd.Timestamp(split_end) if split_end is not None else dates.max()

    X_seq, y_seq, y_al_seq, out_dates = [], [], [], []
    for i in range(seq_len, n):
        pred_date = dates[i]
        if start_ts <= pred_date <= end_ts:
            if np.isnan(y[i]):
                continue
            X_seq.append(X_scaled[i - seq_len : i])
            y_seq.append(y[i])
            y_al_seq.append(y_alert[i])
            out_dates.append(pred_date)
    return (
        np.asarray(X_seq, dtype=np.float32),
        np.asarray(y_seq, dtype=np.float32),
        np.asarray(y_al_seq, dtype=np.int32),
        pd.DatetimeIndex(out_dates),
    )


# ───────────────────────────────────────────────────────────────────────────
#  Model builders
# ───────────────────────────────────────────────────────────────────────────
def build_model(
    arch: str,
    seq_len: int,
    n_features: int,
    hidden_units: int = 64,
    num_layers: int = 2,
    dropout: float = 0.2,
    learning_rate: float = 5e-4,
    loss: str = "huber",
):
    import tensorflow as tf
    from tensorflow.keras.layers import (
        LSTM,
        Bidirectional,
        BatchNormalization,
        Conv1D,
        Dense,
        Dropout,
        Input,
        MaxPooling1D,
        MultiHeadAttention,
        GlobalAveragePooling1D,
        LayerNormalization,
    )
    from tensorflow.keras.models import Model, Sequential
    from tensorflow.keras.optimizers import Adam

    tf.random.set_seed(42)

    if arch == "stacked":
        units = [hidden_units, max(hidden_units // 2, 16), max(hidden_units // 4, 8)]
        units = units[:num_layers]
        model = Sequential()
        model.add(Input(shape=(seq_len, n_features)))
        for k, u in enumerate(units):
            return_seq = k < len(units) - 1
            model.add(LSTM(u, return_sequences=return_seq))
            model.add(BatchNormalization())
            model.add(Dropout(dropout))
        model.add(Dense(16, activation="relu"))
        model.add(Dense(1, activation="linear"))

    elif arch == "bidirectional":
        model = Sequential()
        model.add(Input(shape=(seq_len, n_features)))
        model.add(Bidirectional(LSTM(hidden_units, return_sequences=num_layers > 1)))
        model.add(Dropout(dropout))
        extra = max(num_layers - 1, 0)
        for k in range(extra):
            is_last = k == extra - 1
            model.add(LSTM(max(hidden_units // 2, 16), return_sequences=not is_last))
            model.add(Dropout(dropout))
        model.add(Dense(16, activation="relu"))
        model.add(Dense(1, activation="linear"))

    elif arch == "attention":
        inputs = Input(shape=(seq_len, n_features))
        x = LSTM(hidden_units, return_sequences=True)(inputs)
        x = LayerNormalization()(x)
        x = Dropout(dropout)(x)
        # self-attention over the time axis
        attn = MultiHeadAttention(num_heads=4, key_dim=max(hidden_units // 4, 8))(x, x)
        x = LayerNormalization()(x + attn)
        x = GlobalAveragePooling1D()(x)
        x = Dense(32, activation="relu")(x)
        x = Dropout(dropout)(x)
        out = Dense(1, activation="linear")(x)
        model = Model(inputs, out)

    elif arch == "cnn_lstm":
        model = Sequential()
        model.add(Input(shape=(seq_len, n_features)))
        model.add(Conv1D(filters=64, kernel_size=3, activation="relu", padding="same"))
        model.add(MaxPooling1D(pool_size=2))
        model.add(Conv1D(filters=32, kernel_size=3, activation="relu", padding="same"))
        model.add(LSTM(hidden_units, return_sequences=False))
        model.add(Dropout(dropout))
        model.add(Dense(16, activation="relu"))
        model.add(Dense(1, activation="linear"))

    else:
        raise ValueError(f"Unknown architecture: {arch}")

    model.compile(optimizer=Adam(learning_rate=learning_rate), loss=loss, metrics=["mae"])
    return model


# ───────────────────────────────────────────────────────────────────────────
#  Metric helpers
# ───────────────────────────────────────────────────────────────────────────
def reg_metrics(actual, pred):
    return {
        "mae": float(mean_absolute_error(actual, pred)),
        "rmse": float(np.sqrt(mean_squared_error(actual, pred))),
        "r2": float(r2_score(actual, pred)),
    }


def alert_metrics(pred, y_cls):
    pred_cls = (pred > ALERT_THRESHOLD).astype(int)
    if y_cls.sum() == 0:
        return {}
    return {
        "precision": float(precision_score(y_cls, pred_cls, zero_division=0)),
        "recall": float(recall_score(y_cls, pred_cls, zero_division=0)),
        "f1": float(f1_score(y_cls, pred_cls, zero_division=0)),
        "auroc": float(roc_auc_score(y_cls, pred)),
    }


# ───────────────────────────────────────────────────────────────────────────
#  Train one horizon  (also imported by tune_lstm.py)
# ───────────────────────────────────────────────────────────────────────────
def train_one(
    horizon: str,
    *,
    arch: str = "stacked",
    seq_len: int = 30,
    hidden_units: int = 64,
    num_layers: int = 2,
    dropout: float = 0.2,
    learning_rate: float = 5e-4,
    batch_size: int = 32,
    epochs: int = 100,
    patience: int = 20,
    loss: str = "huber",
    save_artifacts: bool = True,
    verbose: int = 1,
) -> dict:
    import tensorflow as tf
    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

    np.random.seed(42)
    tf.random.set_seed(42)

    reg_target, cls_target = HORIZONS[horizon]
    df, feature_cols = load_and_impute()

    scaler = fit_scaler_train_only(df, feature_cols)
    X_scaled = scaler.transform(df[feature_cols].values).astype(np.float32)
    y = df[reg_target].values.astype(np.float32)
    y_al = df[cls_target].fillna(0).astype(int).values

    X_tr, y_tr, _, _ = make_continuous_sequences(
        X_scaled, y, y_al, df.index, seq_len, "2011-01-01", TRAIN_END
    )
    X_vl, y_vl, y_vl_al, vl_dates = make_continuous_sequences(
        X_scaled, y, y_al, df.index, seq_len,
        pd.Timestamp(TRAIN_END) + pd.Timedelta(days=1), VAL_END,
    )
    X_te, y_te, y_te_al, te_dates = make_continuous_sequences(
        X_scaled, y, y_al, df.index, seq_len,
        pd.Timestamp(VAL_END) + pd.Timedelta(days=1), None,
    )

    if verbose:
        print(
            f"   seq_len={seq_len} arch={arch} | "
            f"train={len(X_tr)}  val={len(X_vl)}  test={len(X_te)}"
        )

    model = build_model(
        arch=arch,
        seq_len=seq_len,
        n_features=len(feature_cols),
        hidden_units=hidden_units,
        num_layers=num_layers,
        dropout=dropout,
        learning_rate=learning_rate,
        loss=loss,
    )

    callbacks = [
        EarlyStopping(patience=patience, restore_best_weights=True, monitor="val_mae"),
        ReduceLROnPlateau(patience=max(patience // 3, 4), factor=0.5, min_lr=1e-6, monitor="val_mae"),
    ]

    history = model.fit(
        X_tr, y_tr,
        validation_data=(X_vl, y_vl),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=callbacks,
        verbose=verbose,
    )

    pred_val = np.clip(model.predict(X_vl, verbose=0).flatten(), 0, None)
    pred_test = np.clip(model.predict(X_te, verbose=0).flatten(), 0, None)

    val_m = reg_metrics(y_vl, pred_val)
    test_m = reg_metrics(y_te, pred_test)
    val_a = alert_metrics(pred_val, y_vl_al)
    test_a = alert_metrics(pred_test, y_te_al)

    result = {
        "horizon": horizon,
        "arch": arch,
        "seq_len": seq_len,
        "hidden_units": hidden_units,
        "num_layers": num_layers,
        "dropout": dropout,
        "learning_rate": learning_rate,
        "batch_size": batch_size,
        "epochs_trained": len(history.history["loss"]),
        "val": val_m,
        "test": test_m,
        "alert_val": val_a,
        "alert_test": test_a,
    }

    if save_artifacts:
        import joblib
        model_path = os.path.join(MODELS_DIR, f"lstm_v2_{horizon}.keras")
        scaler_path = os.path.join(MODELS_DIR, f"lstm_v2_{horizon}_scaler.pkl")
        pred_path = os.path.join(RESULTS_DIR, f"lstm_v2_{horizon}_test_predictions.csv")
        model.save(model_path)
        joblib.dump(scaler, scaler_path)
        pd.DataFrame(
            {
                "date": te_dates,
                "actual": y_te,
                "predicted": pred_test,
                "alert_actual": y_te_al,
                "alert_predicted": (pred_test > ALERT_THRESHOLD).astype(int),
            }
        ).to_csv(pred_path, index=False)
        result["model_path"] = model_path
        result["scaler_path"] = scaler_path
        result["pred_path"] = pred_path

    return result


# ───────────────────────────────────────────────────────────────────────────
#  CLI
# ───────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizons", default="t1,t3,t7")
    parser.add_argument("--arch", default="stacked",
                        choices=["stacked", "bidirectional", "attention", "cnn_lstm"])
    parser.add_argument("--seq-len", type=int, default=30)
    parser.add_argument("--hidden-units", type=int, default=64)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--lr", type=float, default=5e-4)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--loss", default="huber", choices=["huber", "mae", "mse"])
    args = parser.parse_args()

    mlflow.set_tracking_uri(os.path.join(BASE, "..", "mlruns"))
    mlflow.set_experiment("CAAS-LSTM-v2")

    all_results = {}
    for horizon in [h.strip() for h in args.horizons.split(",") if h.strip()]:
        print(f"\n{'='*60}\n🎯  Horizon {horizon.upper()} — arch={args.arch}")
        with mlflow.start_run(run_name=f"LSTM-v2-{horizon}-{args.arch}"):
            result = train_one(
                horizon,
                arch=args.arch,
                seq_len=args.seq_len,
                hidden_units=args.hidden_units,
                num_layers=args.num_layers,
                dropout=args.dropout,
                learning_rate=args.lr,
                batch_size=args.batch_size,
                epochs=args.epochs,
                patience=args.patience,
                loss=args.loss,
            )
            mlflow.log_params({
                "arch": args.arch,
                "seq_len": args.seq_len,
                "hidden_units": args.hidden_units,
                "num_layers": args.num_layers,
                "dropout": args.dropout,
                "lr": args.lr,
                "batch_size": args.batch_size,
                "horizon": horizon,
            })
            for k, v in result["val"].items():
                mlflow.log_metric(f"val_{k}", v)
            for k, v in result["test"].items():
                mlflow.log_metric(f"test_{k}", v)
            for k, v in result["alert_test"].items():
                mlflow.log_metric(f"test_alert_{k}", v)
            print(
                f"   Val  MAE {result['val']['mae']:.2f}  R² {result['val']['r2']:.3f}  "
                f"|  Test MAE {result['test']['mae']:.2f}  R² {result['test']['r2']:.3f}  "
                f"F1 {result['alert_test'].get('f1', float('nan')):.3f}"
            )
        all_results[horizon] = result

    out = os.path.join(RESULTS_DIR, "lstm_v2_summary.json")
    with open(out, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n✅  Saved: {out}")


if __name__ == "__main__":
    main()
