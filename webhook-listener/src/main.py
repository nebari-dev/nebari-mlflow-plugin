"""FastAPI application for MLflow webhook listener."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request

from src import __version__
from src.config import settings
from src.kubernetes_client import KubernetesClient
from src.mlflow_client import MLflowClient
from src.polling_service import PollingService
from src.timeout_utils import with_timeout_and_retry
from src.webhook_handler import (
    process_webhook_event,
    verify_mlflow_signature,
    verify_timestamp_freshness,
)

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
    logger.info(f"Webhook URL: {settings.mlflow_webhook_url}")

    # Initialize MLflow client and ensure webhook is registered
    mlflow_client = MLflowClient(tracking_uri=settings.mlflow_tracking_uri)

    # Initialize Kubernetes client
    k8s_client = KubernetesClient(
        namespace=settings.kube_namespace,
        in_cluster=settings.kube_in_cluster
    )

    # Initialize polling service (will only be used if webhook registration fails or is disabled)
    polling_service = None

    # Check if webhooks are disabled - if so, skip directly to polling
    if settings.disable_webhooks:
        logger.info("Webhooks disabled via configuration - using polling mode only")
        webhook_registered = False
    else:
        # Try to register webhook with timeout and retry logic
        webhook_registered = False
        try:
            logger.info("Checking for existing webhooks...")
            # Delete any existing webhook with the same URL to ensure we use the current secret
            # This handles cases where the webhook secret may have changed
            # Apply timeout/retry to the deletion operation
            delete_with_timeout = with_timeout_and_retry(
                timeout=settings.webhook_startup_timeout,
                max_retries=settings.webhook_startup_retries,
            )(mlflow_client.delete_webhook_by_url)

            deleted = await delete_with_timeout(settings.mlflow_webhook_url)
            if deleted:
                logger.info(f"Deleted existing webhook with URL: {settings.mlflow_webhook_url}")

            logger.info("Registering webhook with timeout...")
            # Apply timeout/retry to webhook registration
            register_with_timeout = with_timeout_and_retry(
                timeout=settings.webhook_startup_timeout,
                max_retries=settings.webhook_startup_retries,
            )(mlflow_client.ensure_webhook_registered)

            was_created, webhook = await register_with_timeout(
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

            webhook_registered = True

        except asyncio.TimeoutError:
            logger.error(
                f"Webhook operations timed out after {settings.webhook_startup_timeout}s "
                f"with {settings.webhook_startup_retries} retries"
            )
        except Exception as e:
            logger.error(f"Failed to complete webhook setup: {e}", exc_info=True)

    # Fall back to polling if webhook registration failed/disabled and polling is enabled
    if not webhook_registered and settings.enable_polling_fallback:
        if settings.disable_webhooks:
            logger.info(
                f"Starting in polling-only mode (interval: {settings.polling_interval}s)"
            )
        else:
            logger.warning(
                "Webhook registration failed - falling back to polling mode "
                f"(interval: {settings.polling_interval}s)"
            )
        polling_service = PollingService(
            mlflow_client=mlflow_client,
            k8s_client=k8s_client,
            interval=settings.polling_interval
        )
        await polling_service.start()
        logger.info("Polling service started as fallback")
    elif not webhook_registered:
        logger.error(
            "Webhook registration failed and polling fallback is disabled. "
            "Service will only respond to webhooks if they are manually configured."
        )

    yield

    # Shutdown
    logger.info("Shutting down MLflow KServe Webhook Listener")

    # Stop polling service if it's running
    if polling_service:
        logger.info("Stopping polling service...")
        await polling_service.stop()


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

    Verifies the webhook signature and processes the event.
    """
    logger.info(f"Received webhook - Delivery ID: {x_mlflow_delivery_id}")

    # Validate required headers
    if not x_mlflow_signature or not x_mlflow_delivery_id or not x_mlflow_timestamp:
        logger.warning(
            "Missing required webhook headers",
            extra={
                "has_signature": bool(x_mlflow_signature),
                "has_delivery_id": bool(x_mlflow_delivery_id),
                "has_timestamp": bool(x_mlflow_timestamp),
            },
        )
        raise HTTPException(
            status_code=400,
            detail="Missing required headers: x-mlflow-signature, x-mlflow-delivery-id, x-mlflow-timestamp",
        )

    # Get payload as bytes first (for signature verification)
    payload_bytes = await request.body()
    payload_str = payload_bytes.decode("utf-8")

    # Parse JSON from the string
    webhook_data = json.loads(payload_str)

    # Verify timestamp freshness (prevent replay attacks)
    if not verify_timestamp_freshness(x_mlflow_timestamp):
        logger.warning(
            "Webhook timestamp is stale or invalid",
            extra={
                "delivery_id": x_mlflow_delivery_id,
                "timestamp": x_mlflow_timestamp,
            },
        )
        raise HTTPException(
            status_code=401,
            detail="Webhook timestamp is stale or invalid",
        )

    # Verify signature
    if not verify_mlflow_signature(
        payload=payload_str,
        signature=x_mlflow_signature,
        secret=settings.mlflow_webhook_secret,
        delivery_id=x_mlflow_delivery_id,
        timestamp=x_mlflow_timestamp,
    ):
        logger.warning(
            "Webhook signature verification failed",
            extra={"delivery_id": x_mlflow_delivery_id},
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature",
        )

    logger.info(
        "Webhook verified successfully",
        extra={"delivery_id": x_mlflow_delivery_id},
    )

    # Process the webhook event
    try:
        result = await process_webhook_event(webhook_data, x_mlflow_delivery_id)
        return result
    except Exception as e:
        logger.error(
            f"Error processing webhook: {e}",
            extra={"delivery_id": x_mlflow_delivery_id},
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error processing webhook: {str(e)}",
        )


