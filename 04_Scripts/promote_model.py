"""
CAAS — MLflow Model Promotion
Transitions the latest run in MLflow from Staging → Production
and archives the previous champion.

Called by: .github/workflows/retrain.yml  step [5/6]

Required env vars:
    MLFLOW_TRACKING_URI  (e.g. http://<ec2-ip>:5000  or local path to mlruns/)

Usage:
    python promote_model.py
    python promote_model.py --from Staging --to Production --archive-champion
    python promote_model.py --dry-run
"""

import os
import sys
import argparse
from dotenv import load_dotenv

load_dotenv()

try:
    import mlflow
    from mlflow.tracking import MlflowClient
except ImportError:
    raise SystemExit("Install mlflow: pip install mlflow")

# ── Config ─────────────────────────────────────────────────
BASE         = os.path.dirname(os.path.abspath(__file__))
TRACKING_URI = os.environ.get(
    "MLFLOW_TRACKING_URI",
    os.path.join(BASE, "..", "mlruns")   # fallback to local
)

EXPERIMENT_NAME = "CAAS-XGBoost"
MODEL_NAMES     = ["caas-xgboost-t1", "caas-xgboost-t3", "caas-xgboost-t7"]


def promote_model(client: MlflowClient, model_name: str,
                  from_stage: str, to_stage: str,
                  archive_champion: bool, dry_run: bool) -> bool:
    """
    Promotes the latest version in `from_stage` to `to_stage`.
    Optionally archives the current `to_stage` version first.
    """
    print(f"\n── {model_name} ──────────────────────────────────")

    # Find latest version in from_stage
    versions_in_from = client.get_latest_versions(model_name, stages=[from_stage])
    if not versions_in_from:
        # Fall back: find the most recent run and register it
        print(f"   ℹ️  No version in '{from_stage}' — checking 'None' stage...")
        versions_in_from = client.get_latest_versions(model_name, stages=["None"])

    if not versions_in_from:
        print(f"   ⚠️  No registered versions found for {model_name}. Skipping.")
        return False

    candidate = versions_in_from[0]
    print(f"   Candidate: version {candidate.version}  run_id={candidate.run_id[:8]}...")

    # Find current champion (to_stage)
    current_champs = client.get_latest_versions(model_name, stages=[to_stage])
    if current_champs and archive_champion:
        champ = current_champs[0]
        print(f"   Archiving current champion: version {champ.version} → Archived")
        if not dry_run:
            client.transition_model_version_stage(
                name=model_name, version=champ.version, stage="Archived"
            )

    # Promote candidate
    print(f"   Promoting: version {candidate.version}  {from_stage} → {to_stage}")
    if not dry_run:
        client.transition_model_version_stage(
            name=model_name,
            version=candidate.version,
            stage=to_stage,
            archive_existing_versions=False,
        )
        print(f"   ✅  {model_name} v{candidate.version} is now {to_stage}")
    else:
        print(f"   [DRY-RUN] Would promote to {to_stage}")

    return True


def main():
    parser = argparse.ArgumentParser(description="Promote CAAS models in MLflow registry")
    parser.add_argument("--from", dest="from_stage", default="Staging",
                        choices=["None", "Staging", "Production"])
    parser.add_argument("--to", dest="to_stage", default="Production",
                        choices=["Staging", "Production", "Archived"])
    parser.add_argument("--archive-champion", action="store_true",
                        help="Archive current Production version before promoting")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without making changes")
    args = parser.parse_args()

    print("=" * 60)
    print("  CAAS — MLflow Model Promotion")
    print(f"  {args.from_stage} → {args.to_stage}  |  Archive: {args.archive_champion}  |  Dry-run: {args.dry_run}")
    print(f"  Tracking URI: {TRACKING_URI}")
    print("=" * 60)

    mlflow.set_tracking_uri(TRACKING_URI)
    client = MlflowClient()

    success, skipped = 0, 0
    for model_name in MODEL_NAMES:
        # Check if model is registered at all
        try:
            client.get_registered_model(model_name)
        except mlflow.exceptions.MlflowException:
            # Model not registered — look for runs and register
            print(f"\n── {model_name} ──────────────────────────────────")
            print(f"   ℹ️  Not registered yet. Searching latest experiment run...")

            exp = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
            if exp:
                horizon = model_name.split("-")[-1]  # t1, t3, or t7
                runs = mlflow.search_runs(
                    experiment_ids=[exp.experiment_id],
                    filter_string=f"tags.mlflow.runName = 'XGBoost-{horizon}'",
                    order_by=["start_time DESC"],
                    max_results=1,
                )
                if not runs.empty:
                    run_id    = runs.iloc[0]["run_id"]
                    model_uri = f"runs:/{run_id}/model_{horizon}"
                    if not args.dry_run:
                        mlflow.register_model(model_uri, model_name)
                        print(f"   ✅  Registered {model_name} from run {run_id[:8]}...")
                    else:
                        print(f"   [DRY-RUN] Would register from run {run_id[:8]}...")
                    skipped += 1
                    continue
            skipped += 1
            continue

        ok = promote_model(
            client, model_name,
            from_stage=args.from_stage,
            to_stage=args.to_stage,
            archive_champion=args.archive_champion,
            dry_run=args.dry_run,
        )
        if ok:
            success += 1
        else:
            skipped += 1

    print(f"\n{'='*60}")
    print(f"✅  Done — {success} promoted, {skipped} skipped")
    if success == 0 and skipped > 0:
        print("   Tip: Run train_xgboost.py first, then retry.")


if __name__ == "__main__":
    main()
