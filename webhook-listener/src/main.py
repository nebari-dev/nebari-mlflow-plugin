"""FastAPI application for MLflow webhook listener."""

import logging
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request, Header, HTTPException

from . import __version__
from .config import settings

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
    x_mlflow_signature: Optional[str] = Header(None),
    x_mlflow_delivery_id: Optional[str] = Header(None),
    x_mlflow_timestamp: Optional[str] = Header(None),
):
    """
    Handle incoming MLflow webhook events.

    This is a STUB implementation that returns placeholder responses.
    Real implementation will be added in Phase 3.
    """
    logger.info(f"Received webhook - Delivery ID: {x_mlflow_delivery_id}")

    # Get payload
    payload_bytes = await request.body()
    payload = payload_bytes.decode("utf-8")
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
    uvicorn.run(
        app,
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
