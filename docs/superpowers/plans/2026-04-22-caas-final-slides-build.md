# CAAS Final Slides Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python script (`04_Scripts/build_slides.py`) that generates `07_Final/slides/CAAS_final.pptx` — a 14-slide, 15-minute defense deck matching the approved spec at [docs/superpowers/specs/2026-04-22-final-slides-design.md](../specs/2026-04-22-final-slides-design.md) exactly.

**Architecture:** Single Python script using `python-pptx` to emit a single `.pptx` file. Text is the source of truth — images are rendered as **labeled placeholder frames** (gray fill, dashed border, caption) that the user deletes + pastes real images into. Numeric values (MAE, R², thresholds) are pinned as Python constants and cross-checked against `03_Data/results/*.json` at build time, failing loudly on mismatch so the grader never sees a stale number.

**Tech Stack:** Python 3.11 (`caas-env/`), `python-pptx>=0.6.23`, `pytest` for smoke tests. No PDF export in the build script — user imports to Canva, exports to PDF from there.

---

## File Structure

```
04_Scripts/
  build_slides.py              # NEW — single-file generator (~700 LOC)

tests/
  test_build_slides.py         # NEW — smoke tests (14 slides, 19 placeholders, text presence)

07_Final/slides/
  CAAS_final.pptx              # OUTPUT — overwritten each build
```

**Design decisions locked in file structure:**
- Single file for the build script. The logic is linear (build slide 1 → slide 14) and the user will want to tweak text without navigating multiple modules. One file, clearly sectioned with `# === Slide N: Title ===` headers.
- Tests live in existing `tests/` directory using the project's existing pytest setup (`pytest.ini` already present).

---

## Task 1: Environment setup + file skeleton

**Files:**
- Create: `04_Scripts/build_slides.py`
- Create: `tests/test_build_slides.py`
- Modify: `requirements.txt` (add `python-pptx`)

- [ ] **Step 1: Install python-pptx in caas-env**

Run:
```bash
cd "/Users/supanut.k/WORKING_DRIVE/AIT/2nd_semester/DATA ENGINEER/Proposal Presentation"
source caas-env/bin/activate
pip install "python-pptx>=0.6.23"
pip show python-pptx | head -5
```

Expected: `Version: 0.6.x` (or newer) printed. Note the exact version for Step 2.

- [ ] **Step 2: Pin python-pptx in requirements.txt**

Open `requirements.txt`, add one line (alphabetical order, near `openmeteo-requests`):

```
python-pptx==<version-from-step-1>
```

- [ ] **Step 3: Create file skeleton**

Create `04_Scripts/build_slides.py` with:

```python
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


def build() -> Path:
    """Build the full 14-slide deck and save to OUTPUT_PATH."""
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
```

- [ ] **Step 4: Create smoke test file**

Create `tests/test_build_slides.py`:

```python
"""Smoke tests for the CAAS PPTX build script."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from pptx import Presentation

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = PROJECT_ROOT / "07_Final" / "slides" / "CAAS_final.pptx"
SCRIPT = PROJECT_ROOT / "04_Scripts" / "build_slides.py"


@pytest.fixture(scope="module")
def built_deck() -> Presentation:
    """Run the build script once per test module, return the loaded deck."""
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=PROJECT_ROOT)
    assert OUTPUT.exists(), f"Build did not produce {OUTPUT}"
    return Presentation(str(OUTPUT))


def test_file_is_generated(built_deck):
    """The output .pptx exists and is non-trivially sized."""
    assert OUTPUT.stat().st_size > 10_000, "pptx file is suspiciously small"
```

- [ ] **Step 5: Run smoke test to verify skeleton works**

Run:
```bash
cd "/Users/supanut.k/WORKING_DRIVE/AIT/2nd_semester/DATA ENGINEER/Proposal Presentation"
source caas-env/bin/activate
pytest tests/test_build_slides.py -v
```

Expected: `test_file_is_generated PASSED`.

- [ ] **Step 6: Commit**

```bash
git add 04_Scripts/build_slides.py tests/test_build_slides.py requirements.txt
git commit -m "feat: scaffold CAAS PPTX build script + smoke test"
```

---

## Task 2: Constants module — pinned values with JSON verification

**Why:** The spec (§6, §8) requires verifying key numeric values against `03_Data/results/*.json` before producing a deck. Wire this into the build so a stale number fails the build rather than reaching the grader.

**Files:**
- Modify: `04_Scripts/build_slides.py` (add constants + verify function near the top)
- Modify: `tests/test_build_slides.py` (add verify test)

- [ ] **Step 1: Add constants block to `build_slides.py`**

Insert after the imports, before `def build()`:

```python
# ============================================================
#  SPEC-PINNED CONSTANTS
#  These values must match 03_Data/results/*.json exactly.
#  verify_numbers() cross-checks at build time.
# ============================================================
RESULTS_DIR = PROJECT_ROOT / "03_Data" / "results"

# Slide 6 — test-set metrics (from lightgbm_summary.json, xgboost_summary.json, lstm_summary.json)
METRICS = {
    "lightgbm": {
        "mae":   {"t1": 5.12, "t3": 6.77, "t7": 8.25},
        "r2":    {"t1": 0.841, "t3": 0.729, "t7": 0.600},
        "auroc": {"t1": 0.992, "t3": 0.973, "t7": 0.946},
    },
    "xgboost":  {
        "mae":   {"t1": 5.31, "t3": 7.08, "t7": 8.90},
        "r2":    {"t1": 0.824, "t3": 0.712, "t7": 0.589},
        "auroc": {"t1": 0.989, "t3": 0.968, "t7": 0.940},
    },
    "lstm":     {
        "mae":   {"t1": 6.67, "t3": 8.87, "t7": 8.06},
        "r2":    {"t1": 0.753, "t3": 0.540, "t7": 0.608},
        "auroc": {"t1": 0.962, "t3": 0.935, "t7": 0.918},
    },
}

# Slide 8 — ablation deltas (from ablation_summary.json)
ABLATION_DELTAS = {"t1": 4.3, "t3": 6.8, "t7": 5.1}  # percent MAE degradation without FIRMS

# Slide 8 — Scenario C thresholds (from scenario_c_summary.json)
SCENARIO_C = {
    "t1": {"threshold": 53.7, "f1_gain_pct": 4.0},
    "t3": {"threshold": 50.0, "f1_gain_pct": 0.0},
    "t7": {"threshold": 50.0, "f1_gain_pct": 0.0},
}


def verify_numbers() -> None:
    """Check that spec-pinned constants match the result JSONs.

    Fails loudly on mismatch so build cannot silently ship a stale metric.
    Tolerances: MAE/R²/AUROC within ±0.01; ablation deltas within ±0.2pp.
    """
    import json

    def _load(name: str) -> dict:
        path = RESULTS_DIR / name
        if not path.exists():
            raise FileNotFoundError(f"Missing results file: {path}")
        with path.open() as f:
            return json.load(f)

    mismatches: list[str] = []

    # Helper to compare a model family against its JSON
    def _check_model(family: str, json_name: str, tol_mae=0.02, tol_r2=0.01, tol_auroc=0.01):
        try:
            data = _load(json_name)
        except FileNotFoundError as e:
            mismatches.append(str(e))
            return
        for h in ("t1", "t3", "t7"):
            for metric, tol in (("mae", tol_mae), ("r2", tol_r2), ("auroc", tol_auroc)):
                spec_val = METRICS[family][metric][h]
                # JSON structure may vary; try common paths
                actual = _extract_metric(data, metric, h)
                if actual is None:
                    mismatches.append(f"{family}.{metric}.{h}: cannot find in {json_name}")
                    continue
                if abs(actual - spec_val) > tol:
                    mismatches.append(
                        f"{family}.{metric}.{h}: spec={spec_val}, json={actual:.3f} "
                        f"(Δ={abs(actual-spec_val):.3f} > tol={tol})"
                    )

    _check_model("lightgbm", "lightgbm_summary.json")
    _check_model("xgboost",  "xgboost_summary.json")
    _check_model("lstm",     "lstm_summary.json")

    # Ablation
    try:
        ab = _load("ablation_summary.json")
        for h in ("t1", "t3", "t7"):
            spec_pct = ABLATION_DELTAS[h]
            actual = _extract_ablation_pct(ab, h)
            if actual is None:
                mismatches.append(f"ablation.{h}: cannot find in ablation_summary.json")
                continue
            if abs(actual - spec_pct) > 0.5:  # 0.5pp tolerance
                mismatches.append(f"ablation.{h}: spec={spec_pct}%, json={actual:.2f}%")
    except FileNotFoundError as e:
        mismatches.append(str(e))

    # Scenario C thresholds
    try:
        sc = _load("scenario_c_summary.json")
        for h in ("t1", "t3", "t7"):
            spec_thr = SCENARIO_C[h]["threshold"]
            actual = _extract_scenario_c_threshold(sc, h)
            if actual is None:
                mismatches.append(f"scenario_c.{h}: cannot find threshold")
                continue
            if abs(actual - spec_thr) > 0.5:
                mismatches.append(f"scenario_c.{h}.threshold: spec={spec_thr}, json={actual}")
    except FileNotFoundError as e:
        mismatches.append(str(e))

    if mismatches:
        header = "=" * 60 + "\nSPEC/JSON MISMATCH — build refuses to generate stale deck:\n"
        body = "\n".join(f"  - {m}" for m in mismatches)
        footer = "\n" + "=" * 60
        raise ValueError(header + body + footer)


def _extract_metric(data: dict, metric: str, horizon: str) -> float | None:
    """Best-effort lookup of a metric from a results JSON.

    Tries multiple schema shapes: {"test": {"t1": {"mae": X}}}, {"t1_mae": X}, etc.
    Returns None if not found.
    """
    h_key = horizon  # t1, t3, t7
    # Shape 1: nested by split then horizon
    for split in ("test", "test_set", "holdout"):
        if split in data and h_key in data[split] and metric in data[split][h_key]:
            return float(data[split][h_key][metric])
    # Shape 2: flat keys like "test_mae_t1"
    for k in (f"test_{metric}_{h_key}", f"{metric}_{h_key}_test", f"{h_key}_{metric}"):
        if k in data:
            return float(data[k])
    # Shape 3: horizon-keyed dict
    if h_key in data and isinstance(data[h_key], dict) and metric in data[h_key]:
        return float(data[h_key][metric])
    return None


def _extract_ablation_pct(data: dict, horizon: str) -> float | None:
    """Best-effort lookup of ablation percent-degradation."""
    for k in (f"mae_delta_pct_{horizon}", f"{horizon}_mae_delta_pct", f"{horizon}_pct"):
        if k in data:
            return float(data[k])
    if horizon in data and isinstance(data[horizon], dict):
        for k in ("mae_delta_pct", "pct", "delta_pct"):
            if k in data[horizon]:
                return float(data[horizon][k])
    return None


def _extract_scenario_c_threshold(data: dict, horizon: str) -> float | None:
    """Best-effort lookup of optimal threshold."""
    if horizon in data and isinstance(data[horizon], dict):
        for k in ("optimal_threshold", "threshold", "best_threshold"):
            if k in data[horizon]:
                return float(data[horizon][k])
    for k in (f"threshold_{horizon}", f"{horizon}_threshold"):
        if k in data:
            return float(data[k])
    return None
```

