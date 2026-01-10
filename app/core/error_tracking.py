"""Error tracking integration for Cognive Control Plane.

This module provides integration with GlitchTip (Sentry-compatible) for:
- Exception capturing and reporting
- Performance monitoring
- User context tracking
- Custom event logging

GlitchTip is a free, self-hosted alternative to Sentry that uses the
Sentry SDK for client integration.
"""

import logging
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Generator

import sentry_sdk
from fastapi import FastAPI
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.core.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


def init_error_tracking(app: FastAPI | None = None) -> bool:
    """Initialize error tracking with GlitchTip/Sentry.

    Args:
        app: Optional FastAPI application for additional context.

    Returns:
        True if initialization successful, False otherwise.
    """
    dsn = getattr(settings, "glitchtip_dsn", None) or getattr(settings, "sentry_dsn", None)
    
    if not dsn:
        logger.warning(
            "⚠️  Error tracking disabled: GLITCHTIP_DSN or SENTRY_DSN not configured"
        )
        return False

    try:
        # Configure Sentry SDK for GlitchTip
        sentry_sdk.init(
            dsn=dsn,
            environment=settings.environment,
            release=f"cognive-control-plane@{getattr(settings, 'app_version', '0.1.0')}",
            
            # Performance monitoring
            traces_sample_rate=_get_traces_sample_rate(),
            profiles_sample_rate=_get_profiles_sample_rate(),
            
            # Enable tracing for specific operations
            enable_tracing=True,
            
            # Integrations
            integrations=[
                StarletteIntegration(transaction_style="endpoint"),
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                RedisIntegration(),
                CeleryIntegration(),
                AsyncioIntegration(),
                LoggingIntegration(
                    level=logging.INFO,
                    event_level=logging.ERROR,
                ),
            ],
            
            # Data scrubbing
            send_default_pii=False,
            
            # Before send hooks
            before_send=_before_send,
            before_send_transaction=_before_send_transaction,
            
            # Attach stacktrace to messages
            attach_stacktrace=True,
            
            # Include local variables in stack traces (careful in production)
            include_local_variables=settings.environment != "production",
            
            # Max breadcrumbs to store
            max_breadcrumbs=50,
            
            # Debug mode for development
            debug=settings.environment == "development",
        )
        
        # Set default tags
        sentry_sdk.set_tag("service", "cognive-control-plane")
        sentry_sdk.set_tag("component", "api")
        
        logger.info("✅ Error tracking initialized (GlitchTip/Sentry)")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize error tracking: {e}")
        return False


def _get_traces_sample_rate() -> float:
    """Get traces sample rate based on environment."""
    env = settings.environment
    if env == "production":
        return 0.1  # 10% sampling in production
    elif env == "staging":
        return 0.5  # 50% in staging
    return 1.0  # 100% in development


def _get_profiles_sample_rate() -> float:
    """Get profiles sample rate based on environment."""
    env = settings.environment
    if env == "production":
        return 0.05  # 5% profiling in production
    elif env == "staging":
        return 0.2  # 20% in staging
    return 0.5  # 50% in development


def _before_send(event: dict, hint: dict) -> dict | None:
    """Process event before sending to GlitchTip.
    
    Use this to:
    - Filter out unwanted errors
    - Scrub sensitive data
    - Add additional context
    """
    # Filter out health check errors
    if "request" in event:
        url = event["request"].get("url", "")
        if any(path in url for path in ["/health", "/metrics", "/ready", "/live"]):
            return None
    
    # Filter out expected exceptions
    if "exception" in event:
        for exception in event.get("exception", {}).get("values", []):
            exc_type = exception.get("type", "")
            
            # Skip expected client errors
            if exc_type in ["HTTPException", "ValidationError", "RequestValidationError"]:
                # Only send if it's a 5xx error
                status_code = event.get("contexts", {}).get("response", {}).get("status_code", 200)
                if status_code < 500:
                    return None
    
    # Scrub any remaining PII
    event = _scrub_sensitive_data(event)
    
    return event


def _before_send_transaction(event: dict, hint: dict) -> dict | None:
    """Process transaction before sending to GlitchTip."""
    # Filter out noisy transactions
    transaction = event.get("transaction", "")
    
    # Skip health checks and metrics endpoints
    if any(path in transaction for path in ["/health", "/metrics", "/ready", "/live"]):
        return None
    
    return event


def _scrub_sensitive_data(event: dict) -> dict:
    """Scrub sensitive data from event."""
    sensitive_keys = {
        "password", "secret", "token", "api_key", "apikey",
        "authorization", "auth", "credential", "private_key",
        "access_token", "refresh_token", "session",
    }
    
    def scrub_dict(d: dict) -> dict:
        result = {}
        for key, value in d.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                result[key] = "[REDACTED]"
            elif isinstance(value, dict):
                result[key] = scrub_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    scrub_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result
    
    return scrub_dict(event)


# =============================================================================
# Context Management
# =============================================================================


