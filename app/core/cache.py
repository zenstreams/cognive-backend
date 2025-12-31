"""Redis cache setup for Cognive Control Plane.

This module provides:
- Connection pooling via redis-py
- Cache utility functions with TTL management
- Cache hit/miss metrics tracking
- Typed cache operations for common use cases

Use Cases:
- LLM pricing data cache (TTL: 1 hour)
- Budget remaining calculations (real-time)
- Agent configuration cache
- API rate limiting counters
- Session management
"""

from __future__ import annotations

import json
import logging
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool

from app.core.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Cache Key Prefixes
# =============================================================================


class CachePrefix(str, Enum):
    """Standardized cache key prefixes for namespace separation."""

    LLM_PRICING = "llm_price"
    AGENT_CONFIG = "agent_config"
    BUDGET = "budget"
    RATE_LIMIT = "rate_limit"
    SESSION = "session"


# =============================================================================
# Cache Metrics
# =============================================================================


@dataclass
class CacheMetrics:
    """Thread-safe, process-local cache metrics tracker.

    Tracks hit/miss counts for monitoring and observability.
    In production, these should be exported to Prometheus/Grafana.

    Note: these counters live in-process. If you run multiple Uvicorn/Gunicorn
    workers, each worker will report its own counters unless you aggregate them
    externally.
    """

    hits: int = field(default=0)
    misses: int = field(default=0)
    errors: int = field(default=0)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    @property
    def total(self) -> int:
        """Total cache operations (hits + misses)."""
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        """Cache hit rate as a percentage (0.0 to 100.0)."""
        if self.total == 0:
            return 0.0
        return (self.hits / self.total) * 100.0

    def record_hit(self) -> None:
        """Record a cache hit."""
        with self._lock:
            self.hits += 1

    def record_miss(self) -> None:
        """Record a cache miss."""
        with self._lock:
            self.misses += 1

    def record_error(self) -> None:
        """Record a cache error."""
        with self._lock:
            self.errors += 1

    def reset(self) -> None:
        """Reset all metrics to zero."""
        with self._lock:
            self.hits = 0
            self.misses = 0
            self.errors = 0

    def to_dict(self) -> dict[str, Any]:
        """Export metrics as dictionary for API responses."""
        with self._lock:
            hits = self.hits
            misses = self.misses
            errors = self.errors

        total = hits + misses
        hit_rate = 0.0 if total == 0 else (hits / total) * 100.0
        return {
            "hits": hits,
            "misses": misses,
            "errors": errors,
            "total": total,
            "hit_rate_percent": round(hit_rate, 2),
        }


# Global metrics instance
cache_metrics = CacheMetrics()


# =============================================================================
# Connection Pool Setup
# =============================================================================


def create_redis_pool() -> ConnectionPool:
    """Create a Redis connection pool with configured settings.

    Returns:
        ConnectionPool configured for production use.
    """
    return ConnectionPool.from_url(
        settings.redis_url,
        max_connections=settings.redis_max_connections,
        socket_timeout=settings.redis_socket_timeout,
        socket_connect_timeout=settings.redis_socket_connect_timeout,
        decode_responses=True,
    )


# Global connection pool - lazy initialization
_redis_pool: ConnectionPool | None = None