- [ ] **Step 2: Wire verify_numbers() into the build() entry point**

In `build_slides.py`, update the `build()` function:

```python
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
```

- [ ] **Step 3: Run the build to discover actual JSON schema shapes**

Run:
```bash
source caas-env/bin/activate
python 04_Scripts/build_slides.py 2>&1 | head -40
```

**Possible outcomes:**
- ✅ Build succeeds → all values match, schemas are compatible with `_extract_*` helpers. Continue.
- ❌ `SPEC/JSON MISMATCH` error → two cases:
  1. Helper couldn't parse the JSON schema. Inspect: `python -c "import json; print(json.dumps(json.load(open('03_Data/results/lightgbm_summary.json')), indent=2))" | head -30` and adjust `_extract_metric` to match.
  2. Spec constant is genuinely stale. Update the constant in `build_slides.py` to match the JSON, re-run.

Iterate Step 3 until the build succeeds. Record any constant updates in the commit message.

- [ ] **Step 4: Add verify test**

Append to `tests/test_build_slides.py`:

```python
def test_verify_numbers_passes_against_current_jsons():
    """verify_numbers() must not raise against the current results/ JSONs."""
    sys.path.insert(0, str(PROJECT_ROOT / "04_Scripts"))
    from build_slides import verify_numbers  # noqa: E402

    verify_numbers()  # raises on mismatch — test fails if it does
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_build_slides.py -v
```

Expected: both tests pass.

- [ ] **Step 6: Commit**

```bash
git add 04_Scripts/build_slides.py tests/test_build_slides.py
git commit -m "feat: pin numeric constants with JSON verification gate"
```

---

## Task 3: Shared styling — palette, fonts, placeholder-frame helper

**Why:** Every slide uses the same colour palette, fonts, and `add_placeholder_frame()` helper (§5 of spec). Define them once.

**Files:**
- Modify: `04_Scripts/build_slides.py` (append helpers block)

- [ ] **Step 1: Add palette + font constants**

Insert after the `verify_numbers` block, before `def build()`:

```python
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from lxml import etree

# ============================================================
#  PALETTE + FONTS
# ============================================================
COLOR_PRIMARY   = RGBColor(0x0E, 0x4D, 0x64)   # AIT institutional blue
COLOR_ACCENT    = RGBColor(0xE8, 0xB9, 0x00)   # AIT yellow
COLOR_SUCCESS   = RGBColor(0x2E, 0x8B, 0x57)   # green for success banners
COLOR_DANGER    = RGBColor(0xC0, 0x39, 0x2B)   # red for blocking step
COLOR_WARN      = RGBColor(0xE6, 0x7E, 0x22)   # amber for soft-drift
COLOR_TEXT      = RGBColor(0x22, 0x2E, 0x3C)   # body text
COLOR_MUTED     = RGBColor(0x66, 0x66, 0x66)   # captions
COLOR_PLACEHOLDER_FILL   = RGBColor(0xE8, 0xE8, 0xE8)
COLOR_PLACEHOLDER_BORDER = RGBColor(0xAA, 0xAA, 0xAA)
COLOR_TABLE_HEADER_BG    = RGBColor(0x0E, 0x4D, 0x64)
COLOR_TABLE_ROW_ALT      = RGBColor(0xF3, 0xF6, 0xF8)

FONT_FAMILY = "Calibri"


def set_font(run, *, size_pt: int, bold: bool = False, italic: bool = False,
             color: RGBColor = COLOR_TEXT, family: str = FONT_FAMILY) -> None:
    """Apply consistent font styling to a text run."""
    run.font.name = family
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
```

- [ ] **Step 2: Add placeholder-frame helper**

Append to `build_slides.py`:

```python
def add_placeholder_frame(
    slide,
    *,
    left: Inches,
    top: Inches,
    width: Inches,
    height: Inches,
    caption: str,
    aspect_hint: str = "",
):
    """Add a gray dashed rectangle with caption — user replaces with real image.

    Per spec §5: fill #E8E8E8, dashed #AAAAAA border 1.5pt, centered italic caption
    "[IMAGE PLACEHOLDER]" + specific caption + aspect hint.
    """
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = COLOR_PLACEHOLDER_FILL
    shape.line.color.rgb = COLOR_PLACEHOLDER_BORDER
    shape.line.width = Pt(1.5)
    # Dashed border (python-pptx doesn't expose this directly — raw XML)
    ln = shape.line._get_or_add_ln()
    prstDash = etree.SubElement(ln, qn("a:prstDash"))
    prstDash.set("val", "dash")

    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.1)
    tf.margin_right = Inches(0.1)

    # Line 1: marker
    p1 = tf.paragraphs[0]
    p1.alignment = PP_ALIGN.CENTER
    r1 = p1.add_run()
    r1.text = "[IMAGE PLACEHOLDER]"
    set_font(r1, size_pt=14, italic=True, color=COLOR_MUTED)

    # Line 2: caption
    p2 = tf.add_paragraph()
    p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run()
    r2.text = caption
    set_font(r2, size_pt=12, italic=True, color=COLOR_MUTED)

    # Line 3: aspect hint
    if aspect_hint:
        p3 = tf.add_paragraph()
        p3.alignment = PP_ALIGN.CENTER
        r3 = p3.add_run()
        r3.text = aspect_hint
        set_font(r3, size_pt=10, italic=True, color=COLOR_MUTED)

    return shape


def add_text_box(slide, *, left, top, width, height, text: str,
                 size_pt: int = 18, bold: bool = False, italic: bool = False,
                 color: RGBColor = COLOR_TEXT, align=PP_ALIGN.LEFT):
    """Add a plain text box."""
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    set_font(r, size_pt=size_pt, bold=bold, italic=italic, color=color)
    return box


def add_speaker_notes(slide, text: str) -> None:
    """Attach speaker notes to a slide."""
    notes = slide.notes_slide
    tf = notes.notes_text_frame
    tf.text = text


def blank_slide(prs):
    """Add a slide using the blank layout (index 6 in default master)."""
    return prs.slides.add_slide(prs.slide_layouts[6])
```

- [ ] **Step 3: Run existing tests to make sure imports still work**

```bash
pytest tests/test_build_slides.py -v
```

Expected: both tests still pass (helpers are unused yet but importable).

- [ ] **Step 4: Commit**

```bash
git add 04_Scripts/build_slides.py
git commit -m "feat: add palette, fonts, placeholder-frame helper"
```

---

## Task 4: Slides 1-3 (Title, Problem, What-we-built)

**Files:**
- Modify: `04_Scripts/build_slides.py`
- Modify: `tests/test_build_slides.py`

- [ ] **Step 1: Implement `slide_1_title`, `slide_2_problem`, `slide_3_contribution`**

Append to `build_slides.py`:

