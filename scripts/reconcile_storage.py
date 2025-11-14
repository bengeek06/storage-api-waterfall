#!/usr/bin/env python3
"""
reconcile_storage.py
--------------------

Maintenance script to reconcile MinIO storage with database records.
Run this periodically (e.g., daily via cron) to detect and report inconsistencies.

Usage:
    python scripts/reconcile_storage.py [--fix] [--report-only]

Options:
    --fix           Automatically fix inconsistencies (mark as corrupted)
    --report-only   Only report issues, don't modify anything
    --dry-run       Same as --report-only
"""

import sys
import os
import argparse
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.config import ProductionConfig
from app.models.storage import StorageFile, FileVersion
from app.models.db import db
from app.services.storage_service import storage_backend
from app.logger import logger


class StorageReconciliator:
    """Reconciles MinIO storage with database records."""

    def __init__(self, fix=False, dry_run=False):
        self.fix = fix and not dry_run
        self.dry_run = dry_run
        self.stats = {
            "total_files": 0,
            "total_versions": 0,
            "db_orphans": 0,  # In DB but not in MinIO
            "minio_orphans": 0,  # In MinIO but not in DB
            "corrupted": 0,
            "ok": 0,
        }

    def check_database_orphans(self):
        """Check for files in database that don't exist in MinIO."""
        logger.info(
            "Checking for database orphans (DB entries without MinIO files)..."
        )

        versions = FileVersion.query.filter(
            FileVersion.status != "corrupted"
        ).all()

        self.stats["total_versions"] = len(versions)

        for version in versions:
            try:
                # Try to stat the object in MinIO
                storage_backend.minio_client.stat_object(
                    bucket_name=storage_backend.bucket_name,
                    object_name=version.object_key,
                )
                self.stats["ok"] += 1

            except Exception as exc:  # pylint: disable=broad-exception-caught
                if "NoSuchKey" in str(exc) or "Not Found" in str(exc):
                    self.stats["db_orphans"] += 1
                    logger.warning(
                        f"DB orphan found: {version.object_key} "
                        f"(file_id={version.file_id}, version_id={version.id})"
                    )

                    if self.fix:
                        version.status = "corrupted"
                        db.session.commit()
                        logger.info(
                            f"Marked version {version.id} as corrupted"
                        )
                        self.stats["corrupted"] += 1
                else:
                    logger.error(
                        f"Error checking {version.object_key}: {exc}",
                        exc_info=True,
                    )

    def check_minio_orphans(self):
        """Check for files in MinIO that don't exist in database."""
        logger.info(
            "Checking for MinIO orphans (MinIO files without DB entries)..."
        )

        bucket_name = storage_backend.bucket_name

        try:
            # List all objects in bucket
            objects = storage_backend.minio_client.list_objects(
                bucket_name, recursive=True
            )

            for obj in objects:
                object_key = obj.object_name

                # Check if exists in database
                version = FileVersion.query.filter_by(
                    object_key=object_key
                ).first()

                if not version:
                    self.stats["minio_orphans"] += 1
                    logger.warning(f"MinIO orphan found: {object_key}")

                    if self.fix:
                        # Option 1: Delete from MinIO (dangerous!)
                        # storage_backend.minio_client.remove_object(bucket_name, object_key)
                        # logger.info(f"Deleted orphan from MinIO: {object_key}")

                        # Option 2: Just log for manual review (safer)
                        logger.info(
                            f"MinIO orphan detected (manual cleanup required): {object_key}"
                        )

        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error(f"Error listing MinIO objects: {exc}", exc_info=True)

    def generate_report(self):
        """Generate reconciliation report."""
        logger.info("=" * 80)
        logger.info("STORAGE RECONCILIATION REPORT")
        logger.info(f"Generated at: {datetime.now(timezone.utc).isoformat()}")
        logger.info("=" * 80)
        logger.info(
            f"Total file versions checked: {self.stats['total_versions']}"
        )
        logger.info(f"OK (consistent): {self.stats['ok']}")
        logger.info(
            f"DB orphans (in DB, not in MinIO): {self.stats['db_orphans']}"
        )
        logger.info(
            f"MinIO orphans (in MinIO, not in DB): {self.stats['minio_orphans']}"
        )
        logger.info(f"Marked as corrupted: {self.stats['corrupted']}")
        logger.info("=" * 80)

        if self.dry_run:
            logger.info("DRY RUN - No changes were made")
        elif self.fix:
            logger.info("FIX MODE - Inconsistencies were corrected")
        else:
            logger.info("REPORT ONLY - Use --fix to correct inconsistencies")

        logger.info("=" * 80)

    def run(self):
        """Run the reconciliation process."""
        logger.info(
            f"Starting storage reconciliation (fix={self.fix}, dry_run={self.dry_run})"
        )

        self.check_database_orphans()
        self.check_minio_orphans()
        self.generate_report()

        return self.stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Reconcile MinIO storage with database records"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically fix inconsistencies (mark DB orphans as corrupted)",
    )
    parser.add_argument(
        "--report-only",
        "--dry-run",
        action="store_true",
        help="Only report issues, don't modify anything",
    )

    args = parser.parse_args()

    # Create Flask app context
    app = create_app(ProductionConfig)

    with app.app_context():
        reconciliator = StorageReconciliator(
            fix=args.fix, dry_run=args.report_only
        )
        stats = reconciliator.run()

        # Exit with error code if issues found
        if stats["db_orphans"] > 0 or stats["minio_orphans"] > 0:
            sys.exit(1)

        sys.exit(0)


if __name__ == "__main__":
    main()
