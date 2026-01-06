"""
Message Queue Service for Cognive Control Plane.

This module provides producer and consumer utilities for publishing
and consuming messages from RabbitMQ queues.

Usage:
    # Publishing a message
    from app.services.message_queue import MessagePublisher, QueueName
    
    publisher = MessagePublisher()
    publisher.publish(
        queue=QueueName.AGENT_RUNS_EVENTS,
        message={"run_id": "123", "status": "started"}
    )
    
    # Consuming messages
    from app.services.message_queue import MessageConsumer, QueueName
    
    def handle_run_event(message: dict):
        print(f"Processing run: {message['run_id']}")
    
    consumer = MessageConsumer()
    consumer.consume(
        queue=QueueName.AGENT_RUNS_EVENTS,
        callback=handle_run_event
    )
"""

import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Generator
from uuid import uuid4

import pika
from pika.adapters.blocking_connection import BlockingChannel

from app.core.messaging import (
    QUEUE_CONFIGS,
    QueueConfig,
    QueueName,
    get_connection,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Message Publisher
# =============================================================================

class MessagePublisher:
    """
    Publisher for sending messages to RabbitMQ queues.
    
    Provides reliable message publishing with:
    - Automatic connection management
    - Message persistence
    - Delivery confirmation
    - Automatic retries
    """
    
    def __init__(self):
        self._connection = None
        self._channel = None
    
    @contextmanager
    def _get_channel(self) -> Generator[BlockingChannel, None, None]:
        """Get a channel, creating connection if needed."""
        connection = get_connection()
        channel = connection.channel()
        channel.confirm_delivery()  # Enable delivery confirmations
        
        try:
            yield channel
        finally:
            connection.close()
    
    def publish(
        self,
        queue: QueueName,
        message: dict[str, Any],
        priority: int = 0,
        correlation_id: str | None = None,
        headers: dict[str, Any] | None = None,
    ) -> str:
        """
        Publish a message to the specified queue.
        
        Args:
            queue: Target queue name.
            message: Message payload (will be JSON serialized).
            priority: Message priority (0-9, higher = more priority).
            correlation_id: Optional correlation ID for tracking.
            headers: Optional message headers.
        
        Returns:
            The message ID.
        
        Raises:
            pika.exceptions.UnroutableError: If message cannot be routed.
        """
        config = QUEUE_CONFIGS[queue]
        message_id = str(uuid4())
        
        # Add metadata to message
        enriched_message = {
            **message,
            "_metadata": {
                "message_id": message_id,
                "queue": queue.value,
                "published_at": datetime.now(timezone.utc).isoformat(),
            }
        }
        
        properties = pika.BasicProperties(
            message_id=message_id,
            correlation_id=correlation_id or message_id,
            content_type="application/json",
            delivery_mode=2,  # Persistent
            priority=priority,
            timestamp=int(datetime.now(timezone.utc).timestamp()),
            headers=headers or {},
        )
        
        body = json.dumps(enriched_message).encode("utf-8")
        
        with self._get_channel() as channel:
            channel.basic_publish(
                exchange=config.exchange,
                routing_key=config.routing_key,
                body=body,
                properties=properties,
                mandatory=True,  # Ensure message is routed
            )
        
        logger.info(f"Published message {message_id} to {queue.value}")
        return message_id
    
    def publish_batch(
        self,
        queue: QueueName,
        messages: list[dict[str, Any]],
    ) -> list[str]:
        """
        Publish multiple messages to the specified queue.
        
        Args:
            queue: Target queue name.
            messages: List of message payloads.
        
        Returns:
            List of message IDs.
        """
        config = QUEUE_CONFIGS[queue]
        message_ids = []
        
        with self._get_channel() as channel:
            for message in messages:
                message_id = str(uuid4())
                message_ids.append(message_id)
                
                enriched_message = {
                    **message,
                    "_metadata": {
                        "message_id": message_id,
                        "queue": queue.value,
                        "published_at": datetime.now(timezone.utc).isoformat(),
                    }
                }
                
                properties = pika.BasicProperties(
                    message_id=message_id,
                    correlation_id=message_id,
                    content_type="application/json",
                    delivery_mode=2,
                    timestamp=int(datetime.now(timezone.utc).timestamp()),
                )
                
                body = json.dumps(enriched_message).encode("utf-8")
                
                channel.basic_publish(
                    exchange=config.exchange,
                    routing_key=config.routing_key,
                    body=body,
                    properties=properties,
                    mandatory=True,
                )
        
        logger.info(f"Published {len(messages)} messages to {queue.value}")
        return message_ids


# =============================================================================
# Message Consumer
# =============================================================================

class MessageConsumer:
    """
    Consumer for receiving messages from RabbitMQ queues.
    
    Provides reliable message consumption with:
    - Automatic acknowledgment on success
    - Automatic rejection on failure (sends to DLQ)
    - Graceful shutdown handling
    """
    
    def __init__(self, prefetch_count: int = 1):
        """
        Initialize consumer.
        
        Args:
            prefetch_count: Number of messages to prefetch (default 1 for fair dispatch).
        """
        self._prefetch_count = prefetch_count
        self._connection = None
        self._channel = None
        self._consuming = False
    
    def consume(
        self,
        queue: QueueName,
        callback: Callable[[dict[str, Any]], None],
        auto_ack: bool = False,
    ) -> None:
        """
        Start consuming messages from the specified queue.
        
        This is a blocking call that will run until stop() is called.
        
        Args:
            queue: Queue to consume from.
            callback: Function to call for each message.
            auto_ack: If True, auto-acknowledge messages (not recommended).
        """
        config = QUEUE_CONFIGS[queue]
        self._connection = get_connection()
        self._channel = self._connection.channel()
        self._channel.basic_qos(prefetch_count=self._prefetch_count)
        
        def on_message(
            channel: BlockingChannel,
            method: pika.spec.Basic.Deliver,
            properties: pika.BasicProperties,
            body: bytes,
        ):
            """Handle incoming message."""
            message_id = properties.message_id or "unknown"
            
            try:
                message = json.loads(body.decode("utf-8"))
                logger.info(f"Received message {message_id} from {queue.value}")
                
                callback(message)
                
                if not auto_ack:
                    channel.basic_ack(delivery_tag=method.delivery_tag)
                    logger.debug(f"Acknowledged message {message_id}")
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode message {message_id}: {e}")
                # Reject without requeue (sends to DLQ)
                channel.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
                
            except Exception as e:
                logger.error(f"Error processing message {message_id}: {e}")
                # Reject without requeue (sends to DLQ)
                channel.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
        
        self._channel.basic_consume(
            queue=config.name,
            on_message_callback=on_message,
            auto_ack=auto_ack,
        )
        
        logger.info(f"Started consuming from {queue.value}")
        self._consuming = True
        
        try:
            self._channel.start_consuming()
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self) -> None:
        """Stop consuming and close connection."""
        if self._channel and self._consuming:
            self._channel.stop_consuming()
            self._consuming = False
        
        if self._connection:
            self._connection.close()
            self._connection = None
        
        logger.info("Consumer stopped")


