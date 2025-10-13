"""Template rendering for InferenceService manifests."""

import logging
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)


def sanitize_k8s_name(name: str) -> str:
    """
    Sanitize a name to comply with Kubernetes naming rules.

    STUB: Currently just lowercases the name.
    Real implementation will be added in Phase 2.

    Rules:
    - Lowercase alphanumeric characters or '-'
    - Start with alphanumeric character
    - End with alphanumeric character
    - Max 253 characters
    """
    logger.debug(f"Sanitizing name: {name} (stub)")

    # STUB: Just lowercase for now
    sanitized = name.lower()
    logger.debug(f"Sanitized name: {sanitized}")
    return sanitized


def generate_inference_service_name(model_name: str, version: str) -> str:
    """
    Generate InferenceService name from model name and version.

    Format: mlflow-{model_name}-v{version}
    """
    name = f"mlflow-{model_name}-v{version}"
    return sanitize_k8s_name(name)


async def render_inference_service(
    template_path: str,
    name: str,
    namespace: str,
    model_name: str,
    model_version: str,
    storage_uri: str,
    run_id: str,
    experiment_id: str,
    **kwargs,
) -> str:
    """
    Render InferenceService YAML from Jinja2 template.

    STUB: Currently returns a dummy YAML string.
    Real implementation will be added in Phase 2.
    """
    logger.info(f"Rendering InferenceService template for {name} (stub)")
    logger.debug(
        f"Template vars: namespace={namespace}, model={model_name}, "
        f"version={model_version}, storage_uri={storage_uri}"
    )

    # STUB: Return dummy YAML
    dummy_yaml = f"""apiVersion: "serving.kserve.io/v1beta1"
kind: "InferenceService"
metadata:
  name: "{name}"
  namespace: "{namespace}"
  labels:
    mlflow.model: "{model_name}"
    mlflow.version: "{model_version}"
    mlflow.run-id: "{run_id}"
spec:
  predictor:
    model:
      modelFormat:
        name: mlflow
      protocolVersion: v2
      storageUri: "{storage_uri}"
"""
    return dummy_yaml