def set_user_context(
    user_id: str | None = None,
    email: str | None = None,
    username: str | None = None,
    tenant_id: str | None = None,
) -> None:
    """Set user context for error tracking.
    
    Args:
        user_id: Unique user identifier.
        email: User email (optional, be careful with PII).
        username: Display name.
        tenant_id: Multi-tenant organization ID.
    """
    user_data = {}
    
    if user_id:
        user_data["id"] = user_id
    if email and settings.environment != "production":
        # Only include email in non-production
        user_data["email"] = email
    if username:
        user_data["username"] = username
    
    if user_data:
        sentry_sdk.set_user(user_data)
    
    if tenant_id:
        sentry_sdk.set_tag("tenant_id", tenant_id)


def clear_user_context() -> None:
    """Clear user context."""
    sentry_sdk.set_user(None)


def set_agent_context(
    agent_id: str,
    agent_name: str | None = None,
    run_id: str | None = None,
) -> None:
    """Set agent execution context.
    
    Args:
        agent_id: Agent identifier.
        agent_name: Human-readable agent name.
        run_id: Current execution run ID.
    """
    sentry_sdk.set_tag("agent_id", agent_id)
    
    if agent_name:
        sentry_sdk.set_tag("agent_name", agent_name)
    
    if run_id:
        sentry_sdk.set_tag("run_id", run_id)


def add_breadcrumb(
    message: str,
    category: str = "custom",
    level: str = "info",
    data: dict[str, Any] | None = None,
) -> None:
    """Add a breadcrumb for debugging context.
    
    Args:
        message: Breadcrumb message.
        category: Category for grouping (e.g., "http", "query", "user").
        level: Severity level (debug, info, warning, error, critical).
        data: Additional data to attach.
    """
    sentry_sdk.add_breadcrumb(
        message=message,
        category=category,
        level=level,
        data=data or {},
    )


# =============================================================================
# Error Capturing
# =============================================================================


def capture_exception(
    exception: Exception | None = None,
    extra: dict[str, Any] | None = None,
    tags: dict[str, str] | None = None,
    level: str = "error",
) -> str | None:
    """Capture an exception and send to GlitchTip.
    
    Args:
        exception: Exception to capture. If None, captures current exception.
        extra: Additional context data.
        tags: Additional tags for filtering.
        level: Severity level.
    
    Returns:
        Event ID if sent successfully, None otherwise.
    """
    with sentry_sdk.push_scope() as scope:
        if extra:
            for key, value in extra.items():
                scope.set_extra(key, value)
        
        if tags:
            for key, value in tags.items():
                scope.set_tag(key, value)
        
        scope.level = level
        
        return sentry_sdk.capture_exception(exception)


def capture_message(
    message: str,
    level: str = "info",
    extra: dict[str, Any] | None = None,
    tags: dict[str, str] | None = None,
) -> str | None:
    """Capture a message and send to GlitchTip.
    
    Args:
        message: Message to capture.
        level: Severity level (debug, info, warning, error, critical).
        extra: Additional context data.
        tags: Additional tags for filtering.
    
    Returns:
        Event ID if sent successfully, None otherwise.
    """
    with sentry_sdk.push_scope() as scope:
        if extra:
            for key, value in extra.items():
                scope.set_extra(key, value)
        
        if tags:
            for key, value in tags.items():
                scope.set_tag(key, value)
        
        return sentry_sdk.capture_message(message, level=level)


# =============================================================================
# Performance Monitoring
# =============================================================================


@contextmanager
def start_transaction(
    name: str,
    op: str = "task",
    description: str | None = None,
) -> Generator[Any, None, None]:
    """Start a performance transaction.
    
    Args:
        name: Transaction name.
        op: Operation type (task, http, db, etc.).
        description: Optional description.
    
    Yields:
        Transaction object.
    """
    with sentry_sdk.start_transaction(
        name=name,
        op=op,
        description=description,
    ) as transaction:
        yield transaction


@contextmanager
def start_span(
    op: str,
    description: str | None = None,
) -> Generator[Any, None, None]:
    """Start a performance span within current transaction.
    
    Args:
        op: Operation type.
        description: Span description.
    
    Yields:
        Span object.
    """
    with sentry_sdk.start_span(op=op, description=description) as span:
        yield span


def track_performance(
    name: str | None = None,
    op: str = "function",
) -> Callable:
    """Decorator to track function performance.
    
    Args:
        name: Transaction name (defaults to function name).
        op: Operation type.
    
    Returns:
        Decorated function.
    """
    def decorator(func: Callable) -> Callable:
        transaction_name = name or f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with start_span(op=op, description=transaction_name):
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with start_span(op=op, description=transaction_name):
                return func(*args, **kwargs)
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# =============================================================================
# Health Check
# =============================================================================


def check_error_tracking_health() -> dict[str, Any]:
    """Check error tracking health status.
    
    Returns:
        Health status dictionary.
    """
    client = sentry_sdk.Hub.current.client
    
    if client is None:
        return {
            "status": "disabled",
            "configured": False,
            "message": "Error tracking not initialized",
        }
    
    dsn = client.dsn
    
    return {
        "status": "healthy",
        "configured": True,
        "dsn_configured": dsn is not None,
        "environment": settings.environment,
    }