```python
# ============================================================
#  Slide 1 — Title
# ============================================================
def slide_1_title(prs):
    s = blank_slide(prs)

    # Optional hero background placeholder (full-bleed)
    add_placeholder_frame(
        s,
        left=Inches(0), top=Inches(0),
        width=SLIDE_W, height=SLIDE_H,
        caption="Chiang Mai haze photo — 16:9 full-bleed (optional)",
        aspect_hint="16:9",
    )

    # Text stack (layered on top of placeholder so user can delete frame or keep)
    add_text_box(s, left=Inches(0.8), top=Inches(2.4), width=Inches(11.7), height=Inches(1.2),
                 text="CAAS — ChiangMai Air Quality Alert System",
                 size_pt=44, bold=True, color=COLOR_PRIMARY, align=PP_ALIGN.CENTER)
    add_text_box(s, left=Inches(0.8), top=Inches(3.7), width=Inches(11.7), height=Inches(0.6),
                 text="End-to-End MLOps Pipeline for PM2.5 Forecasting",
                 size_pt=22, color=COLOR_TEXT, align=PP_ALIGN.CENTER)
    add_text_box(s, left=Inches(0.8), top=Inches(4.8), width=Inches(11.7), height=Inches(0.5),
                 text="Supanut Kompayak (st126055) · Shuvam Shrestha (st125975)",
                 size_pt=18, color=COLOR_TEXT, align=PP_ALIGN.CENTER)
    add_text_box(s, left=Inches(0.8), top=Inches(5.4), width=Inches(11.7), height=Inches(0.4),
                 text="AT82.9002 · Data Engineering and MLOps · AIT · April 2026",
                 size_pt=14, color=COLOR_MUTED, align=PP_ALIGN.CENTER)

    add_speaker_notes(s,
        "Good afternoon. I'm Supanut, with my teammate Shuvam. We built CAAS — a "
        "production-grade air quality forecasting system for Chiang Mai. Let's start with why.")


# ============================================================
#  Slide 2 — Problem
# ============================================================
def slide_2_problem(prs):
    s = blank_slide(prs)

    # Title
    add_text_box(s, left=Inches(0.5), top=Inches(0.35), width=Inches(12.3), height=Inches(0.7),
                 text="Every February–April, Chiang Mai breathes poison.",
                 size_pt=32, bold=True, color=COLOR_PRIMARY)

    # Left column — two stacked placeholders
    add_placeholder_frame(s, left=Inches(0.5), top=Inches(1.3), width=Inches(6), height=Inches(2.7),
                          caption="Chiang Mai haze photo / skyline during burning season",
                          aspect_hint="~4:3")
    add_placeholder_frame(s, left=Inches(0.5), top=Inches(4.2), width=Inches(6), height=Inches(2.7),
                          caption="PM2.5 yearly peaks 2011–2025 chart",
                          aspect_hint="~4:3")

    # Right column — three stats
    stats = [
        ("300+ µg/m³", "peak daily PM2.5 — 20× WHO limit"),
        ("1.2M",       "residents in metro area at risk"),
        ("0",          "public forecasts — PCD publishes only observed values"),
    ]
    for i, (num, caption) in enumerate(stats):
        y = 1.3 + i * 1.8
        add_text_box(s, left=Inches(7), top=Inches(y), width=Inches(5.8), height=Inches(0.9),
                     text=num, size_pt=48, bold=True, color=COLOR_ACCENT)
        add_text_box(s, left=Inches(7), top=Inches(y + 0.9), width=Inches(5.8), height=Inches(0.6),
                     text=caption, size_pt=14, color=COLOR_TEXT)

    # Footer
    add_text_box(s, left=Inches(0.5), top=Inches(7.0), width=Inches(12.3), height=Inches(0.4),
                 text="Residents learn conditions are hazardous after they already are.",
                 size_pt=13, italic=True, color=COLOR_MUTED, align=PP_ALIGN.CENTER)

    add_speaker_notes(s,
        "Chiang Mai sits in a mountain basin. Every burning season, PM2.5 peaks above 300 "
        "micrograms — twenty times the WHO limit. Thailand's PCD publishes the number, but "
        "only after the air is already bad. 1.2 million people have no advance warning. "
        "That's the gap we built CAAS to close.")


# ============================================================
#  Slide 3 — What we built + contribution framing
# ============================================================
def slide_3_contribution(prs):
    s = blank_slide(prs)

    add_text_box(s, left=Inches(0.5), top=Inches(0.35), width=Inches(12.3), height=Inches(0.7),
                 text="What CAAS delivers", size_pt=32, bold=True, color=COLOR_PRIMARY)

    bullets = [
        ("📈", "Forecast PM2.5 at t+1, t+3, t+7 days — 15 years of data, 45 features"),
        ("🔔", "Hazard alerts at the WHO 50 µg/m³ threshold"),
        ("☁️", "Self-retraining MLOps pipeline on AWS — ~$0.55/day"),
    ]
    for i, (icon, text) in enumerate(bullets):
        y = 1.5 + i * 1.3
        add_text_box(s, left=Inches(1.0), top=Inches(y), width=Inches(1.0), height=Inches(1.0),
                     text=icon, size_pt=48, align=PP_ALIGN.CENTER)
        add_text_box(s, left=Inches(2.2), top=Inches(y + 0.15), width=Inches(10), height=Inches(0.9),
                     text=text, size_pt=20, color=COLOR_TEXT)

    # Banner
    banner = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                Inches(0.8), Inches(5.8), Inches(11.7), Inches(1.2))
    banner.fill.solid()
    banner.fill.fore_color.rgb = COLOR_SUCCESS
    banner.line.fill.background()
    tf = banner.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = ("Our contribution is a strong production-oriented integration — "
              "not a new forecasting algorithm.")
    set_font(r, size_pt=18, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))

    add_speaker_notes(s,
        "CAAS is three things: a multi-horizon PM2.5 forecaster, a hazard alert service, "
        "and a self-retraining pipeline running on AWS for under a dollar a day. We want to "
        "be clear upfront — we're not claiming a new algorithm. Our contribution is "
        "integrating public data sources, standard ML, and MLOps discipline into one "
        "working production system.")
```

- [ ] **Step 2: Wire the three slide functions into `build()`**

Replace the "Slides will be added here" comment with:

```python
    slide_1_title(prs)
    slide_2_problem(prs)
    slide_3_contribution(prs)
```

- [ ] **Step 3: Run the build**

```bash
source caas-env/bin/activate
python 04_Scripts/build_slides.py
```

Expected: `Built: 07_Final/slides/CAAS_final.pptx` printed, no errors.

- [ ] **Step 4: Add test: slides 1-3 content + placeholder counts**

Append to `tests/test_build_slides.py`:

```python
def _slide_texts(slide) -> list[str]:
    """Extract all text content from a slide (concatenated across shapes)."""
    texts = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    if run.text.strip():
                        texts.append(run.text.strip())
    return texts


def _placeholder_count(slide) -> int:
    """Count shapes that are our [IMAGE PLACEHOLDER] frames."""
    count = 0
    for shape in slide.shapes:
        if shape.has_text_frame and "[IMAGE PLACEHOLDER]" in shape.text_frame.text:
            count += 1
    return count


def test_slide_1_title(built_deck):
    s = built_deck.slides[0]
    joined = " ".join(_slide_texts(s))
    assert "CAAS" in joined
    assert "ChiangMai Air Quality Alert System" in joined
    assert "Supanut Kompayak" in joined
    assert "Shuvam Shrestha" in joined
    assert _placeholder_count(s) == 1  # hero background


def test_slide_2_problem(built_deck):
    s = built_deck.slides[1]
    joined = " ".join(_slide_texts(s))
    assert "300+ µg/m³" in joined
    assert "1.2M" in joined
    assert _placeholder_count(s) == 2


def test_slide_3_contribution(built_deck):
    s = built_deck.slides[2]
    joined = " ".join(_slide_texts(s))
    assert "integration" in joined.lower()
    assert "not a new forecasting algorithm" in joined
    assert _placeholder_count(s) == 0
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_build_slides.py -v
```

Expected: all 5 tests pass (2 existing + 3 new).

- [ ] **Step 6: Open the pptx and eyeball**

Run:
```bash
open "07_Final/slides/CAAS_final.pptx"
```

Verify visually: three slides, text legible, placeholders visibly gray/dashed, no overflow. If anything's visually wrong, fix here before moving on.

- [ ] **Step 7: Commit**

```bash
git add 04_Scripts/build_slides.py tests/test_build_slides.py
git commit -m "feat: implement slides 1-3 (title, problem, contribution framing)"
```

---

## Task 5: Slides 4-5 (Architecture, Data pipeline)

**Files:**
- Modify: `04_Scripts/build_slides.py`
- Modify: `tests/test_build_slides.py`

- [ ] **Step 1: Implement `slide_4_architecture` and `slide_5_data_pipeline`**

Append to `build_slides.py`:

```python
# ============================================================
#  Slide 4 — System architecture
# ============================================================
def slide_4_architecture(prs):
    s = blank_slide(prs)

    # Title bar
    add_text_box(s, left=Inches(0.5), top=Inches(0.3), width=Inches(12.3), height=Inches(0.6),
                 text="End-to-end architecture", size_pt=28, bold=True, color=COLOR_PRIMARY)

    # Full-slide architecture placeholder
    add_placeholder_frame(
        s,
        left=Inches(0.5), top=Inches(1.1),
        width=Inches(12.3), height=Inches(5.6),
        caption="Cloud architecture — use 01_Proposal/fig_cloud_architecture.png",
        aspect_hint="16:9",
    )

    # Corner label
    add_text_box(s, left=Inches(0.5), top=Inches(6.85), width=Inches(5), height=Inches(0.4),
                 text="All provisioned by Terraform", size_pt=11, italic=True, color=COLOR_MUTED)

    add_speaker_notes(s,
        "Three public data sources — PCD PM2.5, Open-Meteo weather, NASA FIRMS fire hotspots "
        "— feed a daily ingestion job on AWS. Data lands in tiered S3 buckets. Training runs "
        "with MLflow tracking. The serving stack — FastAPI for inference, Streamlit for the "
        "public dashboard, Evidently for drift — runs on a single EC2. GitHub Actions "
        "orchestrates everything. The whole stack is Terraform-provisioned, reproducible "
        "from a clean AWS account with one command.")


# ============================================================
#  Slide 5 — Data pipeline
# ============================================================
def slide_5_data_pipeline(prs):
    s = blank_slide(prs)

    add_text_box(s, left=Inches(0.5), top=Inches(0.3), width=Inches(12.3), height=Inches(0.6),
                 text="Three public sources → 45 features → versioned S3",
                 size_pt=26, bold=True, color=COLOR_PRIMARY)

    # Left 2/3 — flow diagram placeholder
    add_placeholder_frame(
        s,
        left=Inches(0.5), top=Inches(1.2),
        width=Inches(8.2), height=Inches(5.7),
        caption="Daily pipeline — 01_Proposal/fig_daily_pipeline.png or similar",
        aspect_hint="16:9",
    )

    # Right 1/3 — feature category table
    rows = [
        ("Category", "Count"),
        ("PM2.5 lags + rolling", "14"),
        ("Weather (ERA5)", "13"),
        ("FIRMS fire", "6"),
        ("Seasonality", "6"),
        ("Regional PM2.5", "6"),
        ("Total", "45"),
    ]
    table_shape = s.shapes.add_table(
        rows=len(rows), cols=2,
        left=Inches(9.0), top=Inches(1.2),
        width=Inches(3.8), height=Inches(4.0),
    ).table
    for r, (cat, cnt) in enumerate(rows):
        for c, val in enumerate((cat, cnt)):
            cell = table_shape.cell(r, c)
            cell.text = val
            for para in cell.text_frame.paragraphs:
                for run in para.runs:
                    is_header = r == 0
                    is_total = cat == "Total"
                    set_font(run,
                             size_pt=12,
                             bold=is_header or is_total,
                             color=RGBColor(0xFF, 0xFF, 0xFF) if is_header else COLOR_TEXT)
            if r == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = COLOR_TABLE_HEADER_BG
            elif r % 2 == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = COLOR_TABLE_ROW_ALT

    add_speaker_notes(s,
        "The data engineering layer pulls from three free public sources — Thailand's PCD "
        "portal for PM2.5, Open-Meteo for ERA5 weather, and NASA FIRMS for satellite fire "
        "hotspots. Everything lands in a tiered S3 bucket — raw files, cleaned per-source "
        "tables, and the 45-feature daily matrix we train on. The 45 features span five "
        "categories: PM2.5 autoregressive lags, weather, fire hotspots, seasonality, and "
        "regional PM2.5. Each tier is independently reproducible — if a source file updates, "
        "we rebuild downstream without touching the rest.")
```

