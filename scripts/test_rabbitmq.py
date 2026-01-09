#!/usr/bin/env python3
"""
RabbitMQ smoke test for Cognive.

This script validates that required exchanges/queues exist and that messages can
be published and consumed. It publishes a small healthcheck message to each
queue, verifies it can be retrieved, and then cleans it up (ack).

Usage:
    python scripts/test_rabbitmq.py
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Tuple
from uuid import uuid4

# Add project root for imports when running as a standalone script
sys.path.insert(0, str(Path(__file__).parent.parent))

import pika  # noqa: E402

from app.core.messaging import (  # noqa: E402
    QUEUE_CONFIGS,
    QueueConfig,
    get_connection,
    setup_all_queues,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Tunables
PUBLISH_WAIT_SECONDS = 5.0
POLL_INTERVAL_SECONDS = 0.3
MESSAGE_TTL_MS = 15000  # expire test messages if left in queue


def _ensure_declared(channel, config: QueueConfig) -> None:
    """Passively ensure the exchange and queue exist with expected binding."""
    channel.exchange_declare(
        exchange=config.exchange,
        exchange_type="direct",
        durable=config.durable,
        passive=True,
    )
    channel.queue_declare(
        queue=config.name,
        durable=config.durable,
        passive=True,
    )
    channel.queue_bind(
        queue=config.name,
        exchange=config.exchange,
        routing_key=config.routing_key,
    )


def _publish_and_verify(channel, config: QueueConfig) -> Tuple[bool, str]:
    """
    Publish a test message and verify it can be consumed.

    Returns:
        (success, message_id)
    """
    message_id = f"rabbitmq-health-{uuid4()}"
    payload = {
        "_healthcheck": True,
        "_healthcheck_id": message_id,
        "queue": config.name,
        "timestamp": time.time(),
    }

    properties = pika.BasicProperties(
        message_id=message_id,
        content_type="application/json",
        delivery_mode=2,  # persistent
        expiration=str(MESSAGE_TTL_MS),
        headers={"healthcheck": True},
    )

    channel.basic_publish(
        exchange=config.exchange,
        routing_key=config.routing_key,
        body=json.dumps(payload).encode("utf-8"),
        properties=properties,
        mandatory=True,
    )

    deadline = time.time() + PUBLISH_WAIT_SECONDS
    while time.time() < deadline:
        method, props, body = channel.basic_get(queue=config.name, auto_ack=False)
        if not method:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        try:
            message = json.loads(body.decode("utf-8"))
        except Exception:
            # Not our message; requeue and continue
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        if message.get("_healthcheck_id") == message_id:
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return True, message_id

        # Not our test message; put it back and try again without disturbing order
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        time.sleep(POLL_INTERVAL_SECONDS)

    return False, message_id


def main() -> int:
    logger.info("Starting RabbitMQ smoke test")

    # Ensure queues/exchanges exist (idempotent)
    setup_all_queues()

    connection = get_connection()
    channel = connection.channel()
    channel.confirm_delivery()

    overall_success = True

    try:
        for queue_name, config in QUEUE_CONFIGS.items():
            logger.info(f"Checking queue: {config.name}")

            try:
                _ensure_declared(channel, config)
            except Exception as e:
                overall_success = False
                logger.error(f"❌ Queue declaration check failed for {config.name}: {e}")
                continue

            ok, message_id = _publish_and_verify(channel, config)
            if ok:
                logger.info(f"✅ Publish/consume ok for {config.name} (msg {message_id})")
            else:
                overall_success = False
                logger.error(f"❌ Publish/consume failed for {config.name} (msg {message_id})")

    finally:
        connection.close()

    if overall_success:
        logger.info("✅ RabbitMQ smoke test passed for all queues")
        return 0

    logger.error("❌ RabbitMQ smoke test FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())



