"""
RabbitMQ Messaging Configuration for Cognive Control Plane.

This module provides queue definitions, dead letter queue (DLQ) setup,
and utilities for direct RabbitMQ access via pika.

Queues:
- agent.runs.events: Run lifecycle events (started, completed, failed)
- agent.llm.calls: LLM call events for tracking and cost calculation
- agent.tool.invocations: Tool invocation events
- budget.alerts: Budget threshold alerts

Dead Letter Queues:
- dlq.agent.runs.events
- dlq.agent.llm.calls
- dlq.agent.tool.invocations
- dlq.budget.alerts
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import urlparse

import pika
from pika.adapters.blocking_connection import BlockingChannel

from app.core.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Queue Definitions
# =============================================================================

class QueueName(str, Enum):
    """Available message queues."""
    AGENT_RUNS_EVENTS = "agent.runs.events"
    AGENT_LLM_CALLS = "agent.llm.calls"
    AGENT_TOOL_INVOCATIONS = "agent.tool.invocations"
    BUDGET_ALERTS = "budget.alerts"


class DLQName(str, Enum):
    """Dead letter queue names."""
    AGENT_RUNS_EVENTS = "dlq.agent.runs.events"
    AGENT_LLM_CALLS = "dlq.agent.llm.calls"
    AGENT_TOOL_INVOCATIONS = "dlq.agent.tool.invocations"
    BUDGET_ALERTS = "dlq.budget.alerts"


@dataclass
class QueueConfig:
    """Configuration for a message queue."""
    name: str
    exchange: str
    routing_key: str
    dlq_name: str
    dlq_routing_key: str
    message_ttl: int = 86400000  # 24 hours in milliseconds
    max_retries: int = 3
    durable: bool = True


# Queue configurations
QUEUE_CONFIGS: dict[QueueName, QueueConfig] = {
    QueueName.AGENT_RUNS_EVENTS: QueueConfig(
        name=QueueName.AGENT_RUNS_EVENTS.value,
        exchange="agent.runs.events",
        routing_key="agent.runs.events",
        dlq_name=DLQName.AGENT_RUNS_EVENTS.value,
        dlq_routing_key="dlq.agent.runs.events",
    ),
    QueueName.AGENT_LLM_CALLS: QueueConfig(
        name=QueueName.AGENT_LLM_CALLS.value,
        exchange="agent.llm.calls",
        routing_key="agent.llm.calls",
        dlq_name=DLQName.AGENT_LLM_CALLS.value,
        dlq_routing_key="dlq.agent.llm.calls",
    ),
    QueueName.AGENT_TOOL_INVOCATIONS: QueueConfig(
        name=QueueName.AGENT_TOOL_INVOCATIONS.value,
        exchange="agent.tool.invocations",
        routing_key="agent.tool.invocations",
        dlq_name=DLQName.AGENT_TOOL_INVOCATIONS.value,
        dlq_routing_key="dlq.agent.tool.invocations",
    ),
    QueueName.BUDGET_ALERTS: QueueConfig(
        name=QueueName.BUDGET_ALERTS.value,
        exchange="budget.alerts",
        routing_key="budget.alerts",
        dlq_name=DLQName.BUDGET_ALERTS.value,
        dlq_routing_key="dlq.budget.alerts",
    ),
}

# Dead Letter Exchange name
DLX_EXCHANGE = "dlx"
DLX_EXCHANGE_TYPE = "direct"


# =============================================================================
# Connection Management
# =============================================================================

def get_connection_params() -> pika.ConnectionParameters:
    """
    Parse RabbitMQ URL and return connection parameters.
    
    Returns:
        pika.ConnectionParameters configured for the RabbitMQ instance.
    """
    parsed = urlparse(settings.rabbitmq_url)
    
    credentials = pika.PlainCredentials(
        username=parsed.username or "guest",
        password=parsed.password or "guest",
    )
    
    return pika.ConnectionParameters(
        host=parsed.hostname or "localhost",
        port=parsed.port or 5672,
        virtual_host=parsed.path.lstrip("/") or "/",
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300,
    )


def get_connection() -> pika.BlockingConnection:
    """
    Create a new blocking connection to RabbitMQ.
    
    Returns:
        pika.BlockingConnection instance.
    """
    params = get_connection_params()
    return pika.BlockingConnection(params)


# =============================================================================
# Queue Setup
# =============================================================================

def setup_dead_letter_exchange(channel: BlockingChannel) -> None:
    """
    Declare the dead letter exchange (DLX) for handling failed messages.
    
    Args:
        channel: RabbitMQ channel.
    """
    channel.exchange_declare(
        exchange=DLX_EXCHANGE,
        exchange_type=DLX_EXCHANGE_TYPE,
        durable=True,
    )
    logger.info(f"Declared dead letter exchange: {DLX_EXCHANGE}")


def setup_dead_letter_queue(channel: BlockingChannel, dlq_name: str, dlq_routing_key: str) -> None:
    """
    Declare a dead letter queue and bind it to the DLX.
    
    Args:
        channel: RabbitMQ channel.
        dlq_name: Name of the dead letter queue.
        dlq_routing_key: Routing key for the DLQ.
    """
    # Declare the DLQ
    channel.queue_declare(
        queue=dlq_name,
        durable=True,
        arguments={
            # DLQ messages expire after 7 days
            "x-message-ttl": 604800000,
        },
    )
    
    # Bind DLQ to the dead letter exchange
    channel.queue_bind(
        queue=dlq_name,
        exchange=DLX_EXCHANGE,
        routing_key=dlq_routing_key,
    )
    logger.info(f"Declared dead letter queue: {dlq_name}")


def setup_queue(channel: BlockingChannel, config: QueueConfig) -> None:
    """
    Declare a queue with dead letter support and bind it to its exchange.
    
    Args:
        channel: RabbitMQ channel.
        config: Queue configuration.
    """
    # Declare the exchange
    channel.exchange_declare(
        exchange=config.exchange,
        exchange_type="direct",
        durable=config.durable,
    )
    
    # Declare the queue with DLQ arguments
    channel.queue_declare(
        queue=config.name,
        durable=config.durable,
        arguments={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": config.dlq_routing_key,
            "x-message-ttl": config.message_ttl,
        },
    )
    
    # Bind queue to exchange
    channel.queue_bind(
        queue=config.name,
        exchange=config.exchange,
        routing_key=config.routing_key,
    )
    logger.info(f"Declared queue: {config.name} with DLQ: {config.dlq_name}")


def setup_all_queues() -> None:
    """
    Set up all queues, exchanges, and dead letter queues.
    
    This should be called during application startup to ensure
    all required messaging infrastructure exists.
    """
    connection = get_connection()
    channel = connection.channel()
    
    try:
        # Set up the dead letter exchange first
        setup_dead_letter_exchange(channel)
        
        # Set up each queue with its DLQ
        for queue_name, config in QUEUE_CONFIGS.items():
            setup_dead_letter_queue(channel, config.dlq_name, config.dlq_routing_key)
            setup_queue(channel, config)
        
        logger.info("All queues and DLQs configured successfully")
    finally:
        connection.close()


# =============================================================================
# Health Check
# =============================================================================

def check_rabbitmq_health() -> dict[str, Any]:
    """
    Check RabbitMQ connection health.
    
    Returns:
        dict with status and details.
    """
    try:
        connection = get_connection()
        channel = connection.channel()
        
        # Check each queue exists and get message counts
        queue_stats = {}
        for queue_name, config in QUEUE_CONFIGS.items():
            result = channel.queue_declare(queue=config.name, passive=True)
            queue_stats[config.name] = {
                "message_count": result.method.message_count,
                "consumer_count": result.method.consumer_count,
            }
        
        connection.close()
        
        return {
            "status": "healthy",
            "queues": queue_stats,
        }
    except Exception as e:
        logger.error(f"RabbitMQ health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }

