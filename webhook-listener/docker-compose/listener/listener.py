from fastapi import FastAPI, Request, HTTPException, Header
from typing import Optional
import hmac
import hashlib
import base64
import logging
import time
import os

# Configure the root logger
logging.basicConfig(level=logging.DEBUG)

# You can also get a specific logger and set its level
app = FastAPI()
logger = logging.getLogger(__name__)

# Your webhook secret (keep this secure!)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

# Maximum allowed age for webhook timestamps (in seconds)
MAX_TIMESTAMP_AGE = 300  # 5 minutes


def verify_timestamp_freshness(
    timestamp_str: str, max_age: int = MAX_TIMESTAMP_AGE
) -> bool:
    """Verify that the webhook timestamp is recent enough to prevent replay attacks"""
    try:
        webhook_timestamp = int(timestamp_str)
        current_timestamp = int(time.time())
        age = current_timestamp - webhook_timestamp
        return 0 <= age <= max_age
    except (ValueError, TypeError):
        return False


def verify_mlflow_signature(
    payload: str, signature: str, secret: str, delivery_id: str, timestamp: str
) -> bool:
    """Verify the HMAC signature from MLflow webhook"""
    # Extract the base64 signature part (remove 'v1,' prefix)
    if not signature.startswith("v1,"):
        return False

    signature_b64 = signature.removeprefix("v1,")
    # Reconstruct the signed content: delivery_id.timestamp.payload
    signed_content = f"{delivery_id}.{timestamp}.{payload}"
    # Generate expected signature
    expected_signature = hmac.new(
        secret.encode("utf-8"), signed_content.encode("utf-8"), hashlib.sha256
    ).digest()
    expected_signature_b64 = base64.b64encode(expected_signature).decode("utf-8")
    return hmac.compare_digest(signature_b64, expected_signature_b64)


@app.post("/webhook")
async def handle_webhook(
    request: Request,
    x_mlflow_signature: Optional[str] = Header(None),
    x_mlflow_delivery_id: Optional[str] = Header(None),
    x_mlflow_timestamp: Optional[str] = Header(None),
):
    """Handle webhook with HMAC signature verification"""

    # Get raw payload for signature verification
    payload_bytes = await request.body()
    payload = payload_bytes.decode("utf-8")

    # Verify required headers are present
    if not x_mlflow_signature:
        raise HTTPException(status_code=400, detail="Missing signature header")
    if not x_mlflow_delivery_id:
        raise HTTPException(status_code=400, detail="Missing delivery ID header")
    if not x_mlflow_timestamp:
        raise HTTPException(status_code=400, detail="Missing timestamp header")

    # Verify timestamp freshness to prevent replay attacks
    if not verify_timestamp_freshness(x_mlflow_timestamp):
        raise HTTPException(
            status_code=400,
            detail="Timestamp is too old or invalid (possible replay attack)",
        )

    # Verify signature
    if not verify_mlflow_signature(
        payload,
        x_mlflow_signature,
        WEBHOOK_SECRET,
        x_mlflow_delivery_id,
        x_mlflow_timestamp,
    ):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    webhook_data = await request.json()

    # Extract webhook metadata
    entity = webhook_data.get("entity")
    action = webhook_data.get("action")
    timestamp = webhook_data.get("timestamp")
    payload_data = webhook_data.get("data", {})

    # Print the payload for debugging
    print(f"Received webhook: {entity}.{action}")
    print(f"Timestamp: {timestamp}")
    print(f"Delivery ID: {x_mlflow_delivery_id}")
    print(f"Payload: {payload_data}")

    # Add your webhook processing logic here
    # For example, handle different event types
    if entity == "model_version" and action == "created":
        model_name = payload_data.get("name")
        version = payload_data.get("version")
        print(f"New model version: {model_name} v{version}")
        # Add your model version processing logic here
    elif entity == "registered_model" and action == "created":
        model_name = payload_data.get("name")
        print(f"New registered model: {model_name}")
        # Add your registered model processing logic here
    elif entity == "model_version_tag" and action == "set":
        model_name = payload_data.get("name")
        version = payload_data.get("version")
        tag_key = payload_data.get("key")
        tag_value = payload_data.get("value")
        print(f"Tag set on {model_name} v{version}: {tag_key}={tag_value}")
        # Add your tag processing logic here

    return {"status": "success"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
