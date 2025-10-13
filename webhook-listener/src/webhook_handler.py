"""Webhook event processing and signature verification."""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def verify_mlflow_signature(
    payload: str, signature: str, secret: str, delivery_id: str, timestamp: str
) -> bool:
    """
    Verify the HMAC signature from MLflow webhook.

    STUB: Currently returns True.
    Real implementation will be added in Phase 3.
    """
    logger.debug(f"Verifying signature for delivery ID: {delivery_id}")
    # STUB: Always return True for now
    return True


def verify_timestamp_freshness(timestamp_str: str, max_age: int = 300) -> bool:
    """
    Verify that the webhook timestamp is recent enough to prevent replay attacks.

    STUB: Currently returns True.
    Real implementation will be added in Phase 3.
    """
    logger.debug(f"Verifying timestamp freshness: {timestamp_str}")
    # STUB: Always return True for now
    return True


async def process_webhook_event(
    webhook_data: Dict[str, Any], delivery_id: str
) -> Dict[str, Any]:
    """
    Process webhook event and route to appropriate handler.

    STUB: Currently just logs the event and returns success.
    Real implementation will be added in Phase 3.
    """
    entity = webhook_data.get("entity")
    action = webhook_data.get("action")
    data = webhook_data.get("data", {})

    logger.info(f"Processing event: {entity}.{action}")
    logger.info(f"Event data: {data}")

    # STUB: Just return success for now
    return {
        "status": "success",
        "message": "Event processed (stub)",
        "entity": entity,
        "action": action,
    }


async def handle_tag_set_event(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle model_version_tag.set event.

    STUB: Currently just logs.
    Real implementation will be added in Phase 3.
    """
    model_name = data.get("name")
    version = data.get("version")
    tag_key = data.get("key")
    tag_value = data.get("value")

    logger.info(
        f"Tag set event: {model_name} v{version} - {tag_key}={tag_value} (stub)"
    )

    # STUB: Return success
    return {"status": "success", "action": "tag_set_handled"}


async def handle_tag_deleted_event(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle model_version_tag.deleted event.

    STUB: Currently just logs.
    Real implementation will be added in Phase 3.
    """
    model_name = data.get("name")
    version = data.get("version")
    tag_key = data.get("key")

    logger.info(f"Tag deleted event: {model_name} v{version} - {tag_key} (stub)")

    # STUB: Return success
    return {"status": "success", "action": "tag_deleted_handled"}
