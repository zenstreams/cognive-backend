"""Prometheus metrics instrumentation for Cognive Control Plane.

This module provides:
- FastAPI request/response metrics (latency, count, size)
- Custom business metrics (agent runs, LLM calls, costs)
- Database connection pool metrics
- Cache metrics export
- Celery task metrics
"""

import logging
from typing import Callable

from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram, Info
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from prometheus_fastapi_instrumentator.metrics import Info as MetricInfo

logger = logging.getLogger(__name__)

# =============================================================================
# Application Info Metric
# =============================================================================

APP_INFO = Info(
    "cognive_app",
    "Cognive Control Plane application information",
)

# =============================================================================
# Custom Business Metrics
# =============================================================================

# Agent Execution Metrics
AGENT_RUNS_TOTAL = Counter(
    "cognive_agent_runs_total",
    "Total number of agent runs",
    ["agent_id", "status"],
)

AGENT_RUN_DURATION = Histogram(
    "cognive_agent_run_duration_seconds",
    "Agent run duration in seconds",
    ["agent_id"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
)

ACTIVE_AGENT_RUNS = Gauge(
    "cognive_active_agent_runs",
    "Number of currently active agent runs",
    ["agent_id"],
)

# LLM Call Metrics
LLM_CALLS_TOTAL = Counter(
    "cognive_llm_calls_total",
    "Total number of LLM API calls",
    ["provider", "model", "status"],
)

LLM_CALL_DURATION = Histogram(
    "cognive_llm_call_duration_seconds",
    "LLM API call duration in seconds",
    ["provider", "model"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

LLM_TOKENS_TOTAL = Counter(
    "cognive_llm_tokens_total",
    "Total LLM tokens consumed",
    ["provider", "model", "token_type"],  # token_type: input, output
)

# Cost Metrics
COST_TOTAL = Counter(
    "cognive_cost_total_usd",
    "Total cost in USD",
    ["tenant_id", "cost_type"],  # cost_type: llm, storage, compute
)

BUDGET_REMAINING = Gauge(
    "cognive_budget_remaining_usd",
    "Remaining budget in USD",
    ["tenant_id", "budget_type"],
)

# Tool Invocation Metrics
TOOL_INVOCATIONS_TOTAL = Counter(
    "cognive_tool_invocations_total",
    "Total number of tool invocations",
    ["tool_name", "status"],
)

TOOL_INVOCATION_DURATION = Histogram(
    "cognive_tool_invocation_duration_seconds",
    "Tool invocation duration in seconds",
    ["tool_name"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# =============================================================================
# Infrastructure Metrics
# =============================================================================

# Database Metrics
DB_CONNECTIONS_ACTIVE = Gauge(
    "cognive_db_connections_active",
    "Number of active database connections",
    ["pool"],
)

DB_CONNECTIONS_IDLE = Gauge(
    "cognive_db_connections_idle",
    "Number of idle database connections",
    ["pool"],
)

DB_QUERY_DURATION = Histogram(
    "cognive_db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"],  # select, insert, update, delete
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

# Cache Metrics (exported from cache.py)
CACHE_HITS = Counter(
    "cognive_cache_hits_total",
    "Total cache hits",
)

CACHE_MISSES = Counter(
    "cognive_cache_misses_total",
    "Total cache misses",
)

CACHE_ERRORS = Counter(
    "cognive_cache_errors_total",
    "Total cache errors",
)

# Message Queue Metrics
MQ_MESSAGES_PUBLISHED = Counter(
    "cognive_mq_messages_published_total",
    "Total messages published to queue",
    ["queue", "exchange"],
)

MQ_MESSAGES_CONSUMED = Counter(
    "cognive_mq_messages_consumed_total",
    "Total messages consumed from queue",
    ["queue"],
)

MQ_MESSAGES_FAILED = Counter(
    "cognive_mq_messages_failed_total",
    "Total failed message processing",
    ["queue", "reason"],
)

# Celery Task Metrics
CELERY_TASKS_TOTAL = Counter(
    "cognive_celery_tasks_total",
    "Total Celery tasks executed",
    ["task_name", "status"],  # status: success, failure, retry
)

CELERY_TASK_DURATION = Histogram(
    "cognive_celery_task_duration_seconds",
    "Celery task execution duration",
    ["task_name"],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0),
)

CELERY_TASKS_QUEUED = Gauge(
    "cognive_celery_tasks_queued",
    "Number of tasks currently queued",
    ["queue"],
)


# =============================================================================
# Custom Metric Functions for Instrumentator
# =============================================================================


def http_requests_by_path() -> Callable[[MetricInfo], None]:
    """Track HTTP requests with detailed path labels."""
    REQUESTS = Counter(
        "cognive_http_requests_by_path_total",
        "HTTP requests by path",
        ["method", "path", "status"],
    )

    def instrumentation(info: MetricInfo) -> None:
        # Normalize path to avoid high cardinality
        path = info.request.url.path
        # Replace UUIDs and numeric IDs with placeholders
        import re
        path = re.sub(r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "/{uuid}", path)
        path = re.sub(r"/\d+", "/{id}", path)
        
        REQUESTS.labels(
            method=info.request.method,
            path=path,
            status=info.response.status_code if info.response else 0,
        ).inc()

    return instrumentation


def response_size() -> Callable[[MetricInfo], None]:
    """Track response sizes."""
    SIZE = Histogram(
        "cognive_http_response_size_bytes",
        "HTTP response size in bytes",
        ["method", "path"],
        buckets=(100, 1000, 10000, 100000, 1000000, 10000000),
    )

    def instrumentation(info: MetricInfo) -> None:
        if info.response:
            content_length = info.response.headers.get("content-length")
            if content_length:
                import re
                path = info.request.url.path
                path = re.sub(r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "/{uuid}", path)
                path = re.sub(r"/\d+", "/{id}", path)
                SIZE.labels(
                    method=info.request.method,
                    path=path,
                ).observe(int(content_length))

    return instrumentation


# =============================================================================
# Instrumentator Setup
# =============================================================================


def setup_metrics(app: FastAPI, app_version: str = "0.1.0") -> Instrumentator:
    """Configure and attach Prometheus metrics to FastAPI application.

    Args:
        app: FastAPI application instance.
        app_version: Application version string.

    Returns:
        Configured Instrumentator instance.
    """
    # Set application info
    APP_INFO.info({
        "version": app_version,
        "name": "cognive-control-plane",
    })

    # Create instrumentator with configuration
    # Note: should_respect_env_var=False because we check settings.enable_metrics in main.py
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        should_instrument_requests_inprogress=True,
        excluded_handlers=[
            "/metrics",
            "/health",
            "/api/v1/health/live",
            "/api/v1/health/ready",
        ],
        inprogress_name="cognive_http_requests_inprogress",
        inprogress_labels=True,
    )

    # Add custom metrics
    instrumentator.add(http_requests_by_path())
    instrumentator.add(response_size())

    # Instrument the app
    instrumentator.instrument(app)

    # Expose metrics endpoint
    instrumentator.expose(
        app,
        endpoint="/metrics",
        include_in_schema=True,
        tags=["monitoring"],
    )

    logger.info("✅ Prometheus metrics instrumentation configured")
    
    return instrumentator


# =============================================================================
# Helper Functions for Recording Metrics
# =============================================================================


def record_agent_run_start(agent_id: str) -> None:
    """Record the start of an agent run."""
    ACTIVE_AGENT_RUNS.labels(agent_id=agent_id).inc()


def record_agent_run_end(
    agent_id: str,
    status: str,
    duration_seconds: float,
) -> None:
    """Record the completion of an agent run."""
    AGENT_RUNS_TOTAL.labels(agent_id=agent_id, status=status).inc()
    AGENT_RUN_DURATION.labels(agent_id=agent_id).observe(duration_seconds)
    ACTIVE_AGENT_RUNS.labels(agent_id=agent_id).dec()


def record_llm_call(
    provider: str,
    model: str,
    status: str,
    duration_seconds: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """Record an LLM API call."""
    LLM_CALLS_TOTAL.labels(provider=provider, model=model, status=status).inc()
    LLM_CALL_DURATION.labels(provider=provider, model=model).observe(duration_seconds)
    
    if input_tokens > 0:
        LLM_TOKENS_TOTAL.labels(
            provider=provider,
            model=model,
            token_type="input",
        ).inc(input_tokens)
    
    if output_tokens > 0:
        LLM_TOKENS_TOTAL.labels(
            provider=provider,
            model=model,
            token_type="output",
        ).inc(output_tokens)


def record_tool_invocation(
    tool_name: str,
    status: str,
    duration_seconds: float,
) -> None:
    """Record a tool invocation."""
    TOOL_INVOCATIONS_TOTAL.labels(tool_name=tool_name, status=status).inc()
    TOOL_INVOCATION_DURATION.labels(tool_name=tool_name).observe(duration_seconds)


def record_cost(
    tenant_id: str,
    cost_type: str,
    amount_usd: float,
) -> None:
    """Record a cost event."""
    COST_TOTAL.labels(tenant_id=tenant_id, cost_type=cost_type).inc(amount_usd)


def update_budget_remaining(
    tenant_id: str,
    budget_type: str,
    remaining_usd: float,
) -> None:
    """Update remaining budget gauge."""
    BUDGET_REMAINING.labels(tenant_id=tenant_id, budget_type=budget_type).set(remaining_usd)


def record_celery_task(
    task_name: str,
    status: str,
    duration_seconds: float,
) -> None:
    """Record a Celery task execution."""
    CELERY_TASKS_TOTAL.labels(task_name=task_name, status=status).inc()
    CELERY_TASK_DURATION.labels(task_name=task_name).observe(duration_seconds)


def record_mq_publish(queue: str, exchange: str = "") -> None:
    """Record a message publish event."""
    MQ_MESSAGES_PUBLISHED.labels(queue=queue, exchange=exchange).inc()


def record_mq_consume(queue: str) -> None:
    """Record a message consume event."""
    MQ_MESSAGES_CONSUMED.labels(queue=queue).inc()


def record_mq_failure(queue: str, reason: str) -> None:
    """Record a message processing failure."""
    MQ_MESSAGES_FAILED.labels(queue=queue, reason=reason).inc()


def record_cache_hit() -> None:
    """Record a cache hit."""
    CACHE_HITS.inc()


def record_cache_miss() -> None:
    """Record a cache miss."""
    CACHE_MISSES.inc()


def record_cache_error() -> None:
    """Record a cache error."""
    CACHE_ERRORS.inc()


def update_db_pool_metrics(active: int, idle: int, pool: str = "primary") -> None:
    """Update database connection pool metrics."""
    DB_CONNECTIONS_ACTIVE.labels(pool=pool).set(active)
    DB_CONNECTIONS_IDLE.labels(pool=pool).set(idle)


