"""Webhook event processing and signature verification."""

import base64
import hashlib
import hmac
import logging
import textwrap
import time
from typing import Any, Dict

from src.config import settings
from src.kubernetes_client import (
    KubernetesClient,
    KubernetesClientError,
    InferenceServiceAlreadyExistsError,
)
from src.mlflow_client import MLflowClient
from src.templates import generate_inference_service_name, render_inference_service

logger = logging.getLogger(__name__)

# Initialize MLflow client
mlflow_client = MLflowClient(tracking_uri=settings.mlflow_tracking_uri)

# Initialize Kubernetes client
k8s_client = KubernetesClient(
    namespace=settings.kube_namespace,
    in_cluster=settings.kube_in_cluster,
)


def verify_mlflow_signature(
    payload: str, signature: str, secret: str, delivery_id: str, timestamp: str
) -> bool:
    """
    Verify the HMAC signature from MLflow webhook.

    Args:
        payload: Raw payload string from the webhook request body
        signature: Signature from x-mlflow-signature header
        secret: Webhook secret for HMAC verification
        delivery_id: Delivery ID from x-mlflow-delivery-id header
        timestamp: Timestamp from x-mlflow-timestamp header

    Returns:
        bool: True if signature is valid, False otherwise
    """
    logger.debug(
        f"Verifying signature for delivery ID: {delivery_id}",
        extra={
            "delivery_id": delivery_id,
            "timestamp": timestamp,
            "signature_prefix": signature[:10] if signature else None,
        },
    )

    try:
        # Extract the base64 signature part (remove 'v1,' prefix)
        if not signature.startswith("v1,"):
            logger.warning(
                "Invalid signature format: missing 'v1,' prefix",
                extra={"delivery_id": delivery_id, "signature": signature},
            )
            return False

        signature_b64 = signature.removeprefix("v1,")

        # Reconstruct the signed content: delivery_id.timestamp.payload
        signed_content = f"{delivery_id}.{timestamp}.{payload}"

        # Generate expected signature using HMAC-SHA256
        expected_signature = hmac.new(
            secret.encode("utf-8"), signed_content.encode("utf-8"), hashlib.sha256
        ).digest()
        expected_signature_b64 = base64.b64encode(expected_signature).decode("utf-8")

        # Use constant-time comparison to prevent timing attacks
        is_valid = hmac.compare_digest(signature_b64, expected_signature_b64)

        if is_valid:
            logger.info(
                "Signature verification successful",
                extra={"delivery_id": delivery_id},
            )
        else:
            logger.warning(
                "Signature verification failed: signature mismatch",
                extra={
                    "delivery_id": delivery_id,
                    "expected_prefix": expected_signature_b64[:10],
                    "received_prefix": signature_b64[:10],
                },
            )

        return is_valid

    except Exception as e:
        logger.error(
            f"Error during signature verification: {e}",
            extra={"delivery_id": delivery_id, "error": str(e)},
            exc_info=True,
        )
        return False


def verify_timestamp_freshness(timestamp_str: str, max_age: int = 300) -> bool:
    """
    Verify that the webhook timestamp is recent enough to prevent replay attacks.

    Args:
        timestamp_str: Timestamp string from the webhook header (Unix timestamp)
        max_age: Maximum allowed age in seconds (default: 300 seconds / 5 minutes)

    Returns:
        bool: True if timestamp is fresh, False otherwise
    """
    logger.debug(
        f"Verifying timestamp freshness: {timestamp_str}",
        extra={"timestamp": timestamp_str, "max_age": max_age},
    )

    try:
        # Parse the timestamp string to integer
        webhook_timestamp = int(timestamp_str)
        current_timestamp = int(time.time())
        age = current_timestamp - webhook_timestamp

        is_fresh = 0 <= age <= max_age

        if is_fresh:
            logger.debug(
                f"Timestamp is fresh (age: {age} seconds)",
                extra={"age": age, "max_age": max_age, "timestamp": timestamp_str},
            )
        elif age < 0:
            logger.warning(
                f"Timestamp is in the future (difference: {abs(age)} seconds)",
                extra={
                    "age": age,
                    "webhook_timestamp": webhook_timestamp,
                    "current_timestamp": current_timestamp,
                },
            )
        else:
            logger.warning(
                f"Timestamp is too old (age: {age} seconds, max: {max_age} seconds)",
                extra={
                    "age": age,
                    "max_age": max_age,
                    "webhook_timestamp": webhook_timestamp,
                    "current_timestamp": current_timestamp,
                },
            )

        return is_fresh

    except (ValueError, TypeError) as e:
        logger.error(
            f"Invalid timestamp format: {timestamp_str} - {e}",
            extra={"timestamp": timestamp_str, "error": str(e)},
        )
        return False


async def process_webhook_event(
    webhook_data: dict[str, Any], delivery_id: str
) -> dict[str, Any]:
    """
    Process webhook event and route to appropriate handler.

    Args:
        webhook_data: The webhook payload containing entity, action, and data
        delivery_id: The delivery ID from the webhook headers

    Returns:
        Dict with status and processing results
    """
    entity = webhook_data.get("entity")
    action = webhook_data.get("action")
    timestamp = webhook_data.get("timestamp")
    data = webhook_data.get("data", {})

    logger.info(
        f"Processing event: {entity}.{action}",
        extra={
            "entity": entity,
            "action": action,
            "delivery_id": delivery_id,
            "timestamp": timestamp,
        },
    )

    try:
        # Route to appropriate handler based on entity and action
        if entity == "model_version_tag" and action == "set":
            result = await handle_tag_set_event(data)
            logger.info(
                "Tag set event processed successfully",
                extra={"delivery_id": delivery_id, "result": result},
            )
            return {
                "status": "success",
                "entity": entity,
                "action": action,
                "delivery_id": delivery_id,
                "handler_result": result,
            }

        elif entity == "model_version_tag" and action == "deleted":
            result = await handle_tag_deleted_event(data)
            logger.info(
                "Tag deleted event processed successfully",
                extra={"delivery_id": delivery_id, "result": result},
            )
            return {
                "status": "success",
                "entity": entity,
                "action": action,
                "delivery_id": delivery_id,
                "handler_result": result,
            }

        else:
            # Event type not supported - log and return success anyway
            logger.warning(
                f"Unsupported event type: {entity}.{action}",
                extra={
                    "entity": entity,
                    "action": action,
                    "delivery_id": delivery_id,
                },
            )
            return {
                "status": "success",
                "message": f"Event {entity}.{action} received but not handled",
                "entity": entity,
                "action": action,
                "delivery_id": delivery_id,
            }

    except Exception as e:
        logger.error(
            f"Error processing webhook event: {e}",
            extra={
                "entity": entity,
                "action": action,
                "delivery_id": delivery_id,
                "error": str(e),
            },
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Error processing event: {str(e)}",
            "entity": entity,
            "action": action,
            "delivery_id": delivery_id,
        }