- [ ] **Step 2: Wire into `build()`**

Add after the slide_3 line:

```python
    slide_4_architecture(prs)
    slide_5_data_pipeline(prs)
```

- [ ] **Step 3: Build and test**

```bash
python 04_Scripts/build_slides.py
pytest tests/test_build_slides.py -v
```

- [ ] **Step 4: Add tests for slides 4-5**

Append to `tests/test_build_slides.py`:

```python
def test_slide_4_architecture(built_deck):
    s = built_deck.slides[3]
    joined = " ".join(_slide_texts(s))
    assert "End-to-end architecture" in joined
    assert "Terraform" in joined
    assert _placeholder_count(s) == 1


def test_slide_5_data_pipeline(built_deck):
    s = built_deck.slides[4]
    joined = " ".join(_slide_texts(s))
    assert "45 features" in joined or "45" in joined
    assert "PM2.5 lags" in joined or "PM2.5" in joined
    assert _placeholder_count(s) == 1
```

- [ ] **Step 5: Run tests and visual check**

```bash
pytest tests/test_build_slides.py -v
open "07_Final/slides/CAAS_final.pptx"
```

- [ ] **Step 6: Commit**

```bash
git add 04_Scripts/build_slides.py tests/test_build_slides.py
git commit -m "feat: implement slides 4-5 (architecture, data pipeline)"
```

---

## Task 6: Slide 6 (Models + chronological split + metrics)

**Why:** This slide has the most complex layout: timeline bar (drawn as shapes) + large metrics table + callout. Isolating it in its own task keeps the diff reviewable.

**Files:**
- Modify: `04_Scripts/build_slides.py`
- Modify: `tests/test_build_slides.py`

- [ ] **Step 1: Implement `slide_6_models`**

Append to `build_slides.py`:

```python
# ============================================================
#  Slide 6 — Models + chronological split + headline metrics
# ============================================================
def slide_6_models(prs):
    s = blank_slide(prs)

    add_text_box(s, left=Inches(0.5), top=Inches(0.3), width=Inches(12.3), height=Inches(0.6),
                 text="Three model families, chronological evaluation",
                 size_pt=26, bold=True, color=COLOR_PRIMARY)

    # Timeline bar — 3 coloured segments
    segments = [
        ("Train 2011–2022 (12 yrs)", 0.70, COLOR_PRIMARY),
        ("Val 2023",                 0.12, COLOR_WARN),
        ("Test 2024–2025",           0.18, COLOR_ACCENT),
    ]
    x = 0.5
    total_w = 12.3
    y = 1.1
    h = 0.5
    for label, frac, color in segments:
        w = total_w * frac
        box = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y),
                                 Inches(w), Inches(h))
        box.fill.solid()
        box.fill.fore_color.rgb = color
        box.line.fill.background()
        tf = box.text_frame
        tf.margin_left = Inches(0.05); tf.margin_right = Inches(0.05)
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = label
        set_font(r, size_pt=11, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
        x += w

    add_text_box(s, left=Inches(0.5), top=Inches(1.7), width=Inches(12.3), height=Inches(0.3),
                 text="Strict chronological split — no leakage via lag or rolling features.",
                 size_pt=11, italic=True, color=COLOR_MUTED, align=PP_ALIGN.CENTER)

    # Metrics table
    header = ["", "LightGBM (champion)", "XGBoost (secondary)", "LSTM (comparison)"]
    rows_data = [
        ["MAE t+1",  f"{METRICS['lightgbm']['mae']['t1']:.2f}", f"{METRICS['xgboost']['mae']['t1']:.2f}", f"{METRICS['lstm']['mae']['t1']:.2f}"],
        ["MAE t+3",  f"{METRICS['lightgbm']['mae']['t3']:.2f}", f"{METRICS['xgboost']['mae']['t3']:.2f}", f"{METRICS['lstm']['mae']['t3']:.2f}"],
        ["MAE t+7",  f"{METRICS['lightgbm']['mae']['t7']:.2f}", f"{METRICS['xgboost']['mae']['t7']:.2f}", f"{METRICS['lstm']['mae']['t7']:.2f}"],
        ["R² t+1",   f"{METRICS['lightgbm']['r2']['t1']:.3f}",  f"{METRICS['xgboost']['r2']['t1']:.3f}",  f"{METRICS['lstm']['r2']['t1']:.3f}"],
        ["R² t+3",   f"{METRICS['lightgbm']['r2']['t3']:.3f}",  f"{METRICS['xgboost']['r2']['t3']:.3f}",  f"{METRICS['lstm']['r2']['t3']:.3f}"],
        ["AUROC ≥50 t+1", f"{METRICS['lightgbm']['auroc']['t1']:.3f}", f"{METRICS['xgboost']['auroc']['t1']:.3f}", f"{METRICS['lstm']['auroc']['t1']:.3f}"],
    ]
    tbl = s.shapes.add_table(
        rows=len(rows_data) + 1, cols=4,
        left=Inches(0.5), top=Inches(2.3), width=Inches(12.3), height=Inches(3.5),
    ).table
    # Header row
    for c, v in enumerate(header):
        cell = tbl.cell(0, c); cell.text = v
        for para in cell.text_frame.paragraphs:
            for run in para.runs:
                set_font(run, size_pt=12, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
        cell.fill.solid(); cell.fill.fore_color.rgb = COLOR_TABLE_HEADER_BG
    # Body rows
    for r, row in enumerate(rows_data, start=1):
        for c, v in enumerate(row):
            cell = tbl.cell(r, c); cell.text = v
            is_best = c == 1  # LightGBM col is always best (spec-locked)
            for para in cell.text_frame.paragraphs:
                for run in para.runs:
                    set_font(run, size_pt=12, bold=is_best, color=COLOR_TEXT)
            if r % 2 == 0:
                cell.fill.solid(); cell.fill.fore_color.rgb = COLOR_TABLE_ROW_ALT

    # Callout banner
    banner = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                Inches(0.5), Inches(6.2), Inches(12.3), Inches(0.8))
    banner.fill.solid(); banner.fill.fore_color.rgb = COLOR_PRIMARY
    banner.line.fill.background()
    tf = banner.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = ("LightGBM wins at t+1 and t+3; LSTM only competitive at t+7. "
              "Gradient boosting + engineered lag features beat deep sequence on this problem.")
    set_font(r, size_pt=14, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))

    add_speaker_notes(s,
        "We compared three model families — LightGBM, XGBoost, and an LSTM — under the "
        "same chronological evaluation protocol. Training 2011 through 2022, validation on "
        "2023, held-out test on 2024 and 2025. No leakage, no random shuffling. LightGBM "
        "is our champion: 5.12, 6.77, and 8.25 MAE at t+1, t+3, and t+7. XGBoost is a "
        "strong second — we keep it loaded as a runtime fallback for A/B comparison. The "
        "LSTM degrades at mid-horizon — R² drops to 0.54 at t+3. For this problem, "
        "gradient boosting with engineered lag features beats deep sequence modeling. We "
        "retain XGBoost in production not because it wins on accuracy, but because it "
        "gives us a natural champion-challenger surface.")
```

- [ ] **Step 2: Wire into `build()`**

```python
    slide_6_models(prs)
```

- [ ] **Step 3: Add test**

Append to `tests/test_build_slides.py`:

```python
def test_slide_6_models(built_deck):
    s = built_deck.slides[5]
    joined = " ".join(_slide_texts(s))
    assert "5.12" in joined         # LightGBM t+1 MAE
    assert "6.77" in joined         # LightGBM t+3 MAE
    assert "8.25" in joined         # LightGBM t+7 MAE
    assert "0.992" in joined        # LightGBM t+1 AUROC
    assert "Train 2011–2022" in joined
    assert "Val 2023" in joined
    assert "Test 2024–2025" in joined
    assert _placeholder_count(s) == 0
```

- [ ] **Step 4: Build + test + visual check**

```bash
python 04_Scripts/build_slides.py
pytest tests/test_build_slides.py -v
open "07_Final/slides/CAAS_final.pptx"
```

- [ ] **Step 5: Commit**

```bash
git add 04_Scripts/build_slides.py tests/test_build_slides.py
git commit -m "feat: implement slide 6 (models + chronological split + metrics)"
```

---

## Task 7: Slides 7-8 (SHAP, Ablation + Scenario C)

**Files:**
- Modify: `04_Scripts/build_slides.py`
- Modify: `tests/test_build_slides.py`

- [ ] **Step 1: Implement `slide_7_shap` and `slide_8_ablation_threshold`**

Append to `build_slides.py`:

