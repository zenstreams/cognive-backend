"""Pydantic schemas for health check endpoints."""

from typing import Any

from pydantic import BaseModel, Field


class LivenessResponse(BaseModel):
    """Response model for liveness probe."""

    status: str = Field(..., description="Alive indicator (always 'alive' when responding)")


class ReadinessDependencies(BaseModel):
    """Dependency status for readiness checks."""

    database_url: str = Field(..., description="Configured PostgreSQL connection string (masked)")
    redis_url: str = Field(..., description="Configured Redis connection string (masked)")
    rabbitmq_url: str = Field(..., description="Configured RabbitMQ connection string (masked)")
    storage_endpoint: str = Field(..., description="Configured object storage endpoint (MinIO/S3)")


class ReadinessResponse(BaseModel):
    """Response model for readiness probe."""

    status: str = Field(..., description="Readiness indicator (ready when dependencies resolve)")
    dependencies: ReadinessDependencies


class CacheMetricsResponse(BaseModel):
    """Response model for cache metrics."""

    hits: int = Field(..., description="Total cache hits")
    misses: int = Field(..., description="Total cache misses")
    errors: int = Field(..., description="Total cache errors")
    total: int = Field(..., description="Total cache operations")
    hit_rate_percent: float = Field(..., description="Cache hit rate percentage")
    redis_info: dict[str, Any] = Field(..., description="Redis server information")


class ReplicaLag(BaseModel):
    """Replication lag metrics for a single replica connection."""

    url: str = Field(..., description="Replica connection string (masked)")
    in_recovery: bool = Field(..., description="True when connected node is a standby/replica")
    lag_ms: float | None = Field(
        default=None,
        description="Estimated replication lag in milliseconds (null when unavailable)",
    )


class ReplicationStatusResponse(BaseModel):
    """Response model for replication health/lag checks."""

    status: str = Field(..., description="ok when checks succeed; degraded when lag/unavailable")
    primary_in_recovery: bool = Field(..., description="Should be false for the primary/write DB")
    replicas: list[ReplicaLag] = Field(default_factory=list, description="Replica lag metrics")


class BucketInfo(BaseModel):
    """Information about a storage bucket."""

    name: str = Field(..., description="Bucket name")
    created: str = Field(..., description="Bucket creation timestamp (ISO format)")


class StorageHealthResponse(BaseModel):
    """Response model for storage health checks."""

    status: str = Field(..., description="Storage health status (healthy/degraded)")
    endpoint: str = Field(..., description="Storage endpoint URL")
    accessible: bool = Field(..., description="True if storage is accessible")
    bucket_count: int = Field(..., description="Number of buckets found")
    expected_buckets: int = Field(..., description="Number of expected buckets")
    missing_buckets: list[str] = Field(default_factory=list, description="List of missing bucket names")
    healthy: bool = Field(..., description="True if all expected buckets exist")
    buckets: list[BucketInfo] = Field(default_factory=list, description="List of buckets with details")