async def handle_tag_set_event(data: dict[str, Any]) -> dict[str, Any]:
    """
    Handle model_version_tag.set event.

    Processes tag set events and checks if the tag key is "deploy".
    - If deploy=true: Triggers deployment of the model
    - If deploy=false: Triggers undeployment of the model
    - If tag_key != "deploy": Ignores the event

    Args:
        data: Event data containing model name, version, tag key, and value

    Returns:
        Dict with processing status and action taken
    """
    model_name = data.get("name")
    version = data.get("version")
    tag_key = data.get("key")
    tag_value = data.get("value")

    logger.info(
        f"Tag set event: {model_name} v{version} - {tag_key}={tag_value}",
        extra={
            "model_name": model_name,
            "version": version,
            "tag_key": tag_key,
            "tag_value": tag_value,
        },
    )

    # Only process if the tag key is "deploy"
    if tag_key != "deploy":
        logger.debug(
            f"Ignoring non-deploy tag: {tag_key}",
            extra={
                "model_name": model_name,
                "version": version,
                "tag_key": tag_key,
            },
        )
        return {
            "action": "ignored",
            "reason": f"Tag key '{tag_key}' is not 'deploy'",
            "model_name": model_name,
            "version": version,
        }

    # Check if deploy value is "true" or "false"
    if tag_value == "true":
        logger.info(
            f"Deploy tag set to true for {model_name} v{version} - deployment will be triggered",
            extra={
                "model_name": model_name,
                "version": version,
                "action": "deploy",
            },
        )

        try:
            # Fetch model version details from MLflow
            logger.info(
                f"Fetching model details from MLflow for {model_name} v{version}",
                extra={"model_name": model_name, "version": version},
            )

            model_version = await mlflow_client.get_model_version(model_name, version)
            run_id = model_version["run_id"]
            storage_uri = model_version["source"]

            # Get run details to fetch experiment_id
            run_details = await mlflow_client.get_run(run_id)
            experiment_id = run_details["experiment_id"]

            logger.info(
                f"Successfully fetched model details for {model_name} v{version}",
                extra={
                    "model_name": model_name,
                    "version": version,
                    "run_id": run_id,
                    "experiment_id": experiment_id,
                    "storage_uri": storage_uri,
                },
            )

        except Exception as e:
            logger.error(
                f"Failed to fetch model details from MLflow for {model_name} v{version}: {e}",
                extra={
                    "model_name": model_name,
                    "version": version,
                    "error": str(e),
                },
                exc_info=True,
            )
            return {
                "action": "error",
                "model_name": model_name,
                "version": version,
                "message": f"Failed to fetch model details from MLflow: {e!s}",
            }

        try:
            # Render the InferenceService manifest
            manifest = render_inference_service(
                model_name=model_name,
                model_version=version,
                storage_uri=storage_uri,
                run_id=run_id,
                experiment_id=experiment_id,
                namespace=settings.kube_namespace,
            )

            # Generate the InferenceService name
            service_name = generate_inference_service_name(model_name, version)

            # Log the manifest
            indented_manifest = textwrap.indent(manifest, prefix="\t")
            logger.info(
                f"Generated InferenceService manifest for {model_name} v{version}:\n{indented_manifest}",
                extra={
                    "model_name": model_name,
                    "version": version,
                    "service_name": service_name,
                    "manifest": manifest,
                },
            )

            # Deploy to Kubernetes
            try:
                # Use update (which creates if doesn't exist)
                result = await k8s_client.update_inference_service(service_name, manifest)

                logger.info(
                    f"Successfully deployed InferenceService {service_name} for {model_name} v{version}",
                    extra={
                        "model_name": model_name,
                        "version": version,
                        "service_name": service_name,
                        "k8s_result": result,
                    },
                )

                return {
                    "action": "deployed",
                    "model_name": model_name,
                    "version": version,
                    "service_name": service_name,
                    "namespace": settings.kube_namespace,
                    "status": result.get("status"),
                    "uid": result.get("uid"),
                }

            except InferenceServiceAlreadyExistsError:
                # This shouldn't happen since we use update, but handle it gracefully
                logger.warning(
                    f"InferenceService {service_name} already exists, this is unexpected with update",
                    extra={
                        "model_name": model_name,
                        "version": version,
                        "service_name": service_name,
                    },
                )
                return {
                    "action": "deployed",
                    "model_name": model_name,
                    "version": version,
                    "service_name": service_name,
                    "namespace": settings.kube_namespace,
                    "note": "already_exists",
                }

            except KubernetesClientError as e:
                logger.error(
                    f"Kubernetes error deploying {service_name}: {e}",
                    extra={
                        "model_name": model_name,
                        "version": version,
                        "service_name": service_name,
                        "error": str(e),
                    },
                    exc_info=True,
                )
                return {
                    "action": "error",
                    "model_name": model_name,
                    "version": version,
                    "service_name": service_name,
                    "message": f"Kubernetes deployment failed: {str(e)}",
                }

        except Exception as e:
            logger.error(
                f"Failed to generate manifest for {model_name} v{version}: {e}",
                extra={
                    "model_name": model_name,
                    "version": version,
                    "error": str(e),
                },
                exc_info=True,
            )
            return {
                "action": "error",
                "model_name": model_name,
                "version": version,
                "message": f"Failed to generate manifest: {str(e)}",
            }

    elif tag_value == "false":
        logger.info(
            f"Deploy tag set to false for {model_name} v{version} - undeployment will be triggered",
            extra={
                "model_name": model_name,
                "version": version,
                "action": "undeploy",
            },
        )

        # Generate the InferenceService name
        service_name = generate_inference_service_name(model_name, version)

        # Delete InferenceService from Kubernetes
        try:
            result = await k8s_client.delete_inference_service(service_name)

            logger.info(
                f"Successfully deleted InferenceService {service_name} for {model_name} v{version}",
                extra={
                    "model_name": model_name,
                    "version": version,
                    "service_name": service_name,
                    "k8s_result": result,
                },
            )

            return {
                "action": "undeployed",
                "model_name": model_name,
                "version": version,
                "service_name": service_name,
                "namespace": settings.kube_namespace,
                "status": result.get("status"),
                "note": result.get("note"),
            }

        except KubernetesClientError as e:
            logger.error(
                f"Kubernetes error deleting {service_name}: {e}",
                extra={
                    "model_name": model_name,
                    "version": version,
                    "service_name": service_name,
                    "error": str(e),
                },
                exc_info=True,
            )
            return {
                "action": "error",
                "model_name": model_name,
                "version": version,
                "service_name": service_name,
                "message": f"Kubernetes deletion failed: {e!s}",
            }

    else:
        logger.warning(
            f"Deploy tag has unexpected value: {tag_value} (expected 'true' or 'false')",
            extra={
                "model_name": model_name,
                "version": version,
                "tag_value": tag_value,
            },
        )
        return {
            "action": "ignored",
            "reason": f"Deploy tag value '{tag_value}' is not 'true' or 'false'",
            "model_name": model_name,
            "version": version,
        }