def get_redis_pool() -> ConnectionPool:
    """Get or create the global Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = create_redis_pool()
    return _redis_pool


def get_redis_client() -> redis.Redis:
    """Get a Redis client using the shared connection pool.

    Returns:
        Redis client configured with connection pooling.
    """
    return redis.Redis(connection_pool=get_redis_pool())


@asynccontextmanager
async def redis_client() -> AsyncGenerator[redis.Redis, None]:
    """Async context manager for Redis client with automatic cleanup.

    Usage:
        async with redis_client() as cache:
            await cache.get("my_key")
    """
    client = get_redis_client()
    try:
        yield client
    finally:
        await client.close()


# =============================================================================
# Cache Operations
# =============================================================================


class CacheService:
    """High-level cache service with metrics tracking.

    Provides typed operations for common caching patterns with
    automatic hit/miss tracking and error handling.
    """

    def __init__(self, client: redis.Redis | None = None):
        """Initialize cache service.

        Args:
            client: Optional Redis client. Uses default pool if not provided.
        """
        self._client = client

    @property
    def client(self) -> redis.Redis:
        """Get Redis client, creating one if needed."""
        if self._client is None:
            self._client = get_redis_client()
        return self._client

    @staticmethod
    def _make_key(prefix: CachePrefix | str, key: str) -> str:
        """Build namespaced cache key."""
        prefix_str = prefix.value if isinstance(prefix, CachePrefix) else prefix
        return f"{prefix_str}:{key}"

    async def get(self, prefix: CachePrefix | str, key: str) -> str | None:
        """Get a cached value.

        Args:
            prefix: Cache key prefix for namespace separation.
            key: Unique identifier within the prefix namespace.

        Returns:
            Cached string value or None if not found.
        """
        cache_key = self._make_key(prefix, key)
        try:
            value = await self.client.get(cache_key)
            if value is not None:
                cache_metrics.record_hit()
                logger.debug("Cache HIT: %s", cache_key)
            else:
                cache_metrics.record_miss()
                logger.debug("Cache MISS: %s", cache_key)
            return value
        except Exception as exc:
            cache_metrics.record_error()
            logger.warning("Cache GET error for %s: %s", cache_key, exc)
            return None

    async def get_json(self, prefix: CachePrefix | str, key: str) -> dict | list | None:
        """Get a cached JSON value, deserialized.

        Args:
            prefix: Cache key prefix for namespace separation.
            key: Unique identifier within the prefix namespace.

        Returns:
            Deserialized JSON object or None if not found.
        """
        value = await self.get(prefix, key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            logger.warning("Cache JSON decode error for %s:%s: %s", prefix, key, exc)
            return None

    async def set(
        self,
        prefix: CachePrefix | str,
        key: str,
        value: str,
        ttl: int | None = None,
    ) -> bool:
        """Set a cached value with optional TTL.

        Args:
            prefix: Cache key prefix for namespace separation.
            key: Unique identifier within the prefix namespace.
            value: String value to cache.
            ttl: Time-to-live in seconds. None for no expiry.

        Returns:
            True if successfully set, False otherwise.
        """
        cache_key = self._make_key(prefix, key)
        try:
            if ttl:
                await self.client.setex(cache_key, ttl, value)
            else:
                await self.client.set(cache_key, value)
            logger.debug("Cache SET: %s (TTL: %s)", cache_key, ttl or "none")
            return True
        except Exception as exc:
            cache_metrics.record_error()
            logger.warning("Cache SET error for %s: %s", cache_key, exc)
            return False

    async def set_json(
        self,
        prefix: CachePrefix | str,
        key: str,
        value: dict | list,
        ttl: int | None = None,
    ) -> bool:
        """Set a cached JSON value with optional TTL.

        Args:
            prefix: Cache key prefix for namespace separation.
            key: Unique identifier within the prefix namespace.
            value: JSON-serializable dict or list.
            ttl: Time-to-live in seconds. None for no expiry.

        Returns:
            True if successfully set, False otherwise.
        """
        try:
            json_str = json.dumps(value)
            return await self.set(prefix, key, json_str, ttl)
        except (TypeError, ValueError) as exc:
            logger.warning("Cache JSON encode error for %s:%s: %s", prefix, key, exc)
            return False

    async def delete(self, prefix: CachePrefix | str, key: str) -> bool:
        """Delete a cached value.

        Args:
            prefix: Cache key prefix for namespace separation.
            key: Unique identifier within the prefix namespace.

        Returns:
            True if key was deleted, False otherwise.
        """
        cache_key = self._make_key(prefix, key)
        try:
            result = await self.client.delete(cache_key)
            logger.debug("Cache DELETE: %s (found: %s)", cache_key, bool(result))
            return bool(result)
        except Exception as exc:
            cache_metrics.record_error()
            logger.warning("Cache DELETE error for %s: %s", cache_key, exc)
            return False

    async def exists(self, prefix: CachePrefix | str, key: str) -> bool:
        """Check if a key exists in cache.

        Args:
            prefix: Cache key prefix for namespace separation.
            key: Unique identifier within the prefix namespace.

        Returns:
            True if key exists, False otherwise.
        """
        cache_key = self._make_key(prefix, key)
        try:
            return bool(await self.client.exists(cache_key))
        except Exception as exc:
            cache_metrics.record_error()
            logger.warning("Cache EXISTS error for %s: %s", cache_key, exc)
            return False

    async def increment(self, prefix: CachePrefix | str, key: str, amount: int = 1) -> int | None:
        """Increment a counter in cache.

        Useful for rate limiting and usage tracking.

        Args:
            prefix: Cache key prefix for namespace separation.
            key: Unique identifier within the prefix namespace.
            amount: Amount to increment by.

        Returns:
            New counter value or None on error.
        """
        cache_key = self._make_key(prefix, key)
        try:
            result = await self.client.incrby(cache_key, amount)
            return result
        except Exception as exc:
            cache_metrics.record_error()
            logger.warning("Cache INCR error for %s: %s", cache_key, exc)
            return None

    async def expire(self, prefix: CachePrefix | str, key: str, ttl: int) -> bool:
        """Set expiry on an existing key.

        Args:
            prefix: Cache key prefix for namespace separation.
            key: Unique identifier within the prefix namespace.
            ttl: Time-to-live in seconds.

        Returns:
            True if expiry was set, False otherwise.
        """
        cache_key = self._make_key(prefix, key)
        try:
            return bool(await self.client.expire(cache_key, ttl))
        except Exception as exc:
            cache_metrics.record_error()
            logger.warning("Cache EXPIRE error for %s: %s", cache_key, exc)
            return False

    async def get_ttl(self, prefix: CachePrefix | str, key: str) -> int:
        """Get remaining TTL for a key.

        Args:
            prefix: Cache key prefix for namespace separation.
            key: Unique identifier within the prefix namespace.

        Returns:
            TTL in seconds, -1 if no expiry, -2 if key doesn't exist.
        """
        cache_key = self._make_key(prefix, key)
        try:
            return await self.client.ttl(cache_key)
        except Exception as exc:
            cache_metrics.record_error()
            logger.warning("Cache TTL error for %s: %s", cache_key, exc)
            return -2

    async def close(self) -> None:
        """Close the Redis client connection."""
        if self._client:
            await self._client.close()
            self._client = None


# =============================================================================
# Domain-Specific Cache Helpers
# =============================================================================


async def cache_llm_pricing(model: str, pricing: dict[str, float]) -> bool:
    """Cache LLM pricing data.

    Args:
        model: Model identifier (e.g., "gpt-4", "claude-3-opus").
        pricing: Pricing dict with 'input' and 'output' costs per 1K tokens.

    Returns:
        True if successfully cached.
    """
    cache = CacheService()
    try:
        return await cache.set_json(
            CachePrefix.LLM_PRICING,
            model,
            pricing,
            ttl=settings.cache_ttl_llm_pricing,
        )
    finally:
        await cache.close()


async def get_llm_pricing(model: str) -> dict[str, float] | None:
    """Get cached LLM pricing data.

    Args:
        model: Model identifier (e.g., "gpt-4", "claude-3-opus").

    Returns:
        Pricing dict or None if not cached.
    """
    cache = CacheService()
    try:
        result = await cache.get_json(CachePrefix.LLM_PRICING, model)
        return result if isinstance(result, dict) else None
    finally:
        await cache.close()


async def cache_agent_config(agent_id: str, config: dict) -> bool:
    """Cache agent configuration.

    Args:
        agent_id: Unique agent identifier.
        config: Agent configuration dict.

    Returns:
        True if successfully cached.
    """
    cache = CacheService()
    try:
        return await cache.set_json(
            CachePrefix.AGENT_CONFIG,
            agent_id,
            config,
            ttl=settings.cache_ttl_agent_config,
        )
    finally:
        await cache.close()


async def get_agent_config(agent_id: str) -> dict | None:
    """Get cached agent configuration.

    Args:
        agent_id: Unique agent identifier.

    Returns:
        Agent config dict or None if not cached.
    """
    cache = CacheService()
    try:
        result = await cache.get_json(CachePrefix.AGENT_CONFIG, agent_id)
        return result if isinstance(result, dict) else None
    finally:
        await cache.close()


async def invalidate_agent_config(agent_id: str) -> bool:
    """Invalidate cached agent configuration.

    Args:
        agent_id: Unique agent identifier.

    Returns:
        True if successfully invalidated.
    """
    cache = CacheService()
    try:
        return await cache.delete(CachePrefix.AGENT_CONFIG, agent_id)
    finally:
        await cache.close()


# =============================================================================
# Rate Limiting Helpers
# =============================================================================


async def check_rate_limit(
    identifier: str,
    limit: int,
    window_seconds: int,
) -> tuple[bool, int]:
    """Check and update rate limit counter.

    Uses sliding window counter pattern.

    Args:
        identifier: Unique identifier (e.g., "api_key:abc123" or "ip:1.2.3.4").
        limit: Maximum allowed requests in the window.
        window_seconds: Time window in seconds.

    Returns:
        Tuple of (allowed: bool, current_count: int).
    """
    cache = CacheService()
    try:
        current = await cache.increment(CachePrefix.RATE_LIMIT, identifier)
        if current is None:
            # Error occurred, fail open (allow request)
            return True, 0

        if current == 1:
            # First request in window, set expiry
            await cache.expire(CachePrefix.RATE_LIMIT, identifier, window_seconds)

        allowed = current <= limit
        return allowed, current
    finally:
        await cache.close()


# =============================================================================
# Health Check
# =============================================================================


async def check_redis_connectivity() -> None:
    """Check Redis connectivity for health probes.

    Raises:
        Exception: If Redis is unreachable.
    """
    cache = CacheService()
    try:
        await cache.client.ping()
    finally:
        await cache.close()


async def get_cache_info() -> dict[str, Any]:
    """Get Redis server info for monitoring.

    Returns:
        Dict with Redis server stats.
    """
    cache = CacheService()
    try:
        info = await cache.client.info("memory")
        return {
            "used_memory_human": info.get("used_memory_human", "unknown"),
            "used_memory_peak_human": info.get("used_memory_peak_human", "unknown"),
            "maxmemory_human": info.get("maxmemory_human", "unknown"),
            "connected_clients": (await cache.client.info("clients")).get("connected_clients", 0),
        }
    except Exception as exc:
        logger.warning("Failed to get Redis info: %s", exc)
        return {"error": str(exc)}
    finally:
        await cache.close()