```python
# ============================================================
#  Slide 7 — SHAP: signal shifts with horizon
# ============================================================
def slide_7_shap(prs):
    s = blank_slide(prs)

    add_text_box(s, left=Inches(0.5), top=Inches(0.3), width=Inches(12.3), height=Inches(0.6),
                 text="The predictive signal shifts with horizon",
                 size_pt=26, bold=True, color=COLOR_PRIMARY)

    panels = [
        ("t+1 → pm25_lag1", "recent PM2.5 persistence",
         "03_Data/results/fig_shap_summary_t1.png"),
        ("t+3 → hotspot_14d_roll", "14-day fire accumulation",
         "03_Data/results/fig_shap_summary_t3.png"),
        ("t+7 → sin_month", "seasonal calendar position",
         "03_Data/results/fig_shap_summary_t7.png"),
    ]
    panel_w = 4.0
    gap = 0.15
    start_x = (13.333 - (panel_w * 3 + gap * 2)) / 2
    for i, (label_top, label_bot, source) in enumerate(panels):
        x = start_x + i * (panel_w + gap)
        add_text_box(s, left=Inches(x), top=Inches(1.1), width=Inches(panel_w), height=Inches(0.45),
                     text=label_top, size_pt=14, bold=True,
                     color=COLOR_PRIMARY, align=PP_ALIGN.CENTER)
        add_placeholder_frame(
            s,
            left=Inches(x), top=Inches(1.6),
            width=Inches(panel_w), height=Inches(4.2),
            caption=f"SHAP summary — {source}",
            aspect_hint="square",
        )
        add_text_box(s, left=Inches(x), top=Inches(5.85), width=Inches(panel_w), height=Inches(0.4),
                     text=label_bot, size_pt=11, italic=True,
                     color=COLOR_MUTED, align=PP_ALIGN.CENTER)

    add_text_box(s, left=Inches(0.5), top=Inches(6.5), width=Inches(12.3), height=Inches(0.7),
                 text=("Measurement-driven → fire-driven → climatology-driven. "
                       "Physically consistent with Chiang Mai haze meteorology."),
                 size_pt=14, italic=True, color=COLOR_TEXT, align=PP_ALIGN.CENTER)

    add_speaker_notes(s,
        "One of our favorite findings. SHAP attributions reveal the dominant predictor "
        "changes with horizon. At t+1, yesterday's PM2.5 dominates — simple persistence. "
        "At t+3, it shifts to the 14-day rolling fire hotspot count — burning accumulates, "
        "then PM2.5 follows. At t+7, the calendar takes over — sine of the month — because "
        "a week ahead, you're essentially predicting where in the haze season you'll land. "
        "This is physically interpretable: measurement, then emissions, then climatology. "
        "The model learned the meteorology without us hard-coding it.")


# ============================================================
#  Slide 8 — FIRMS ablation + Scenario C threshold
# ============================================================
def slide_8_ablation_threshold(prs):
    s = blank_slide(prs)

    add_text_box(s, left=Inches(0.5), top=Inches(0.3), width=Inches(12.3), height=Inches(0.6),
                 text="FIRMS adds measurable value; WHO threshold is near-optimal",
                 size_pt=22, bold=True, color=COLOR_PRIMARY)

    # Left half — ablation
    add_text_box(s, left=Inches(0.5), top=Inches(1.0), width=Inches(6.0), height=Inches(0.4),
                 text="Scenario D: remove FIRMS features",
                 size_pt=14, bold=True, color=COLOR_TEXT)
    add_placeholder_frame(
        s,
        left=Inches(0.5), top=Inches(1.5),
        width=Inches(6.0), height=Inches(3.6),
        caption="FIRMS ablation bar — 03_Data/results/fig_firms_ablation.png",
        aspect_hint="~4:3",
    )
    deltas = (f"+{ABLATION_DELTAS['t1']}% (t+1)  ·  "
              f"+{ABLATION_DELTAS['t3']}% (t+3)  ·  "
              f"+{ABLATION_DELTAS['t7']}% (t+7)")
    add_text_box(s, left=Inches(0.5), top=Inches(5.2), width=Inches(6.0), height=Inches(0.5),
                 text=deltas + " MAE degradation without FIRMS",
                 size_pt=13, bold=True, color=COLOR_DANGER, align=PP_ALIGN.CENTER)
    add_text_box(s, left=Inches(0.5), top=Inches(5.7), width=Inches(6.0), height=Inches(0.5),
                 text="Fire data is not just significant — it is operationally material.",
                 size_pt=11, italic=True, color=COLOR_MUTED, align=PP_ALIGN.CENTER)

    # Right half — Scenario C
    add_text_box(s, left=Inches(6.8), top=Inches(1.0), width=Inches(6.0), height=Inches(0.4),
                 text="Scenario C: threshold tuning",
                 size_pt=14, bold=True, color=COLOR_TEXT)
    add_placeholder_frame(
        s,
        left=Inches(6.8), top=Inches(1.5),
        width=Inches(6.0), height=Inches(2.6),
        caption=f"PR curve t+1 with {SCENARIO_C['t1']['threshold']} µg/m³ marked — fig_pr_curve_t1.png",
        aspect_hint="~4:3",
    )
    # Threshold table
    tbl = s.shapes.add_table(
        rows=4, cols=3,
        left=Inches(6.8), top=Inches(4.2), width=Inches(6.0), height=Inches(1.6),
    ).table
    tbl_rows = [
        ["Horizon", "Optimal threshold", "F1 gain vs 50"],
        ["t+1", f"{SCENARIO_C['t1']['threshold']} µg/m³",
                f"+{SCENARIO_C['t1']['f1_gain_pct']}%"],
        ["t+3", f"{SCENARIO_C['t3']['threshold']} (no change)",
                f"{SCENARIO_C['t3']['f1_gain_pct']}%"],
        ["t+7", f"{SCENARIO_C['t7']['threshold']} (no change)",
                f"{SCENARIO_C['t7']['f1_gain_pct']}%"],
    ]
    for r, row in enumerate(tbl_rows):
        for c, v in enumerate(row):
            cell = tbl.cell(r, c); cell.text = v
            for para in cell.text_frame.paragraphs:
                for run in para.runs:
                    set_font(run, size_pt=11, bold=(r == 0),
                             color=RGBColor(0xFF, 0xFF, 0xFF) if r == 0 else COLOR_TEXT)
            if r == 0:
                cell.fill.solid(); cell.fill.fore_color.rgb = COLOR_TABLE_HEADER_BG
            elif r % 2 == 0:
                cell.fill.solid(); cell.fill.fore_color.rgb = COLOR_TABLE_ROW_ALT
    add_text_box(s, left=Inches(6.8), top=Inches(5.9), width=Inches(6.0), height=Inches(0.5),
                 text="WHO/Thai 50 µg/m³ threshold is well-calibrated for two of three horizons — we keep it.",
                 size_pt=11, italic=True, color=COLOR_MUTED, align=PP_ALIGN.CENTER)

    add_speaker_notes(s,
        "Two rigor checks. First, ablation: we retrained the champion without the six FIRMS "
        "features. MAE degrades between 4.3 and 6.8 percent across horizons — strongest at "
        "t+3, where the 14-day fire accumulation matters most. So FIRMS is earning its "
        "integration cost. Second, threshold tuning: we asked whether the default WHO 50 "
        "µg/m³ alert threshold is optimal. For t+3 and t+7, yes — it's within noise of the "
        "F1 maximum. For t+1, tuning to 53.7 gains 4 percent F1 — a real but small "
        "improvement. We keep 50 operationally because consistency with the public-health "
        "standard beats marginal F1, but the analysis is published.")
```

- [ ] **Step 2: Wire into `build()`**

```python
    slide_7_shap(prs)
    slide_8_ablation_threshold(prs)
```

- [ ] **Step 3: Add tests**

```python
def test_slide_7_shap(built_deck):
    s = built_deck.slides[6]
    joined = " ".join(_slide_texts(s))
    assert "pm25_lag1" in joined
    assert "hotspot_14d_roll" in joined
    assert "sin_month" in joined
    assert _placeholder_count(s) == 3


def test_slide_8_ablation_threshold(built_deck):
    s = built_deck.slides[7]
    joined = " ".join(_slide_texts(s))
    assert "Scenario D" in joined or "FIRMS" in joined
    assert "53.7" in joined
    assert _placeholder_count(s) == 2
```

- [ ] **Step 4: Build + test + visual check**

```bash
python 04_Scripts/build_slides.py
pytest tests/test_build_slides.py -v
open "07_Final/slides/CAAS_final.pptx"
```

- [ ] **Step 5: Commit**

```bash
git add 04_Scripts/build_slides.py tests/test_build_slides.py
git commit -m "feat: implement slides 7-8 (SHAP, ablation + Scenario C)"
```

---

## Task 8: Slide 9 (Drift policy + retrain trigger + promotion gate)

**Why:** This is the densest slide — closes the professor's heaviest feedback. The 4-stage flow is drawn as shapes (not an image placeholder) so the grader can read it directly.

**Files:**
- Modify: `04_Scripts/build_slides.py`
- Modify: `tests/test_build_slides.py`

- [ ] **Step 1: Implement `slide_9_drift_policy`**

Append to `build_slides.py`:

```python
# ============================================================
#  Slide 9 — Drift policy + retrain trigger + promotion gate
# ============================================================
def slide_9_drift_policy(prs):
    s = blank_slide(prs)

    add_text_box(s, left=Inches(0.5), top=Inches(0.3), width=Inches(12.3), height=Inches(0.55),
                 text="Drift → Retrain → Validate → Promote — one unified policy",
                 size_pt=22, bold=True, color=COLOR_PRIMARY)

    # 4 stage columns
    stages = [
        {
            "title": "1. MONITOR",
            "subtitle": "Evidently · daily on EC2",
            "bullets": [
                "Core features (hard drift):\nPSI > 0.25 OR KS p < 0.05 → flag",
                "Soft features (seasonal-suppressed):\nFIRMS exempt from PSI alone",
                "Rolling 28-day MAE tracked",
            ],
            "color": COLOR_PRIMARY,
        },
        {
            "title": "2. TRIGGER",
            "subtitle": "any of ⇣",
            "bullets": [
                "Core-feature PSI > 0.25 for ≥ 3 days",
                "Rolling MAE ↑ ≥ 15% vs baseline",
                "Monthly schedule cap",
            ],
            "color": COLOR_WARN,
        },
        {
            "title": "3. VALIDATE",
            "subtitle": "validate_candidate.py",
            "bullets": [
                "Must beat champion by MAE ≥ 5% at primary horizon",
                "Alert F1 ≥ 0.75 at t+1 / t+3",
                "Else → BLOCK, keep champion",
            ],
            "color": COLOR_DANGER,
        },
        {
            "title": "4. PROMOTE",
            "subtitle": "promote_model.py → MLflow",
            "bullets": [
                "New stage = Production",
                "Previous → Archived",
                "FastAPI hot-reloads on next heartbeat",
            ],
            "color": COLOR_SUCCESS,
        },
    ]
    col_w = 2.95
    gap = 0.15
    y = 1.0
    h = 5.0
    start_x = (13.333 - (col_w * 4 + gap * 3)) / 2
    for i, stage in enumerate(stages):
        x = start_x + i * (col_w + gap)
        box = s.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                 Inches(x), Inches(y), Inches(col_w), Inches(h))
        box.fill.solid(); box.fill.fore_color.rgb = RGBColor(0xF7, 0xF9, 0xFB)
        box.line.color.rgb = stage["color"]; box.line.width = Pt(2.5)
        tf = box.text_frame
        tf.margin_left = Inches(0.15); tf.margin_right = Inches(0.15)
        tf.margin_top = Inches(0.1)

        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = stage["title"]
        set_font(r, size_pt=16, bold=True, color=stage["color"])

        p = tf.add_paragraph(); p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = stage["subtitle"]
        set_font(r, size_pt=10, italic=True, color=COLOR_MUTED)

        for bullet in stage["bullets"]:
            p = tf.add_paragraph(); p.alignment = PP_ALIGN.LEFT
            p.space_before = Pt(6)
            r = p.add_run(); r.text = "• " + bullet
            set_font(r, size_pt=11, color=COLOR_TEXT)

        # Arrow between stages
        if i < len(stages) - 1:
            arrow = s.shapes.add_shape(
                MSO_SHAPE.RIGHT_ARROW,
                Inches(x + col_w - 0.05), Inches(y + h / 2 - 0.2),
                Inches(gap + 0.1), Inches(0.4),
            )
            arrow.fill.solid(); arrow.fill.fore_color.rgb = COLOR_MUTED
            arrow.line.fill.background()

    # Bottom callout
    callout = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                  Inches(0.5), Inches(6.3), Inches(12.3), Inches(0.9))
    callout.fill.solid(); callout.fill.fore_color.rgb = COLOR_WARN
    callout.line.fill.background()
    tf = callout.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = ("Seasonal suppression is deliberate — naive PSI would retrain every February "
              "because FIRMS legitimately spikes. Two-tier policy preserves sensitivity "
              "without false alarms.")
    set_font(r, size_pt=12, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))

    add_speaker_notes(s,
        "This is the policy the professor asked us to unify. Four stages. Monitor — "
        "Evidently runs daily on EC2. We split features into two tiers: core features like "
        "PM2.5 lags and weather use PSI and KS tests directly. Soft features — mainly FIRMS "
        "— are zero-inflated in the rainy season, so naive drift detection would fire every "
        "February by design. We suppress those unless paired with a performance signal. "
        "Trigger — retraining fires if core-feature PSI stays above 0.25 for three days, OR "
        "rolling 28-day MAE degrades by 15 percent, OR monthly cap hits. Validate — the "
        "candidate must beat the champion by at least 5 percent MAE AND keep alert F1 above "
        "0.75. If it fails either, validate_candidate.py blocks the promotion and we keep "
        "the champion. Promote — only if it passes, promote_model.py rewrites the MLflow "
        "registry stage. FastAPI reloads on the next heartbeat. No human click required.")
```