@app.get("/health")
async def health_check():
    """
    Health check endpoint for Kubernetes probes.

    Returns a simple status indicating the service is running.
    """
    return {"status": "healthy"}


@app.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check endpoint.

    Tests connectivity to MLflow and Kubernetes API and returns detailed status.
    This endpoint is more resource-intensive and should not be used for probes.
    """
    health_status = {
        "status": "healthy",
        "mlflow_connected": False,
        "kubernetes_connected": False,
        "details": {}
    }

    # Test MLflow connectivity
    try:
        mlflow_client = MLflowClient(tracking_uri=settings.mlflow_tracking_uri)
        # Try to list webhooks as a simple connectivity test
        webhooks = mlflow_client.list_webhooks()
        health_status["mlflow_connected"] = True
        health_status["details"]["mlflow"] = {
            "tracking_uri": settings.mlflow_tracking_uri,
            "webhook_count": len(webhooks)
        }
        logger.debug(f"MLflow health check passed - found {len(webhooks)} webhooks")
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["details"]["mlflow_error"] = str(e)
        logger.warning(f"MLflow health check failed: {e}")

    # Test Kubernetes connectivity
    try:
        k8s_client = KubernetesClient(
            namespace=settings.kube_namespace,
            in_cluster=settings.kube_in_cluster
        )
        # Try to list InferenceServices as a connectivity test
        # Use the managed-by label to only count services managed by this webhook
        services = await k8s_client.list_inference_services(
            label_selector="managed-by=nebari-mlflow-webhook-listener"
        )
        health_status["kubernetes_connected"] = True
        health_status["details"]["kubernetes"] = {
            "namespace": settings.kube_namespace,
            "in_cluster": settings.kube_in_cluster,
            "managed_services_count": len(services)
        }
        logger.debug(f"Kubernetes health check passed - found {len(services)} managed services")
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["details"]["kubernetes_error"] = str(e)
        logger.warning(f"Kubernetes health check failed: {e}")

    # Overall health is only healthy if both connections work
    if not (health_status["mlflow_connected"] and health_status["kubernetes_connected"]):
        health_status["status"] = "unhealthy"

    return health_status


@app.get("/services")
async def list_services():
    """
    List all managed InferenceServices.
    
    Returns a list of InferenceServices that are managed by this webhook listener,
    along with their current status and metadata.
    """
    try:
        k8s_client = KubernetesClient(
            namespace=settings.kube_namespace,
            in_cluster=settings.kube_in_cluster
        )
        
        # List InferenceServices managed by this webhook
        raw_services = await k8s_client.list_inference_services(
            label_selector="managed-by=nebari-mlflow-webhook-listener"
        )
        
        # Transform the raw service data into a more user-friendly format
        services = []
        for svc in raw_services:
            labels = svc.get("labels", {})
            status = svc.get("status", {})
            
            # Extract ready condition from status
            ready_status = "Unknown"
            conditions = status.get("conditions", [])
            for condition in conditions:
                if condition.get("type") == "Ready":
                    ready_status = "Ready" if condition.get("status") == "True" else "Not Ready"
                    break
            
            # Extract URL if available
            url = status.get("url", None)
            
            services.append({
                "name": svc["name"],
                "namespace": svc["namespace"],
                "model_name": labels.get("mlflow.org/model-name", "unknown"),
                "model_version": labels.get("mlflow.org/model-version", "unknown"),
                "run_id": labels.get("mlflow.org/run-id", "unknown"),
                "status": ready_status,
                "url": url,
                "creation_timestamp": svc.get("creation_timestamp"),
            })
        
        logger.info(f"Listed {len(services)} managed InferenceServices")
        
        return {
            "services": services,
            "total": len(services),
            "namespace": settings.kube_namespace
        }
        
    except Exception as e:
        logger.error(f"Error listing InferenceServices: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error listing InferenceServices: {str(e)}"
        )


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
