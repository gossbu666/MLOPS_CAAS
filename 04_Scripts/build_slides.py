"""CAAS Final Presentation — PPTX build script.

Generates 07_Final/slides/CAAS_final.pptx from the approved design spec at
docs/superpowers/specs/2026-04-22-final-slides-design.md.

Usage (from project root, caas-env activated):
    python 04_Scripts/build_slides.py

Output: 07_Final/slides/CAAS_final.pptx
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "07_Final" / "slides" / "CAAS_final.pptx"
SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)  # 16:9 widescreen

# ============================================================
#  SPEC-PINNED CONSTANTS
#  These values must match 03_Data/results/*.json exactly.
#  verify_numbers() cross-checks at build time — fails loudly on drift.
# ============================================================
RESULTS_DIR = PROJECT_ROOT / "03_Data" / "results"

# Slide 6 — test-set metrics (from lightgbm/xgboost/lstm_summary.json)
METRICS = {
    "lightgbm": {
        "mae":   {"t1": 5.12, "t3": 6.77, "t7": 8.25},
        "r2":    {"t1": 0.841, "t3": 0.729, "t7": 0.600},
        "auroc": {"t1": 0.992, "t3": 0.973, "t7": 0.946},
    },
    "xgboost":  {
        "mae":   {"t1": 5.31, "t3": 7.08, "t7": 8.90},
        "r2":    {"t1": 0.843, "t3": 0.723, "t7": 0.544},
        "auroc": {"t1": 0.992, "t3": 0.973, "t7": 0.933},
    },
    "lstm":     {
        "mae":   {"t1": 6.67, "t3": 8.87, "t7": 8.06},
        "r2":    {"t1": 0.753, "t3": 0.540, "t7": 0.608},
        "auroc": {"t1": 0.984, "t3": 0.927, "t7": 0.961},
    },
}

# Slide 8 — ablation deltas (from ablation_summary.json, % MAE degradation without FIRMS)
ABLATION_DELTAS = {"t1": 6.78, "t3": 5.10, "t7": 4.28}

# Slide 8 — Scenario C optimal thresholds + F1 gain vs default 50 (from scenario_c_summary.json)
SCENARIO_C = {
    "t1": {"threshold": 53.72, "f1_gain_pct": 4.0},
    "t3": {"threshold": 50.98, "f1_gain_pct": 0.2},
    "t7": {"threshold": 45.82, "f1_gain_pct": 1.1},
}


def _load_results(name: str) -> dict:
    import json
    path = RESULTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing results file: {path}")
    with path.open() as f:
        return json.load(f)


def verify_numbers() -> None:
    """Cross-check spec constants against 03_Data/results/*.json.

    Fails the build loudly on drift so a stale number never reaches the grader.
    Tolerances: MAE ±0.02, R² ±0.01, AUROC ±0.01, ablation ±0.5pp, threshold ±0.5, f1_gain_pct ±0.5pp.
    """
    mismatches: list[str] = []

    # Model metrics
    model_files = {
        "lightgbm": "lightgbm_summary.json",
        "xgboost":  "xgboost_summary.json",
        "lstm":     "lstm_summary.json",
    }
    for family, json_name in model_files.items():
        try:
            data = _load_results(json_name)
        except FileNotFoundError as e:
            mismatches.append(str(e))
            continue
        for h in ("t1", "t3", "t7"):
            # mae and r2 live under ["test"]
            for metric, tol in (("mae", 0.02), ("r2", 0.01)):
                spec_val = METRICS[family][metric][h]
                try:
                    actual = float(data[h]["test"][metric])
                except (KeyError, TypeError):
                    mismatches.append(f"{family}.{metric}.{h}: cannot read data[{h!r}]['test'][{metric!r}]")
                    continue
                if abs(actual - spec_val) > tol:
                    mismatches.append(
                        f"{family}.{metric}.{h}: spec={spec_val}, json={actual:.4f} "
                        f"(Δ={abs(actual-spec_val):.4f} > tol={tol})"
                    )
            # auroc lives under ["alert_test"]
            spec_val = METRICS[family]["auroc"][h]
            try:
                actual = float(data[h]["alert_test"]["auroc"])
            except (KeyError, TypeError):
                mismatches.append(f"{family}.auroc.{h}: cannot read data[{h!r}]['alert_test']['auroc']")
                continue
            if abs(actual - spec_val) > 0.01:
                mismatches.append(
                    f"{family}.auroc.{h}: spec={spec_val}, json={actual:.4f} "
                    f"(Δ={abs(actual-spec_val):.4f} > tol=0.01)"
                )

    # Ablation
    try:
        ab = _load_results("ablation_summary.json")
        for h in ("t1", "t3", "t7"):
            spec_pct = ABLATION_DELTAS[h]
            try:
                actual = float(ab[h]["mae_pct_change"])
            except (KeyError, TypeError):
                mismatches.append(f"ablation.{h}: cannot read data[{h!r}]['mae_pct_change']")
                continue
            if abs(actual - spec_pct) > 0.5:
                mismatches.append(f"ablation.{h}: spec={spec_pct}%, json={actual:.2f}% (Δ>0.5pp)")
    except FileNotFoundError as e:
        mismatches.append(str(e))

    # Scenario C
    try:
        sc = _load_results("scenario_c_summary.json")
        for h in ("t1", "t3", "t7"):
            spec_thr = SCENARIO_C[h]["threshold"]
            spec_gain = SCENARIO_C[h]["f1_gain_pct"]
            try:
                actual_thr = float(sc[h]["optimal_threshold"])
                actual_gain_pct = float(sc[h]["f1_gain"]) * 100.0
            except (KeyError, TypeError):
                mismatches.append(f"scenario_c.{h}: cannot read optimal_threshold or f1_gain")
                continue
            if abs(actual_thr - spec_thr) > 0.5:
                mismatches.append(
                    f"scenario_c.{h}.threshold: spec={spec_thr}, json={actual_thr} (Δ>0.5)"
                )
            if abs(actual_gain_pct - spec_gain) > 0.5:
                mismatches.append(
                    f"scenario_c.{h}.f1_gain_pct: spec={spec_gain}%, json={actual_gain_pct:.2f}% (Δ>0.5pp)"
                )
    except FileNotFoundError as e:
        mismatches.append(str(e))

    if mismatches:
        header = "=" * 60 + "\nSPEC/JSON MISMATCH — build refuses to generate stale deck:\n"
        body = "\n".join(f"  - {m}" for m in mismatches)
        footer = "\n" + "=" * 60
        raise ValueError(header + body + footer)


def build() -> Path:
    """Build the full 14-slide deck and save to OUTPUT_PATH."""
    verify_numbers()  # fails build if any spec constant drifted from its JSON

    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    # Slides will be added here by subsequent tasks.

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUTPUT_PATH))
    return OUTPUT_PATH


if __name__ == "__main__":
    out = build()
    print(f"Built: {out}")
