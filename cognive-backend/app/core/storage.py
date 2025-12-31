"""
S3-compatible object storage configuration and management.

This module provides a unified interface for S3-compatible storage backends:
- MinIO (self-hosted, free)
- AWS S3 (cloud-hosted)
- DigitalOcean Spaces
- Any S3-compatible service

Features:
- Dual client support (MinIO native + boto3)
- Automatic bucket creation with lifecycle policies
- Presigned URL generation
- Upload/download operations
- Automatic setup on application startup

Configuration:
    Switch between storage backends by changing STORAGE_ENDPOINT:
    - MinIO: STORAGE_ENDPOINT=http://minio:9000
    - AWS S3: STORAGE_ENDPOINT=https://s3.amazonaws.com
    - DO Spaces: STORAGE_ENDPOINT=https://nyc3.digitaloceanspaces.com
"""

import logging
from typing import Optional

import boto3
from botocore.client import Config
from minio import Minio
from minio.error import S3Error
from minio.lifecycleconfig import (
    Expiration,
    LifecycleConfig,
    Rule,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


# Bucket definitions with retention policies
BUCKETS = {
    "audit-logs-archive": {
        "description": "Long-term audit log storage",
        "retention_days": 90,
    },
    "execution-replay-data": {
        "description": "Agent execution replay data for debugging",
        "retention_days": 30,
    },
    "report-exports": {
        "description": "Generated reports (PDF, CSV, etc.)",
        "retention_days": 365,
    },
    "agent-artifacts": {
        "description": "Agent-generated artifacts and outputs",
        "retention_days": 180,
    },
}


class StorageClient:
    """
    Unified storage client supporting both MinIO native client and boto3 S3 API.
    
    This client works with ANY S3-compatible storage backend by using boto3.
    The storage backend is determined by the STORAGE_ENDPOINT environment variable.
    
    Examples:
        # MinIO (self-hosted)
        STORAGE_ENDPOINT=http://minio:9000
        
        # AWS S3
        STORAGE_ENDPOINT=https://s3.us-east-1.amazonaws.com
        
        # DigitalOcean Spaces
        STORAGE_ENDPOINT=https://nyc3.digitaloceanspaces.com
    
    Usage:
        storage = StorageClient()
        await storage.initialize()
        
        # Upload file
        storage.upload_file('report-exports', 'reports/2024.pdf', '/tmp/report.pdf')
        
        # Download file
        storage.download_file('report-exports', 'reports/2024.pdf', '/tmp/downloaded.pdf')
        
        # Direct bytes upload
        storage.put_object('audit-logs-archive', 'logs/app.log', b'log data')
    """

    def __init__(self):
        self._minio_client: Optional[Minio] = None
        self._s3_client = None
        self._initialized = False

    @property
    def minio_client(self) -> Minio:
        """
        MinIO native client for advanced operations.
        
        Note: This client works with MinIO-specific features. For AWS S3,
        use the s3_client property instead.
        """
        if not self._minio_client:
            self._minio_client = self._create_minio_client()
        return self._minio_client

    @property
    def s3_client(self):
        """
        Boto3 S3 client for S3-compatible operations.
        
        This client works with any S3-compatible backend (MinIO, AWS S3, etc.)
        based on the STORAGE_ENDPOINT configuration.
        """
        if not self._s3_client:
            self._s3_client = self._create_boto3_client()
        return self._s3_client

    def _create_minio_client(self) -> Minio:
        """Create MinIO native client for MinIO-specific features."""
        # Parse endpoint to extract host and port
        endpoint = settings.storage_endpoint.replace("http://", "").replace("https://", "")
        
        # Determine if SSL/TLS should be used
        secure = settings.storage_secure or settings.storage_endpoint.startswith("https://")

        logger.info(f"Initializing storage client: endpoint={endpoint}, secure={secure}")

        return Minio(
            endpoint=endpoint,
            access_key=settings.storage_access_key,
            secret_key=settings.storage_secret_key,
            secure=secure,
        )

    def _create_boto3_client(self):
        """
        Create boto3 S3-compatible client.
        
        This client works with any S3-compatible backend based on STORAGE_ENDPOINT.
        """
        logger.info(f"Initializing S3-compatible client: endpoint={settings.storage_endpoint}")

        return boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint,
            aws_access_key_id=settings.storage_access_key,
            aws_secret_access_key=settings.storage_secret_key,
            config=Config(signature_version="s3v4"),
            region_name=settings.storage_region,
        )

    async def initialize(self) -> None:
        """
        Initialize storage: create buckets and configure lifecycle policies.
        
        This should be called during application startup.
        
        Note: This is async to match FastAPI's startup event handler signature
        and to allow for future async operations without breaking the API.
        """
        if self._initialized:
            logger.info("Storage already initialized, skipping")
            return

        logger.info("Initializing object storage...")

        try:
            # Ensure all buckets exist
            for bucket_name, config in BUCKETS.items():
                self._ensure_bucket_exists(bucket_name, config)

            self._initialized = True
            logger.info("✅ Object storage initialized successfully")
            logger.info(f"   - Buckets created: {len(BUCKETS)}")
            logger.info(f"   - Endpoint: {settings.storage_endpoint}")
            
            # Only show console URL for MinIO (not for AWS S3)
            if "minio" in settings.storage_endpoint.lower():
                console_url = settings.storage_endpoint.replace(":9000", ":9001")
                logger.info(f"   - Console: {console_url}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize storage: {e}")
            raise

    def _ensure_bucket_exists(self, bucket_name: str, config: dict) -> None:
        """
        Create bucket if it doesn't exist and configure lifecycle policies.
        
        Note: Not async because MinIO client operations are synchronous.
        """
        try:
            # Check if bucket exists
            if self.minio_client.bucket_exists(bucket_name):
                logger.info(f"   ✓ Bucket '{bucket_name}' already exists")
            else:
                # Create bucket
                self.minio_client.make_bucket(bucket_name)
                logger.info(f"   + Created bucket '{bucket_name}': {config['description']}")

            # Configure lifecycle policy (auto-delete old objects)
            retention_days = config.get("retention_days")
            if retention_days:
                self._set_lifecycle_policy(bucket_name, retention_days)

            # Enable versioning (recommended for production)
            self._enable_versioning(bucket_name)

        except S3Error as e:
            logger.error(f"Error ensuring bucket '{bucket_name}': {e}")
            raise

    def _set_lifecycle_policy(self, bucket_name: str, retention_days: int) -> None:
        """
        Configure lifecycle policy to auto-delete objects after retention period.
        
        This helps manage storage costs and comply with data retention policies.
        
        Note: Not async because MinIO client operations are synchronous.
        """
        try:
            # Prefer public constructor args; fall back to older SDK shapes if needed.
            try:
                rule = Rule(
                    rule_id=f"expire-after-{retention_days}-days",
                    status="Enabled",
                    expiration=Expiration(days=retention_days),
                )
            except TypeError:
                # Older minio SDK versions may not accept `expiration=` in constructor.
                rule = Rule(
                    rule_id=f"expire-after-{retention_days}-days",
                    status="Enabled",
                )
                # Try supported attribute/property names before falling back to private.
                try:
                    setattr(rule, "expiration", Expiration(days=retention_days))
                except Exception:
                    # Last resort (kept for backward compatibility with the previous implementation).
                    rule._expiration = Expiration(days=retention_days)

            lifecycle_config = LifecycleConfig([rule])

            self.minio_client.set_bucket_lifecycle(bucket_name, lifecycle_config)
            logger.info(f"   → Lifecycle policy set: {retention_days} days retention")

        except Exception as e:
            # Storage backend may not support lifecycle in all configurations
            logger.warning(f"Could not set lifecycle policy for '{bucket_name}': {e}")

    def _enable_versioning(self, bucket_name: str) -> None:
        """
        Enable versioning on bucket for data protection.
        
        This allows recovering from accidental deletions or overwrites.
        
        Note: Not async because MinIO client operations are synchronous.
        """
        try:
            # MinIO Python client expects a VersioningConfig object (not a dict) in most versions.
            versioning_config = None
            enabled = None

            # Different minio-py versions expose these from different modules; try a few.
            try:
                from minio.versioningconfig import VersioningConfig  # type: ignore

                try:
                    from minio.commonconfig import ENABLED  # type: ignore
                except Exception:
                    # Some versions may export ENABLED from `minio.versioningconfig`.
                    from minio.versioningconfig import ENABLED  # type: ignore

                enabled = ENABLED
                versioning_config = VersioningConfig(enabled)
            except Exception:
                # Fallback: try commonconfig for VersioningConfig.
                try:
                    from minio.commonconfig import VersioningConfig, ENABLED  # type: ignore

                    enabled = ENABLED
                    versioning_config = VersioningConfig(enabled)
                except Exception:
                    versioning_config = None

            if versioning_config is None:
                raise RuntimeError("MinIO SDK does not expose VersioningConfig/ENABLED as expected")

            self.minio_client.set_bucket_versioning(bucket_name, versioning_config)
            logger.info("   → Versioning enabled")
        except Exception as e:
            # Versioning may not be available in all storage configurations
            logger.warning(f"Could not enable versioning for '{bucket_name}': {e}")

    def upload_file(
        self,
        bucket_name: str,
        object_name: str,
        file_path: str,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Upload a file to MinIO using boto3 API.
        
        Args:
            bucket_name: Destination bucket
            object_name: Object key (path) in bucket
            file_path: Local file path to upload
            metadata: Optional metadata tags
        """
        extra_args = {}
        if metadata:
            extra_args["Metadata"] = metadata
        if settings.storage_sse:
            extra_args["ServerSideEncryption"] = settings.storage_sse
            if settings.storage_sse == "aws:kms" and settings.storage_sse_kms_key_id:
                extra_args["SSEKMSKeyId"] = settings.storage_sse_kms_key_id

        self.s3_client.upload_file(file_path, bucket_name, object_name, ExtraArgs=extra_args)
        logger.info(f"Uploaded: {file_path} → s3://{bucket_name}/{object_name}")

    def download_file(self, bucket_name: str, object_name: str, file_path: str) -> None:
        """
        Download a file from MinIO using boto3 API.
        
        Args:
            bucket_name: Source bucket
            object_name: Object key (path) in bucket
            file_path: Local destination path
        """
        self.s3_client.download_file(bucket_name, object_name, file_path)
        logger.info(f"Downloaded: s3://{bucket_name}/{object_name} → {file_path}")

    def put_object(self, bucket_name: str, object_name: str, data: bytes) -> None:
        """
        Upload bytes data directly to MinIO.
        
        Args:
            bucket_name: Destination bucket
            object_name: Object key (path) in bucket
            data: Bytes data to upload
        """
        extra_args = {}
        if settings.storage_sse:
            extra_args["ServerSideEncryption"] = settings.storage_sse
            if settings.storage_sse == "aws:kms" and settings.storage_sse_kms_key_id:
                extra_args["SSEKMSKeyId"] = settings.storage_sse_kms_key_id

        self.s3_client.put_object(
            Bucket=bucket_name,
            Key=object_name,
            Body=data,
            **extra_args,
        )
        logger.info(f"Put object: s3://{bucket_name}/{object_name} ({len(data)} bytes)")

    def get_object(self, bucket_name: str, object_name: str) -> bytes:
        """
        Download object as bytes.
        
        Args:
            bucket_name: Source bucket
            object_name: Object key (path) in bucket
            
        Returns:
            Object data as bytes
        """
        response = self.s3_client.get_object(Bucket=bucket_name, Key=object_name)
        data = response["Body"].read()
        logger.info(f"Got object: s3://{bucket_name}/{object_name} ({len(data)} bytes)")
        return data

    def list_objects(self, bucket_name: str, prefix: str = "") -> list:
        """
        List objects in a bucket.
        
        Args:
            bucket_name: Bucket to list
            prefix: Optional prefix filter
            
        Returns:
            List of object keys
        """
        response = self.s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        objects = response.get("Contents", [])
        return [obj["Key"] for obj in objects]

    def delete_object(self, bucket_name: str, object_name: str) -> None:
        """
        Delete an object from MinIO.
        
        Args:
            bucket_name: Bucket containing the object
            object_name: Object key to delete
        """
        self.s3_client.delete_object(Bucket=bucket_name, Key=object_name)
        logger.info(f"Deleted: s3://{bucket_name}/{object_name}")

    def get_presigned_url(
        self,
        bucket_name: str,
        object_name: str,
        expiration: int = 3600,
    ) -> str:
        """
        Generate a presigned URL for temporary access to an object.
        
        Args:
            bucket_name: Bucket containing the object
            object_name: Object key
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Presigned URL string
        """
        url = self.s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": object_name},
            ExpiresIn=expiration,
        )
        logger.info(f"Generated presigned URL: s3://{bucket_name}/{object_name} (expires in {expiration}s)")
        return url


# Global storage client instance
_storage_client: Optional[StorageClient] = None


def get_storage_client() -> StorageClient:
    """
    Get the global storage client instance.
    
    Usage in FastAPI endpoints:
        from app.core.storage import get_storage_client
        
        @app.post("/upload")
        async def upload_file():
            storage = get_storage_client()
            storage.upload_file("report-exports", "report.pdf", "/tmp/report.pdf")
    """
    global _storage_client
    if _storage_client is None:
        _storage_client = StorageClient()
    return _storage_client


async def init_storage() -> None:
    """
    Initialize storage during application startup.
    
    Add this to your FastAPI app startup:
        from app.core.storage import init_storage
        
        @app.on_event("startup")
        async def startup_event():
            await init_storage()
    """
    storage = get_storage_client()
    await storage.initialize()


async def check_storage_connectivity() -> dict:
    """
    Check storage connectivity and return status information.
    
    Used by health check endpoints to verify storage is accessible.
    
    Returns:
        Dict with storage status information
        
    Raises:
        Exception: If storage is not accessible
    """
    storage = get_storage_client()
    
    try:
        # Attempt to list buckets as a connectivity test
        buckets = storage.minio_client.list_buckets()
        bucket_count = len(buckets)
        
        # Verify expected buckets exist
        existing_buckets = {b.name for b in buckets}
        missing_buckets = [name for name in BUCKETS.keys() if name not in existing_buckets]
        
        return {
            "accessible": True,
            "bucket_count": bucket_count,
            "expected_buckets": len(BUCKETS),
            "missing_buckets": missing_buckets,
            "healthy": len(missing_buckets) == 0,
        }
    except Exception as e:
        logger.error(f"Storage connectivity check failed: {e}")
        raise Exception(f"Storage not accessible: {str(e)}") from e

