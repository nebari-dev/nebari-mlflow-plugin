"""FastAPI application for MLflow webhook listener."""

import logging
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request

from src import __version__
from src.config import settings
from src.mlflow_client import MLflowClient

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    logger.info("Starting MLflow KServe Webhook Listener")
    logger.info(f"MLflow Tracking URI: {settings.mlflow_tracking_uri}")
    logger.info(f"Kubernetes Namespace: {settings.kube_namespace}")
    logger.info(f"Storage URI Base: {settings.storage_uri_base}")
    logger.info(f"Webhook URL: {settings.mlflow_webhook_url}")

    # Initialize MLflow client and ensure webhook is registered
    mlflow_client = MLflowClient(tracking_uri=settings.mlflow_tracking_uri)

    logger.info("Checking webhook registration...")
    was_created, webhook = mlflow_client.ensure_webhook_registered(
        name=settings.mlflow_webhook_name,
        url=settings.mlflow_webhook_url,
        events=["model_version_tag.set", "model_version_tag.deleted"],
        secret=settings.mlflow_webhook_secret,
        description="Automatically deploy MLflow models to KServe based on tags",
        test_on_create=False  # Don't test during startup to avoid circular dependency
    )

    if was_created:
        logger.info(f"Webhook registered successfully: {webhook.webhook_id}")
    else:
        logger.info(f"Using existing webhook: {webhook.webhook_id}")

    yield

    # Shutdown
    logger.info("Shutting down MLflow KServe Webhook Listener")


# Initialize FastAPI app
app = FastAPI(
    title="MLflow KServe Webhook Listener",
    description="Automatically deploy MLflow models to KServe based on tags",
    version=__version__,
    lifespan=lifespan,
)


@app.post("/webhook")
async def handle_webhook(
    request: Request,
    x_mlflow_signature: str | None = Header(None),
    x_mlflow_delivery_id: str | None = Header(None),
    x_mlflow_timestamp: str | None = Header(None),
):
    """
    Handle incoming MLflow webhook events.

    This is a STUB implementation that returns placeholder responses.
    Real implementation will be added in Phase 3.
    """
    logger.info(f"Received webhook - Delivery ID: {x_mlflow_delivery_id}")

    # Get payload
    payload_bytes = await request.body()
    payload_bytes.decode("utf-8")
    webhook_data = await request.json()

    entity = webhook_data.get("entity")
    action = webhook_data.get("action")
    data = webhook_data.get("data", {})

    logger.info(f"Event: {entity}.{action}")
    logger.info(f"Data: {data}")

    # STUB: Return placeholder response
    return {
        "status": "success",
        "message": "Webhook received (stub implementation)",
        "entity": entity,
        "action": action,
        "delivery_id": x_mlflow_delivery_id,
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for Kubernetes probes.

    This is a STUB implementation that returns basic status.
    Real implementation will be added in Phase 6.
    """
    return {
        "status": "healthy",
        "mlflow_connected": True,  # STUB: Always returns True
        "kubernetes_connected": True,  # STUB: Always returns True
    }


@app.get("/services")
async def list_services():
    """
    List all managed InferenceServices.

    This is a STUB implementation that returns empty list.
    Real implementation will be added in Phase 6.
    """
    return {
        "services": []  # STUB: Empty list
    }


def main():
    """Main entry point for the CLI."""
    # Configure SSL if certificates are provided
    ssl_kwargs = {}
    if settings.ssl_certfile and settings.ssl_keyfile:
        logger.info(f"SSL enabled - cert: {settings.ssl_certfile}, key: {settings.ssl_keyfile}")
        ssl_kwargs = {
            "ssl_certfile": settings.ssl_certfile,
            "ssl_keyfile": settings.ssl_keyfile,
        }
    else:
        logger.info("SSL not configured - running without HTTPS")

    uvicorn.run(
        app,
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.log_level.lower(),
        **ssl_kwargs,
    )


if __name__ == "__main__":
    main()
