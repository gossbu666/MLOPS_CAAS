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
