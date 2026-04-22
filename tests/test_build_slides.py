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


def test_verify_numbers_passes_against_current_jsons():
    """verify_numbers() must not raise against the current results/ JSONs."""
    sys.path.insert(0, str(PROJECT_ROOT / "04_Scripts"))
    from build_slides import verify_numbers  # noqa: E402

    verify_numbers()  # raises on mismatch — test fails if it does
