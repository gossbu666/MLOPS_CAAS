"""
CAAS — Upload Results to S3
Pushes processed data and forecast results to the CAAS S3 bucket.

Called by: .github/workflows/daily_pipeline.yml  step [4/5]

Required env vars (set via GitHub Secrets in CI):
    AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY
    AWS_REGION          (e.g. ap-southeast-1)
    S3_BUCKET_NAME      (e.g. caas-mlops-bucket)

Usage:
    python upload_to_s3.py
    python upload_to_s3.py --dry-run   # show what would be uploaded, don't upload
"""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

try:
    import boto3
    from botocore.exceptions import NoCredentialsError, ClientError
except ImportError:
    raise SystemExit("Install boto3: pip install boto3")

# ── Config ─────────────────────────────────────────────────
BASE         = os.path.dirname(os.path.abspath(__file__))
DATA_DIR     = os.path.join(BASE, "..", "03_Data")
S3_BUCKET    = os.environ.get("S3_BUCKET_NAME", "caas-mlops-bucket")
AWS_REGION   = os.environ.get("AWS_REGION", "ap-southeast-1")

# Files to upload and their S3 prefix
UPLOAD_MANIFEST = [
    # (local_path,                              s3_key_prefix)
    ("processed/features.csv",                  "data/processed/"),
    ("processed/pm25_consolidated.csv",         "data/processed/"),
    ("processed/weather_consolidated.csv",      "data/processed/"),
    ("processed/firms_consolidated.csv",        "data/processed/"),
    ("results/latest_forecast.json",            "results/"),
    ("results/forecast_history.csv",            "results/"),
    ("results/xgboost_summary.json",            "results/"),
    ("results/drift_summary.json",              "results/"),
    ("models/xgboost_t1.json",                  "models/"),
    ("models/xgboost_t3.json",                  "models/"),
    ("models/xgboost_t7.json",                  "models/"),
]


def upload_file(s3_client, local_path: str, s3_key: str, dry_run: bool) -> bool:
    if not os.path.exists(local_path):
        print(f"   ⚠️  Skip (not found): {local_path}")
        return False

    size_kb = os.path.getsize(local_path) / 1024
    print(f"   {'[DRY-RUN] ' if dry_run else ''}⬆️  {local_path} → s3://{S3_BUCKET}/{s3_key}  ({size_kb:.1f} KB)")

    if dry_run:
        return True

    try:
        s3_client.upload_file(local_path, S3_BUCKET, s3_key)
        return True
    except (NoCredentialsError, ClientError) as e:
        print(f"   ❌  Upload failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Upload CAAS results to S3")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be uploaded without actually uploading")
    args = parser.parse_args()

    if not args.dry_run:
        if not os.environ.get("AWS_ACCESS_KEY_ID"):
            print("❌  AWS_ACCESS_KEY_ID not set. Add to .env or GitHub Secrets.")
            sys.exit(1)

    print(f"📦  Uploading CAAS results to s3://{S3_BUCKET}/")
    print(f"    Region: {AWS_REGION}  |  Dry-run: {args.dry_run}")
    print()

    s3 = None if args.dry_run else boto3.client("s3", region_name=AWS_REGION)

    # Add date-stamped copy of drift report if it exists
    from datetime import date
    today = date.today().strftime("%Y%m%d")
    drift_html = os.path.join(DATA_DIR, "results", f"drift_report_{today}.html")
    if os.path.exists(drift_html):
        UPLOAD_MANIFEST.append(
            (f"results/drift_report_{today}.html", f"results/drift_reports/")
        )

    success, fail = 0, 0
    for rel_path, s3_prefix in UPLOAD_MANIFEST:
        local = os.path.join(DATA_DIR, rel_path)
        filename = os.path.basename(rel_path)
        s3_key = s3_prefix + filename

        ok = upload_file(s3, local, s3_key, args.dry_run)
        if ok:
            success += 1
        else:
            fail += 1

    print(f"\n{'✅' if fail == 0 else '⚠️ '} Upload complete: {success} succeeded, {fail} skipped/failed")

    if fail > 0 and not args.dry_run:
        sys.exit(1)


if __name__ == "__main__":
    main()
