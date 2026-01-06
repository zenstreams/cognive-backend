"""
Celery Application Configuration for Cognive Control Plane.

This module configures Celery with RabbitMQ as the message broker
and Redis as the result backend.

Features:
- Task routing to specific queues
- Dead letter queue (DLQ) support
- Task retry policies
- Result expiration
- Monitoring via Flower
"""

from celery import Celery
from kombu import Exchange, Queue

from app.core.config import settings
from app.core.messaging import DLX_EXCHANGE, QUEUE_CONFIGS, QueueName

# =============================================================================
# Celery Application Instance
# =============================================================================

app = Celery(
    "cognive",
    broker=settings.rabbitmq_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.agent_tasks",
        "app.tasks.llm_tasks",
        "app.tasks.budget_tasks",
    ],
)

# =============================================================================
# Celery Configuration
# =============================================================================

def _build_task_queues() -> list[Queue]:
    """Build Celery queues from the shared queue config to keep DLQ/TTL in sync."""
    queues: list[Queue] = []
    for cfg in QUEUE_CONFIGS.values():
        exchange = Exchange(cfg.exchange, type="direct", durable=cfg.durable)
        queues.append(
            Queue(
                cfg.name,
                exchange=exchange,
                routing_key=cfg.routing_key,
                durable=cfg.durable,
                queue_arguments={
                    "x-dead-letter-exchange": DLX_EXCHANGE,
                    "x-dead-letter-routing-key": cfg.dlq_routing_key,
                    "x-message-ttl": cfg.message_ttl,
                },
            )
        )
    return queues


app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue=QueueName.AGENT_RUNS_EVENTS.value,
    
    # Queue routing
    task_routes={
        "app.tasks.agent_tasks.*": {"queue": QueueName.AGENT_RUNS_EVENTS.value},
        "app.tasks.llm_tasks.*": {"queue": QueueName.AGENT_LLM_CALLS.value},
        "app.tasks.budget_tasks.*": {"queue": QueueName.BUDGET_ALERTS.value},
        # Reserved for tool invocation pipelines if/when tasks are added
        "app.tasks.tool_tasks.*": {"queue": QueueName.AGENT_TOOL_INVOCATIONS.value},
    },
    task_queues=_build_task_queues(),
    
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,  # Store additional task metadata
    
    # Task execution settings
    task_acks_late=True,  # Acknowledge after task completes (for reliability)
    task_reject_on_worker_lost=True,  # Reject task if worker dies
    worker_prefetch_multiplier=1,  # Fair task distribution
    
    # Task retry defaults
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    
    # Beat scheduler (for periodic tasks)
    beat_schedule={
        # Example: Check budget alerts every minute
        # "check-budget-alerts": {
        #     "task": "app.tasks.budget_tasks.check_budget_alerts",
        #     "schedule": 60.0,
        # },
    },
)

# =============================================================================
# Celery Signals
# =============================================================================

@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery connectivity."""
    print(f"Request: {self.request!r}")
    return {"status": "ok", "worker": self.request.hostname}

