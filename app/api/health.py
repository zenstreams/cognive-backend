"""Health check endpoints for Kubernetes probes and monitoring."""

from fastapi import APIRouter, HTTPException, status

from app.core.cache import cache_metrics, check_redis_connectivity, get_cache_info
from app.core.config import settings
from app.core.database import check_database_connectivity_async
from app.core.storage import check_storage_connectivity
from app.core.utils import mask_credentials
from app.schemas.health import (
    CacheMetricsResponse,
    LivenessResponse,
    ReadinessResponse,
    ReplicationStatusResponse,
    StorageHealthResponse,
)

router = APIRouter()


@router.get(
    "/liveness",
    summary="Lightweight liveness probe",
    description="Kubernetes liveness probe endpoint. Returns immediately if the process is running. "
    "Use this for container orchestration health checks.",
    response_model=LivenessResponse,
    responses={
        200: {
            "description": "Process is running",
            "content": {"application/json": {"example": {"status": "alive"}}},
        }
    },
)
async def liveness():
    """Lightweight probe to confirm the app process is alive.

    This endpoint performs no I/O and returns immediately, making it suitable
    for high-frequency health checks by load balancers and orchestrators.
    """
    return {"status": "alive"}


@router.get(
    "/readiness",
    summary="Readiness probe with dependency hints",
    description="Kubernetes readiness probe endpoint. Returns configured dependencies with "
    "credentials masked for security. Use this to verify the service can accept traffic.",
    response_model=ReadinessResponse,
    responses={
        200: {
            "description": "Service is ready and dependencies are configured",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ready",
                        "dependencies": {
                            "database_url": "postgresql://postgres:***@postgres:5432/cognive",
                            "redis_url": "redis://redis:6379/0",
                            "rabbitmq_url": "amqp://guest:***@rabbitmq:5672//",
                            "storage_endpoint": "http://minio:9000",
                        },
                    }
                }
            },
        },
        503: {
            "description": "Service not ready",
            "content": {"application/json": {"example": {"detail": "Not ready"}}},
        },
    },
)
async def readiness():
    """Readiness probe that returns configured dependencies with masked credentials.

    All connection strings have their passwords masked to prevent credential
    exposure in logs, monitoring systems, or API responses.
    """
    try:
        await check_database_connectivity_async()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Not ready (database unavailable): {exc}",
        ) from exc

    try:
        await check_redis_connectivity()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Not ready (redis unavailable): {exc}",
        ) from exc

    try:
        await check_storage_connectivity()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Not ready (storage unavailable): {exc}",
        ) from exc

    return {
        "status": "ready",
        "dependencies": {
            "database_url": mask_credentials(settings.database_url_async),
            "redis_url": mask_credentials(settings.redis_url),
            "rabbitmq_url": mask_credentials(settings.rabbitmq_url),
            "storage_endpoint": settings.storage_endpoint,
        },
    }


@router.get(
    "/cache",
    summary="Cache metrics and Redis info",
    description="Returns cache hit/miss metrics and Redis server information for monitoring.",
    response_model=CacheMetricsResponse,
    responses={
        200: {
            "description": "Cache metrics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "hits": 1500,
                        "misses": 300,
                        "errors": 2,
                        "total": 1800,
                        "hit_rate_percent": 83.33,
                        "redis_info": {
                            "used_memory_human": "1.5M",
                            "used_memory_peak_human": "2.0M",
                            "maxmemory_human": "4G",
                            "connected_clients": 10,
                        },
                    }
                }
            },
        },
    },
)
async def cache_health():
    """Get cache metrics and Redis server information.

    Provides observability into cache performance including hit/miss rates
    and Redis memory usage.
    """
    metrics = cache_metrics.to_dict()
    redis_info = await get_cache_info()

    return {
        **metrics,
        "redis_info": redis_info,
    }


@router.get(
    "/storage",
    summary="Object storage health and bucket information",
    description="Returns storage connectivity status, bucket counts, and health information for MinIO/S3.",
    response_model=StorageHealthResponse,
    responses={
        200: {
            "description": "Storage health retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "endpoint": "http://minio:9000",
                        "accessible": True,
                        "bucket_count": 4,
                        "expected_buckets": 4,
                        "missing_buckets": [],
                        "buckets": [
                            {"name": "agent-artifacts", "created": "2024-01-01T00:00:00Z"},
                            {"name": "execution-replay-data", "created": "2024-01-01T00:00:00Z"},
                            {"name": "report-exports", "created": "2024-01-01T00:00:00Z"},
                            {"name": "audit-logs-archive", "created": "2024-01-01T00:00:00Z"},
                        ],
                    }
                }
            },
        },
        503: {
            "description": "Storage not accessible",
            "content": {"application/json": {"example": {"detail": "Storage unavailable"}}},
        },
    },
)
async def storage_health():
    """Get detailed storage health information including bucket status.
    
    Verifies storage connectivity and provides information about
    configured buckets for monitoring and debugging.
    """
    try:
        storage_info = await check_storage_connectivity()
        
        # Get bucket details
        from app.core.storage import get_storage_client
        
        storage = get_storage_client()
        buckets = storage.minio_client.list_buckets()
        bucket_list = [
            {"name": bucket.name, "created": bucket.creation_date.isoformat()}
            for bucket in buckets
        ]
        
        return {
            "status": "healthy" if storage_info["healthy"] else "degraded",
            "endpoint": settings.storage_endpoint,
            **storage_info,
            "buckets": bucket_list,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Storage unavailable: {exc}",
        ) from exc


@router.get(
    "/replication",
    summary="Replication lag and read-replica checks",
    description="Checks primary vs replica roles and reports estimated replication lag from each configured read replica.",
    response_model=ReplicationStatusResponse,
    responses={
        200: {"description": "Replication status retrieved"},
        503: {"description": "Replication checks failed"},
    },
)
async def replication_status():
    # We implement this endpoint using lightweight SQL calls to avoid pulling in ORM models.
    from sqlalchemy import text

    from app.core.database import async_write_engine, get_async_read_engine_entries

    async with async_write_engine.connect() as conn:
        primary_in_recovery = bool((await conn.execute(text("SELECT pg_is_in_recovery()"))).scalar())

    replicas: list[dict] = []
    degraded = False

    for url, replica_engine in get_async_read_engine_entries():
        masked = mask_credentials(url)
        try:
            async with replica_engine.connect() as conn:
                in_recovery = bool((await conn.execute(text("SELECT pg_is_in_recovery()"))).scalar())
                # On replicas, pg_last_xact_replay_timestamp() should be non-null when replaying.
                lag_ms = (
                    await conn.execute(
                        text(
                            "SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) * 1000"
                        )
                    )
                ).scalar()
                lag_ms_val = float(lag_ms) if lag_ms is not None else None
                if lag_ms_val is None:
                    degraded = True
                replicas.append({"url": masked, "in_recovery": in_recovery, "lag_ms": lag_ms_val})
        except Exception:
            degraded = True
            replicas.append({"url": masked, "in_recovery": False, "lag_ms": None})

    if primary_in_recovery:
        degraded = True

    return {
        "status": "degraded" if degraded else "ok",
        "primary_in_recovery": primary_in_recovery,
        "replicas": replicas,
    }