async def handle_tag_deleted_event(data: dict[str, Any]) -> dict[str, Any]:
    """
    Handle model_version_tag.deleted event.

    Processes tag deletion events and checks if the tag key is "deploy".
    If the deploy tag is deleted, triggers undeployment of the model.

    Args:
        data: Event data containing model name, version, and tag key

    Returns:
        Dict with processing status and action taken
    """
    model_name = data.get("name")
    version = data.get("version")
    tag_key = data.get("key")

    logger.info(
        f"Tag deleted event: {model_name} v{version} - {tag_key}",
        extra={
            "model_name": model_name,
            "version": version,
            "tag_key": tag_key,
        },
    )

    # Only process if the tag key is "deploy"
    if tag_key != "deploy":
        logger.debug(
            f"Ignoring deletion of non-deploy tag: {tag_key}",
            extra={
                "model_name": model_name,
                "version": version,
                "tag_key": tag_key,
            },
        )
        return {
            "action": "ignored",
            "reason": f"Tag key '{tag_key}' is not 'deploy'",
            "model_name": model_name,
            "version": version,
        }

    # Deploy tag was deleted - trigger undeployment
    logger.info(
        f"Deploy tag deleted for {model_name} v{version} - undeployment will be triggered",
        extra={
            "model_name": model_name,
            "version": version,
            "action": "undeploy",
        },
    )

    # Generate the InferenceService name
    service_name = generate_inference_service_name(model_name, version)

    # Delete InferenceService from Kubernetes
    try:
        result = await k8s_client.delete_inference_service(service_name)

        logger.info(
            f"Successfully deleted InferenceService {service_name} for {model_name} v{version}",
            extra={
                "model_name": model_name,
                "version": version,
                "service_name": service_name,
                "k8s_result": result,
            },
        )

        return {
            "action": "undeployed",
            "model_name": model_name,
            "version": version,
            "service_name": service_name,
            "namespace": settings.kube_namespace,
            "status": result.get("status"),
            "note": result.get("note"),
        }

    except KubernetesClientError as e:
        logger.error(
            f"Kubernetes error deleting {service_name}: {e}",
            extra={
                "model_name": model_name,
                "version": version,
                "service_name": service_name,
                "error": str(e),
            },
            exc_info=True,
        )
        return {
            "action": "error",
            "model_name": model_name,
            "version": version,
            "service_name": service_name,
            "message": f"Kubernetes deletion failed: {e!s}",
        }
