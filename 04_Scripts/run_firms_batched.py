"""
Run FIRMS fetch in year batches with one command.

This wrapper reduces API transaction-limit collisions by running smaller year windows,
then merges each successful batch output into one final consolidated file.

Usage:
    caas-env/bin/python 04_Scripts/run_firms_batched.py

Optional env vars:
    FIRMS_START_YEAR=2011
    FIRMS_END_YEAR=2025
    FIRMS_BATCH_SIZE=3
    FIRMS_BATCH_RETRIES=2
    FIRMS_BATCH_PAUSE_SEC=20
"""

from __future__ import annotations

import os
import sys
import time
import shutil
import subprocess
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BASE_DIR / "04_Scripts"
FETCH_SCRIPT = SCRIPTS_DIR / "fetch_firms.py"
PROCESSED_PATH = BASE_DIR / "03_Data" / "processed" / "firms_consolidated.csv"
BATCH_OUTPUT_DIR = BASE_DIR / "03_Data" / "raw" / "firms_batch_outputs"


def make_batches(start_year: int, end_year: int, batch_size: int) -> list[tuple[int, int]]:
    batches = []
    current = start_year
    while current <= end_year:
        batch_end = min(current + batch_size - 1, end_year)
        batches.append((current, batch_end))
        current = batch_end + 1
    return batches


def run_one_batch(
    py_exec: str,
    batch_start: int,
    batch_end: int,
    retries: int,
    pause_sec: int,
) -> bool:
    env = os.environ.copy()
    env["FIRMS_START_YEAR"] = str(batch_start)
    env["FIRMS_END_YEAR"] = str(batch_end)

    for attempt in range(1, retries + 1):
        print(f"\n🚀 Batch {batch_start}-{batch_end} (attempt {attempt}/{retries})")
        result = subprocess.run([py_exec, str(FETCH_SCRIPT)], env=env)

        if result.returncode == 0:
            print(f"✅ Batch {batch_start}-{batch_end} completed")
            return True

        print(f"⚠️ Batch {batch_start}-{batch_end} failed with exit code {result.returncode}")
        if attempt < retries:
            print(f"⏳ Cooling down {pause_sec}s before retry...")
            time.sleep(pause_sec)

    return False


def snapshot_batch_output(batch_start: int, batch_end: int) -> Path:
    if not PROCESSED_PATH.exists():
        raise FileNotFoundError(f"Missing expected output: {PROCESSED_PATH}")

    BATCH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_path = BATCH_OUTPUT_DIR / f"firms_{batch_start}_{batch_end}.csv"
    shutil.copy2(PROCESSED_PATH, snapshot_path)
    return snapshot_path


def merge_batch_outputs(batch_files: list[Path], final_start: int, final_end: int) -> None:
    if not batch_files:
        raise RuntimeError("No batch output files to merge")

    frames = []
    for path in batch_files:
        df = pd.read_csv(path)
        if "date" not in df.columns:
            raise ValueError(f"Invalid batch output (missing date column): {path}")
        frames.append(df)

    merged = pd.concat(frames, ignore_index=True)
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
    merged = merged.dropna(subset=["date"]) 
    merged = merged.sort_values("date").drop_duplicates(subset=["date"], keep="last")

    full_range = pd.date_range(start=f"{final_start}-01-01", end=f"{final_end}-12-31", freq="D")
    merged = merged.set_index("date").reindex(full_range).rename_axis("date").reset_index()

    for col in ["hotspot_count", "hotspot_50km", "hotspot_100km"]:
        if col in merged.columns:
            merged[col] = merged[col].fillna(0).astype(int)

    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(PROCESSED_PATH, index=False)


if __name__ == "__main__":
    start_year = int(os.getenv("FIRMS_START_YEAR", "2011"))
    end_year = int(os.getenv("FIRMS_END_YEAR", "2025"))
    batch_size = max(1, int(os.getenv("FIRMS_BATCH_SIZE", "3")))
    batch_retries = max(1, int(os.getenv("FIRMS_BATCH_RETRIES", "2")))
    batch_pause_sec = max(5, int(os.getenv("FIRMS_BATCH_PAUSE_SEC", "20")) )

    if start_year > end_year:
        raise ValueError("FIRMS_START_YEAR must be <= FIRMS_END_YEAR")

    py_exec = sys.executable
    batches = make_batches(start_year, end_year, batch_size)

    print("🔥 FIRMS batched runner")
    print(f"   Python     : {py_exec}")
    print(f"   Range      : {start_year} -> {end_year}")
    print(f"   Batch size : {batch_size} year(s)")
    print(f"   Retries    : {batch_retries}")
    print(f"   Pause      : {batch_pause_sec}s")
    print(f"   Batches    : {', '.join(f'{s}-{e}' for s, e in batches)}")

    snapshots: list[Path] = []
    failed_batches: list[str] = []

    for batch_start, batch_end in batches:
        ok = run_one_batch(py_exec, batch_start, batch_end, batch_retries, batch_pause_sec)
        if not ok:
            failed_batches.append(f"{batch_start}-{batch_end}")
            continue

        try:
            snapshot = snapshot_batch_output(batch_start, batch_end)
            snapshots.append(snapshot)
        except Exception as exc:
            failed_batches.append(f"{batch_start}-{batch_end} (snapshot error: {exc})")

    if failed_batches:
        print("\n❌ Some batches failed:")
        for item in failed_batches:
            print(f"   - {item}")
        print("\nFix/retry only failed batches by setting FIRMS_START_YEAR and FIRMS_END_YEAR.")
        sys.exit(1)

    merge_batch_outputs(snapshots, start_year, end_year)
    print(f"\n✅ Final merged output saved: {PROCESSED_PATH}")