# =============================================================================
# Convenience Functions
# =============================================================================

def publish_agent_run_event(
    run_id: str,
    agent_id: str,
    event_type: str,
    data: dict[str, Any] | None = None,
) -> str:
    """
    Publish an agent run lifecycle event.
    
    Args:
        run_id: The run ID.
        agent_id: The agent ID.
        event_type: Event type (e.g., "started", "completed", "failed").
        data: Optional additional event data.
    
    Returns:
        The message ID.
    """
    publisher = MessagePublisher()
    return publisher.publish(
        queue=QueueName.AGENT_RUNS_EVENTS,
        message={
            "run_id": run_id,
            "agent_id": agent_id,
            "event_type": event_type,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def publish_llm_call_event(
    run_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost: float,
    latency_ms: int,
    data: dict[str, Any] | None = None,
) -> str:
    """
    Publish an LLM call event for cost tracking.
    
    Args:
        run_id: The run ID.
        model: LLM model name.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        cost: Calculated cost.
        latency_ms: Call latency in milliseconds.
        data: Optional additional data.
    
    Returns:
        The message ID.
    """
    publisher = MessagePublisher()
    return publisher.publish(
        queue=QueueName.AGENT_LLM_CALLS,
        message={
            "run_id": run_id,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "latency_ms": latency_ms,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def publish_tool_invocation_event(
    run_id: str,
    tool_name: str,
    success: bool,
    duration_ms: int,
    data: dict[str, Any] | None = None,
) -> str:
    """
    Publish a tool invocation event.
    
    Args:
        run_id: The run ID.
        tool_name: Name of the tool invoked.
        success: Whether the invocation was successful.
        duration_ms: Invocation duration in milliseconds.
        data: Optional additional data.
    
    Returns:
        The message ID.
    """
    publisher = MessagePublisher()
    return publisher.publish(
        queue=QueueName.AGENT_TOOL_INVOCATIONS,
        message={
            "run_id": run_id,
            "tool_name": tool_name,
            "success": success,
            "duration_ms": duration_ms,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def publish_budget_alert(
    organization_id: str,
    agent_id: str | None,
    alert_type: str,
    threshold: float,
    current_value: float,
    message: str,
) -> str:
    """
    Publish a budget threshold alert.
    
    Args:
        organization_id: The organization ID.
        agent_id: Optional agent ID (if agent-specific alert).
        alert_type: Type of alert (e.g., "warning", "critical", "exceeded").
        threshold: The threshold that was crossed.
        current_value: The current budget usage value.
        message: Human-readable alert message.
    
    Returns:
        The message ID.
    """
    publisher = MessagePublisher()
    return publisher.publish(
        queue=QueueName.BUDGET_ALERTS,
        message={
            "organization_id": organization_id,
            "agent_id": agent_id,
            "alert_type": alert_type,
            "threshold": threshold,
            "current_value": current_value,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        priority=5 if alert_type == "critical" else 0,
    )