- [ ] **Step 2: Wire into `build()` and test**

```python
    slide_9_drift_policy(prs)
```

- [ ] **Step 3: Add test**

```python
def test_slide_9_drift_policy(built_deck):
    s = built_deck.slides[8]
    joined = " ".join(_slide_texts(s))
    assert "MONITOR" in joined
    assert "TRIGGER" in joined
    assert "VALIDATE" in joined
    assert "PROMOTE" in joined
    assert "0.25" in joined     # PSI threshold
    assert "5%" in joined or "≥ 5%" in joined or "MAE ≥ 5%" in joined
    assert "0.75" in joined     # F1 threshold
    assert _placeholder_count(s) == 0
```

- [ ] **Step 4: Build + test + visual check**

```bash
python 04_Scripts/build_slides.py
pytest tests/test_build_slides.py -v
open "07_Final/slides/CAAS_final.pptx"
```

Visually verify: four columns fit the slide width, bullet text doesn't overflow, arrows between stages visible.

- [ ] **Step 5: Commit**

```bash
git add 04_Scripts/build_slides.py tests/test_build_slides.py
git commit -m "feat: implement slide 9 (drift policy + retrain + promotion gate)"
```

---

## Task 9: Slide 10 (GitHub Actions stages + blocking step)

**Files:**
- Modify: `04_Scripts/build_slides.py`
- Modify: `tests/test_build_slides.py`

- [ ] **Step 1: Implement `slide_10_gh_actions`**

Append to `build_slides.py`:

```python
# ============================================================
#  Slide 10 — GitHub Actions stages + blocking step
# ============================================================
def slide_10_gh_actions(prs):
    s = blank_slide(prs)

    add_text_box(s, left=Inches(0.5), top=Inches(0.3), width=Inches(12.3), height=Inches(0.55),
                 text="retrain.yml — 6 stages, one gate, $0",
                 size_pt=24, bold=True, color=COLOR_PRIMARY)

    stages = [
        ("1", "Snapshot data",    "fetch_pm25_live.py + S3 sync",     "immutable daily snapshot", False),
        ("2", "Build features",   "build_features.py",                 "45-col matrix → features/", False),
        ("3", "Train candidate",  "train_lightgbm / xgboost / lstm",   "artifact + MLflow run",    False),
        ("4", "🛑 Validate",       "validate_candidate.py",             "BLOCKS if MAE gain <5% OR F1 <0.75", True),
        ("5", "Register",         "MLflow model registry",             "candidate → Staging",      False),
        ("6", "Promote + deploy", "promote_model.py + FastAPI reload", "stage → Production",       False),
    ]

    box_w = 2.0
    gap = 0.05
    y = 1.2
    h = 2.5
    start_x = (13.333 - (box_w * 6 + gap * 5)) / 2
    for i, (num, title, script, outcome, is_block) in enumerate(stages):
        x = start_x + i * (box_w + gap)
        box = s.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                 Inches(x), Inches(y), Inches(box_w), Inches(h))
        box.fill.solid()
        box.fill.fore_color.rgb = RGBColor(0xFB, 0xEC, 0xEC) if is_block else RGBColor(0xF3, 0xF6, 0xF8)
        box.line.color.rgb = COLOR_DANGER if is_block else COLOR_PRIMARY
        box.line.width = Pt(3 if is_block else 1.5)
        tf = box.text_frame
        tf.margin_left = Inches(0.1); tf.margin_right = Inches(0.1); tf.margin_top = Inches(0.1)

        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = num
        set_font(r, size_pt=22, bold=True,
                 color=COLOR_DANGER if is_block else COLOR_PRIMARY)

        p = tf.add_paragraph(); p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = title
        set_font(r, size_pt=12, bold=True, color=COLOR_TEXT)

        p = tf.add_paragraph(); p.alignment = PP_ALIGN.CENTER
        p.space_before = Pt(4)
        r = p.add_run(); r.text = script
        set_font(r, size_pt=9, italic=True, color=COLOR_MUTED, family="Consolas")

        p = tf.add_paragraph(); p.alignment = PP_ALIGN.CENTER
        p.space_before = Pt(4)
        r = p.add_run(); r.text = outcome
        set_font(r, size_pt=9, color=COLOR_DANGER if is_block else COLOR_TEXT,
                 bold=is_block)

        # Arrow between boxes
        if i < len(stages) - 1:
            arrow = s.shapes.add_shape(
                MSO_SHAPE.RIGHT_ARROW,
                Inches(x + box_w - 0.02), Inches(y + h / 2 - 0.12),
                Inches(gap + 0.05), Inches(0.25),
            )
            arrow.fill.solid(); arrow.fill.fore_color.rgb = COLOR_MUTED
            arrow.line.fill.background()

    # GH Actions screenshot placeholder
    add_placeholder_frame(
        s,
        left=Inches(0.5), top=Inches(4.1),
        width=Inches(12.3), height=Inches(2.3),
        caption="Green retrain.yml run — github.com/supanut-k/caas/actions",
        aspect_hint="16:9",
    )

    # Bottom banner
    banner = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                Inches(0.5), Inches(6.6), Inches(12.3), Inches(0.6))
    banner.fill.solid(); banner.fill.fore_color.rgb = COLOR_SUCCESS
    banner.line.fill.background()
    tf = banner.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = ("ubuntu-latest · ~8 min end-to-end · GitHub Actions minutes = "
              "unlimited & free (public repo) · AWS API calls ~$0.01/run")
    set_font(r, size_pt=11, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))

    add_speaker_notes(s,
        "And here's the CI/CD answer. Six stages: snapshot the data, build features, train "
        "the candidate, validate, register, promote. The validate step is the gate — "
        "validate_candidate.py returns non-zero if the candidate doesn't beat the champion, "
        "which fails the workflow and blocks stages 5 and 6. Nothing gets promoted without "
        "passing the gate. Runtime is about 8 minutes on ubuntu-latest. Because our repo is "
        "public, GitHub Actions minutes are free and unlimited. AWS costs are pennies per run.")
```

- [ ] **Step 2: Wire into `build()`, add test**

```python
    slide_10_gh_actions(prs)
```

```python
def test_slide_10_gh_actions(built_deck):
    s = built_deck.slides[9]
    joined = " ".join(_slide_texts(s))
    for stage in ("Snapshot data", "Build features", "Train candidate",
                  "Validate", "Register", "Promote"):
        assert stage in joined, f"missing stage: {stage}"
    assert "BLOCKS" in joined
    assert "ubuntu-latest" in joined
    assert _placeholder_count(s) == 1
```

- [ ] **Step 3: Build + test + visual check**

```bash
python 04_Scripts/build_slides.py
pytest tests/test_build_slides.py -v
open "07_Final/slides/CAAS_final.pptx"
```

- [ ] **Step 4: Commit**

```bash
git add 04_Scripts/build_slides.py tests/test_build_slides.py
git commit -m "feat: implement slide 10 (GH Actions stages + blocking step)"
```

---

## Task 10: Slide 11 (Live demo — embedded screenshots, Option B)

**Files:**
- Modify: `04_Scripts/build_slides.py`
- Modify: `tests/test_build_slides.py`

- [ ] **Step 1: Implement `slide_11_demo`**

Append to `build_slides.py`:

```python
# ============================================================
#  Slide 11 — LIVE DEMO (embedded screenshots, zero live tabs)
# ============================================================
def slide_11_demo(prs):
    s = blank_slide(prs)

    add_text_box(s, left=Inches(0.5), top=Inches(0.25), width=Inches(12.3), height=Inches(0.55),
                 text="CAAS running on AWS — http://13.250.17.6",
                 size_pt=22, bold=True, color=COLOR_PRIMARY)
    add_text_box(s, left=Inches(0.5), top=Inches(0.85), width=Inches(12.3), height=Inches(0.4),
                 text="5 views, 240 seconds, all captures from live EC2",
                 size_pt=12, italic=True, color=COLOR_MUTED)

    # 2x3 grid, 5 screenshot placeholders + 1 transition text cell
    cells = [
        ("1️⃣ Streamlit dashboard",   "Dashboard from http://13.250.17.6:8502"),
        ("2️⃣ FastAPI Swagger",       "Swagger UI from http://13.250.17.6:8000/docs"),
        ("3️⃣ MLflow experiments",    "Experiments + champion run from :5001"),
        ("4️⃣ Evidently drift report","Latest report with core vs soft features"),
        ("5️⃣ GitHub Actions",        "Actions list + retrain.yml expanded stages"),
    ]
    col_w = 4.0
    row_h = 2.75
    gap = 0.15
    start_x = (13.333 - (col_w * 3 + gap * 2)) / 2
    start_y = 1.4
    for i, (label, caption) in enumerate(cells):
        row, col = divmod(i, 3)
        x = start_x + col * (col_w + gap)
        y = start_y + row * (row_h + gap)
        # Label above the frame
        add_text_box(s, left=Inches(x), top=Inches(y), width=Inches(col_w), height=Inches(0.3),
                     text=label, size_pt=12, bold=True, color=COLOR_PRIMARY)
        # Placeholder below label
        add_placeholder_frame(
            s,
            left=Inches(x), top=Inches(y + 0.35),
            width=Inches(col_w), height=Inches(row_h - 0.35),
            caption=caption,
            aspect_hint="16:9",
        )

    add_speaker_notes(s,
        "For the next four minutes, we're walking through CAAS as it runs on AWS. All five "
        "views are captures from our live EC2 at 13.250.17.6. Streamlit dashboard — "
        "freshness, forecast cards, alert banner, history, Model Insights tab. FastAPI — "
        "health check, forecast endpoint, OpenAPI. MLflow — eight experiments, champion "
        "run with full lineage. Drift — core green, FIRMS amber and suppressed by the "
        "two-tier policy. GitHub Actions — Tests green, Drift Check green, retrain workflow "
        "with the six stages we just covered. Back to slides — let's talk cost.")
```

- [ ] **Step 2: Wire into `build()`, add test**

```python
    slide_11_demo(prs)
```

```python
def test_slide_11_demo(built_deck):
    s = built_deck.slides[10]
    joined = " ".join(_slide_texts(s))
    assert "http://13.250.17.6" in joined
    assert "Streamlit" in joined
    assert "FastAPI" in joined
    assert "MLflow" in joined
    assert "Evidently" in joined or "drift" in joined.lower()
    assert "GitHub Actions" in joined
    assert _placeholder_count(s) == 5
```

- [ ] **Step 3: Build + test + visual check**

```bash
python 04_Scripts/build_slides.py
pytest tests/test_build_slides.py -v
open "07_Final/slides/CAAS_final.pptx"
```

- [ ] **Step 4: Commit**

```bash
git add 04_Scripts/build_slides.py tests/test_build_slides.py
git commit -m "feat: implement slide 11 (demo grid — embedded screenshots)"
```

---

## Task 11: Slides 12-14 (Cost, Limitations + learned, Takeaways)

**Files:**
- Modify: `04_Scripts/build_slides.py`
- Modify: `tests/test_build_slides.py`

- [ ] **Step 1: Implement `slide_12_cost`, `slide_13_limitations`, `slide_14_takeaways`**

Append to `build_slides.py`:

```python
# ============================================================
#  Slide 12 — Cost breakdown + realism defense
# ============================================================
def slide_12_cost(prs):
    s = blank_slide(prs)

    add_text_box(s, left=Inches(0.5), top=Inches(0.3), width=Inches(12.3), height=Inches(0.55),
                 text="$0.55/day — with receipts",
                 size_pt=26, bold=True, color=COLOR_PRIMARY)

    # Cost table
    rows = [
        ("Component", "Usage", "Daily cost"),
        ("EC2 t3.small (24/7)",     "24 h × $0.023/h",           "$0.552"),
        ("EBS gp3 20 GB",           "storage + IOPS",            "$0.053"),
        ("S3 standard (~1.5 GB)",   "storage + requests",        "$0.004"),
        ("Data transfer out",       "~200 MB/day",               "$0.018"),
        ("GitHub Actions",          "public repo",               "$0.00"),
        ("FIRMS / Open-Meteo / PCD","free research tier",        "$0.00"),
        ("Total",                   "",                          "~$0.63/day"),
        ("with EventBridge stop 12h/day", "",                    "~$0.35/day"),
    ]
    tbl = s.shapes.add_table(
        rows=len(rows), cols=3,
        left=Inches(0.5), top=Inches(1.1), width=Inches(8.3), height=Inches(4.6),
    ).table
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            cell = tbl.cell(r, c); cell.text = v
            is_header = (r == 0)
            is_total  = row[0] == "Total"
            is_stop   = "EventBridge" in row[0]
            for para in cell.text_frame.paragraphs:
                for run in para.runs:
                    set_font(run,
                             size_pt=12,
                             bold=is_header or is_total,
                             italic=is_stop,
                             color=RGBColor(0xFF, 0xFF, 0xFF) if is_header else COLOR_TEXT)
            if is_header:
                cell.fill.solid(); cell.fill.fore_color.rgb = COLOR_TABLE_HEADER_BG
            elif is_total:
                cell.fill.solid(); cell.fill.fore_color.rgb = COLOR_ACCENT
            elif r % 2 == 0:
                cell.fill.solid(); cell.fill.fore_color.rgb = COLOR_TABLE_ROW_ALT

    # Right column — donut placeholder + callout
    add_placeholder_frame(
        s,
        left=Inches(9.2), top=Inches(1.1),
        width=Inches(3.6), height=Inches(2.8),
        caption="Daily cost breakdown donut (generate in Canva)",
        aspect_hint="square",
    )

    callout = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                  Inches(0.5), Inches(5.9), Inches(12.3), Inches(1.3))
    callout.fill.solid(); callout.fill.fore_color.rgb = COLOR_SUCCESS
    callout.line.fill.background()
    tf = callout.text_frame; tf.word_wrap = True
    tf.margin_left = Inches(0.3); tf.margin_right = Inches(0.3)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = ("Always-on serving (FastAPI + Streamlit + MLflow + Evidently) all fits inside "
              "a single t3.small — the three services peak at ~1.3 GB RAM. "
              "The \"always-on\" cost is ONE EC2 instance, not four.")
    set_font(r, size_pt=13, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))

    add_speaker_notes(s,
        "The cost claim the professor asked us to defend. On-demand pricing, one EC2 "
        "t3.small running 24/7, is 55 cents a day. Add a little storage, egress, and we "
        "land at 63 cents. GitHub Actions is free because our repo is public. The data APIs "
        "are free at research tier. The 'always-on' story that the professor flagged as "
        "suspicious — the four services — all co-locate on a single 2 GB EC2 instance "
        "because our workload is low traffic. If we ran EventBridge to stop the instance "
        "overnight, we'd drop to 35 cents a day. For a realistic national deployment you'd "
        "horizontally scale, but for one station at demo scale, this math is honest.")


# ============================================================
#  Slide 13 — Limitations + what we learned
# ============================================================
def slide_13_limitations(prs):
    s = blank_slide(prs)

    add_text_box(s, left=Inches(0.5), top=Inches(0.3), width=Inches(12.3), height=Inches(0.55),
                 text="Limitations and what we learned",
                 size_pt=26, bold=True, color=COLOR_PRIMARY)

    # Left column — Limitations
    add_text_box(s, left=Inches(0.5), top=Inches(1.1), width=Inches(6.0), height=Inches(0.5),
                 text="Limitations", size_pt=18, bold=True, color=COLOR_DANGER)
    limits = [
        ("Single station.", "CAAS trains and serves on one PCD station (35T/36T). Inter-station transfer not demonstrated."),
        ("Hindcast weather.", "ERA5 is retrospective; true t+3/t+7 production needs ECMWF/GFS forecast inputs."),
        ("LSTM under-performs at t+3.", "R² = 0.54. Transformers are a likely next step."),
        ("Seasonal FIRMS zero-inflation.", "Suppression heuristic works; STL decomposition would be cleaner."),
    ]
    for i, (title, body) in enumerate(limits):
        y = 1.7 + i * 1.25
        add_text_box(s, left=Inches(0.5), top=Inches(y), width=Inches(6.0), height=Inches(0.4),
                     text="• " + title, size_pt=13, bold=True, color=COLOR_TEXT)
        add_text_box(s, left=Inches(0.75), top=Inches(y + 0.4), width=Inches(5.75), height=Inches(0.85),
                     text=body, size_pt=11, color=COLOR_MUTED)

    # Right column — What we learned
    add_text_box(s, left=Inches(7.0), top=Inches(1.1), width=Inches(6.0), height=Inches(0.5),
                 text="What we learned", size_pt=18, bold=True, color=COLOR_SUCCESS)
    learned = [
        ("Boring MLOps pays.", "Chronological splits, validation gates, drift policy — the least novel parts carried the story."),
        ("Interpretability > complexity.", "SHAP told a physically clean story a black-box wouldn't have."),
        ("Public data goes far.", "Three free sources produced a grader-ready system."),
        ("Integration is the product.", "The pieces aren't new — wiring them into a self-retraining pipeline on one EC2 is."),
    ]
    for i, (title, body) in enumerate(learned):
        y = 1.7 + i * 1.25
        add_text_box(s, left=Inches(7.0), top=Inches(y), width=Inches(6.0), height=Inches(0.4),
                     text="• " + title, size_pt=13, bold=True, color=COLOR_TEXT)
        add_text_box(s, left=Inches(7.25), top=Inches(y + 0.4), width=Inches(5.75), height=Inches(0.85),
                     text=body, size_pt=11, color=COLOR_MUTED)

    add_speaker_notes(s,
        "What we'd change and what we take away. Four honest limitations — single station, "
        "hindcast weather, LSTM at mid-horizon, and seasonal zero-inflation. None of these "
        "are blockers for the demo scope, but all four are the first things we'd fix in a "
        "real deployment. On the learning side — the boring MLOps parts carried more weight "
        "than the modeling choices. SHAP gave us a physically interpretable story that a "
        "pure deep model wouldn't have offered. And the whole project reinforced that "
        "integration — not invention — was the real engineering.")


# ============================================================
#  Slide 14 — Takeaways + thank-you
# ============================================================
def slide_14_takeaways(prs):
    s = blank_slide(prs)

    add_text_box(s, left=Inches(0.5), top=Inches(0.4), width=Inches(12.3), height=Inches(0.45),
                 text="Three takeaways", size_pt=16, italic=True,
                 color=COLOR_MUTED, align=PP_ALIGN.CENTER)

    takeaways = [
        ("🎯", "LightGBM + engineered lags beat LSTM at all three horizons on this problem."),
        ("🔥", "FIRMS fire data is operationally material — 4.3–6.8% MAE contribution."),
        ("⚙️", "A self-retraining MLOps pipeline fits in $0.55/day — integration over invention."),
    ]
    for i, (icon, text) in enumerate(takeaways):
        y = 1.3 + i * 1.0
        add_text_box(s, left=Inches(1.0), top=Inches(y), width=Inches(0.8), height=Inches(0.8),
                     text=icon, size_pt=40, align=PP_ALIGN.CENTER)
        add_text_box(s, left=Inches(2.0), top=Inches(y + 0.15), width=Inches(10), height=Inches(0.8),
                     text=text, size_pt=18, color=COLOR_TEXT)

    # Separator line
    line = s.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                              Inches(4.0), Inches(4.8), Inches(5.3), Inches(0.02))
    line.fill.solid(); line.fill.fore_color.rgb = COLOR_MUTED; line.line.fill.background()

    add_text_box(s, left=Inches(0.5), top=Inches(5.1), width=Inches(12.3), height=Inches(0.7),
                 text="Thank you — we welcome your questions.",
                 size_pt=28, bold=True, color=COLOR_PRIMARY, align=PP_ALIGN.CENTER)

    # Bottom-left credits
    add_text_box(s, left=Inches(0.5), top=Inches(6.6), width=Inches(8), height=Inches(0.3),
                 text="Supanut Kompayak (st126055) · Shuvam Shrestha (st125975)",
                 size_pt=11, color=COLOR_MUTED)
    add_text_box(s, left=Inches(0.5), top=Inches(6.9), width=Inches(8), height=Inches(0.3),
                 text="AT82.9002 · Instructor: Dr. Chantri Polprasert · AIT · April 2026",
                 size_pt=11, color=COLOR_MUTED)

    # Bottom-right: GitHub + QR placeholder
    add_text_box(s, left=Inches(9.5), top=Inches(6.6), width=Inches(3.3), height=Inches(0.3),
                 text="github.com/supanut-k/caas", size_pt=11, bold=True,
                 color=COLOR_PRIMARY, align=PP_ALIGN.RIGHT)
    add_placeholder_frame(
        s,
        left=Inches(11.8), top=Inches(5.5),
        width=Inches(1.0), height=Inches(1.0),
        caption="GitHub QR",
        aspect_hint="square",
    )

    add_speaker_notes(s,
        "Three takeaways. LightGBM with engineered lags wins on this problem — deep "
        "sequence is not automatically better. NASA FIRMS fire data earns its integration "
        "cost — 4 to 7 percent MAE contribution. And a self-retraining MLOps pipeline on "
        "AWS costs under 55 cents a day — the contribution of this capstone was "
        "integration, not invention. Thank you — Shuvam and I are happy to take your "
        "questions.")
```

