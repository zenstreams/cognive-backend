#!/usr/bin/env python3
"""
MinIO Storage Initialization Script

Run this script to initialize MinIO buckets with lifecycle policies.

Usage:
    python scripts/init_storage.py

This script:
1. Connects to MinIO
2. Creates all required buckets
3. Configures lifecycle/retention policies
4. Enables versioning
5. Validates the setup
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.storage import BUCKETS, get_storage_client, init_storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def validate_storage():
    """Validate storage setup by listing buckets and testing operations."""
    logger.info("\n" + "=" * 60)
    logger.info("VALIDATING STORAGE SETUP")
    logger.info("=" * 60)

    storage = get_storage_client()

    # List all buckets
    try:
        buckets = storage.minio_client.list_buckets()
        logger.info(f"\n✅ Found {len(buckets)} buckets:")
        for bucket in buckets:
            logger.info(f"   - {bucket.name} (created: {bucket.creation_date})")

        # Verify our expected buckets exist
        bucket_names = {b.name for b in buckets}
        expected_buckets = set(BUCKETS.keys())
        missing = expected_buckets - bucket_names
        extra = bucket_names - expected_buckets

        if missing:
            logger.warning(f"\n⚠️  Missing expected buckets: {missing}")
        if extra:
            logger.info(f"\nℹ️  Additional buckets found: {extra}")

        if not missing:
            logger.info("\n✅ All expected buckets are present!")

        # Test basic operations
        logger.info("\n" + "-" * 60)
        logger.info("TESTING BASIC OPERATIONS")
        logger.info("-" * 60)

        test_bucket = "agent-artifacts"
        test_object = "test/hello.txt"
        test_data = b"Hello from Cognive!"

        try:
            # Put object
            storage.put_object(test_bucket, test_object, test_data)
            logger.info(f"✅ Upload test passed")

            # Get object
            retrieved_data = storage.get_object(test_bucket, test_object)
            assert retrieved_data == test_data
            logger.info(f"✅ Download test passed")

            # List objects
            objects = storage.list_objects(test_bucket, prefix="test/")
            assert test_object in objects
            logger.info(f"✅ List objects test passed")

            # Generate presigned URL
            url = storage.get_presigned_url(test_bucket, test_object, expiration=300)
            assert url
            logger.info(f"✅ Presigned URL test passed")
            logger.info(f"   URL: {url[:80]}...")

            # Delete object
            storage.delete_object(test_bucket, test_object)
            logger.info(f"✅ Delete test passed")

            logger.info("\n✅ All basic operations successful!")

        except Exception as e:
            logger.error(f"\n❌ Operation test failed: {e}")
            raise

        # Display bucket info
        logger.info("\n" + "-" * 60)
        logger.info("BUCKET INFORMATION")
        logger.info("-" * 60)

        for bucket_name, config in BUCKETS.items():
            logger.info(f"\n📦 {bucket_name}")
            logger.info(f"   Description: {config['description']}")
            logger.info(f"   Retention: {config['retention_days']} days")

            # Check lifecycle policy
            try:
                lifecycle = storage.minio_client.get_bucket_lifecycle(bucket_name)
                logger.info(f"   Lifecycle: ✅ Configured")
            except Exception:
                logger.info(f"   Lifecycle: ⚠️  Not configured (may not be supported)")

        logger.info("\n" + "=" * 60)
        logger.info("✅ STORAGE VALIDATION COMPLETE")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"\n❌ Validation failed: {e}")
        raise


async def main():
    """Main initialization flow."""
    logger.info("\n" + "=" * 60)
    logger.info("COGNIVE STORAGE INITIALIZATION")
    logger.info("=" * 60)

    try:
        # Initialize storage
        await init_storage()

        # Validate setup
        await validate_storage()

        logger.info("\n✅ Storage initialization completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Access MinIO console: http://localhost:9003")
        logger.info("2. Login with credentials from .env file")
        logger.info("3. Verify buckets and policies in the web UI")
        logger.info("\nStorage is ready for use!")

    except Exception as e:
        logger.error(f"\n❌ Initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