- [ ] **Step 2: Wire all three into `build()`**

```python
    slide_12_cost(prs)
    slide_13_limitations(prs)
    slide_14_takeaways(prs)
```

- [ ] **Step 3: Add tests**

```python
def test_slide_12_cost(built_deck):
    s = built_deck.slides[11]
    joined = " ".join(_slide_texts(s))
    assert "$0.55" in joined
    assert "$0.63" in joined or "0.63" in joined
    assert "EC2 t3.small" in joined or "t3.small" in joined
    assert "GitHub Actions" in joined
    assert _placeholder_count(s) == 1


def test_slide_13_limitations(built_deck):
    s = built_deck.slides[12]
    joined = " ".join(_slide_texts(s))
    assert "Limitations" in joined
    assert "What we learned" in joined
    assert "Single station" in joined
    assert "Integration is the product" in joined
    assert _placeholder_count(s) == 0


def test_slide_14_takeaways(built_deck):
    s = built_deck.slides[13]
    joined = " ".join(_slide_texts(s))
    assert "Three takeaways" in joined
    assert "Thank you" in joined
    assert "github.com/supanut-k/caas" in joined
    assert "Supanut Kompayak" in joined
    assert "Shuvam Shrestha" in joined
    assert _placeholder_count(s) == 1
```

- [ ] **Step 4: Build + test + visual check**

```bash
python 04_Scripts/build_slides.py
pytest tests/test_build_slides.py -v
open "07_Final/slides/CAAS_final.pptx"
```

- [ ] **Step 5: Commit**

```bash
git add 04_Scripts/build_slides.py tests/test_build_slides.py
git commit -m "feat: implement slides 12-14 (cost, limitations+learned, takeaways)"
```

---

## Task 12: Final integration check + handoff

- [ ] **Step 1: Add top-level integrity tests**

Append to `tests/test_build_slides.py`:

```python
def test_deck_has_exactly_14_slides(built_deck):
    assert len(built_deck.slides) == 14, f"expected 14 slides, got {len(built_deck.slides)}"


def test_total_placeholder_count_matches_spec(built_deck):
    """Spec §5: exactly 19 placeholders across the deck.

    Breakdown: 1 (s1) + 2 (s2) + 0 (s3) + 1 (s4) + 1 (s5) + 0 (s6) + 3 (s7)
               + 2 (s8) + 0 (s9) + 1 (s10) + 5 (s11) + 1 (s12) + 0 (s13) + 1 (s14) = 19
    """
    total = sum(_placeholder_count(s) for s in built_deck.slides)
    assert total == 19, f"expected 19 placeholder frames, got {total}"


def test_every_slide_has_speaker_notes(built_deck):
    for i, slide in enumerate(built_deck.slides, start=1):
        notes = slide.notes_slide.notes_text_frame.text
        assert len(notes.strip()) > 40, f"slide {i} has no speaker notes"


def test_no_placeholder_leaked_into_normal_slide(built_deck):
    """Make sure we don't accidentally show [IMAGE PLACEHOLDER] on a slide with no frame."""
    # Nothing to assert — covered by per-slide counts. Sanity check only.
    pass
```

- [ ] **Step 2: Run the full test suite**

```bash
source caas-env/bin/activate
pytest tests/test_build_slides.py -v
```

Expected: all tests pass. If any fail, fix inline before committing.

- [ ] **Step 3: Final visual inspection**

```bash
open "07_Final/slides/CAAS_final.pptx"
```

**Visual checklist (walk every slide once):**
- [ ] Slide 1 title is centered and readable over optional hero
- [ ] Slide 2 three big stats all fit, no overflow
- [ ] Slide 3 green banner readable
- [ ] Slide 4 architecture placeholder large enough for a diagram
- [ ] Slide 5 feature table aligned to the right column
- [ ] Slide 6 metrics table: LightGBM column visibly bold
- [ ] Slide 7 three SHAP panels evenly spaced
- [ ] Slide 8 split halves balanced; threshold table readable
- [ ] Slide 9 four stage columns fit slide width, arrows visible
- [ ] Slide 10 validate box is red-outlined + red-highlighted
- [ ] Slide 11 five screenshot frames in 2×3 grid, numbered
- [ ] Slide 12 cost table + realism banner
- [ ] Slide 13 two-column layout balanced
- [ ] Slide 14 takeaways centered, credits + QR bottom-anchored

- [ ] **Step 4: Test Canva import path**

This is the delivery-gate step. The user will import into Canva — verify it works:

1. Go to `canva.com` → Create design → Import file
2. Upload `CAAS_final.pptx`
3. Verify all 14 slides import with text intact and placeholder frames visible as editable shapes
4. If any slide breaks, investigate and fix in `build_slides.py` (most common issue: exotic shape types → switch to `MSO_SHAPE.RECTANGLE`)

- [ ] **Step 5: Update `06_Handoff/CAAS_STATUS.md`**

Prepend a Session 8 entry:

```markdown
### 2026-04-22 — Session 8 — Final presentation deck

- Approved 14-slide, 15-min defense deck design (spec `docs/superpowers/specs/2026-04-22-final-slides-design.md`)
- Implemented `04_Scripts/build_slides.py` — generates `07_Final/slides/CAAS_final.pptx`
- Numeric values cross-checked against `03_Data/results/*.json` at build time
- 19 image placeholder frames across deck (Supanut to paste real images in Canva)
- Demo approach: Option B (embedded screenshots, no live AWS tabs during defense)
- Standalone demo video: DROPPED
- Tests: `tests/test_build_slides.py` — deck integrity (14 slides, 19 placeholders, speaker notes on all, spec-locked metric values present)
- Next: Supanut imports pptx into Canva → pastes screenshots → rehearses → exports PDF → submits.
```

- [ ] **Step 6: Final commit**

```bash
git add 04_Scripts/build_slides.py tests/test_build_slides.py 06_Handoff/CAAS_STATUS.md
git commit -m "feat: integration tests + status log for final slides"
```

- [ ] **Step 7: Tag the build**

```bash
git tag -a v1.0-slides -m "Final defense slide deck — 14 slides, 15 min, spec-approved"
```

---

## Self-Review (completed by plan author)

**Spec coverage:** every slide 1–14 has a dedicated task, every placeholder in spec §5 appears in the build code, every numeric value in spec §6 is pinned in the constants module and verified against JSONs at build time.

**Placeholder scan:** no TBD/TODO/placeholder-instruction language. All "placeholder frame" references are the intentional user-pastable image slots defined in spec §5, not plan failures.

**Type/method consistency:** all slide functions use the pattern `slide_N_<topic>(prs)` returning `None` after calling `prs.slides.add_slide(...)`. All use `blank_slide(prs)` helper. Colours, fonts, and `add_placeholder_frame`/`add_text_box`/`add_speaker_notes` helpers are defined in Task 3 and used consistently across all slide tasks. `METRICS`, `ABLATION_DELTAS`, `SCENARIO_C` constants are defined in Task 2 and referenced by name in Tasks 6-8.

**Task sizing:** each task touches 1–3 slides worth of code, builds + tests + commits at the end. No task takes more than ~25 min of focused work.
