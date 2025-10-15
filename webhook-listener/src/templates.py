"""Template rendering for InferenceService manifests."""

import logging
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateError

logger = logging.getLogger(__name__)

# Get the templates directory path
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# Kubernetes name length limit
K8S_NAME_MAX_LENGTH = 253


def sanitize_k8s_name(name: str) -> str:
    """
    Sanitize a name to comply with Kubernetes naming rules.

    Rules:
    - Lowercase alphanumeric characters or hyphens
    - Must start and end with alphanumeric character
    - Maximum 253 characters

    Args:
        name: The name to sanitize

    Returns:
        A valid Kubernetes name

    Raises:
        ValueError: If the sanitized name would be empty
    """
    logger.debug(f"Sanitizing name: {name}")

    # Convert to lowercase
    name = name.lower()

    # Replace invalid characters with hyphens
    name = re.sub(r"[^a-z0-9-]", "-", name)

    # Remove leading/trailing hyphens
    name = name.strip("-")

    # Replace multiple consecutive hyphens with single hyphen
    name = re.sub(r"-+", "-", name)

    # Truncate to K8S_NAME_MAX_LENGTH characters
    if len(name) > K8S_NAME_MAX_LENGTH:
        name = name[:K8S_NAME_MAX_LENGTH].rstrip("-")

    # Ensure we have a valid name (not empty)
    if not name:
        error_msg = "Sanitized name cannot be empty"
        raise ValueError(error_msg)

    logger.debug(f"Sanitized name: {name}")
    return name


def generate_inference_service_name(model_name: str, model_version: str) -> str:
    """
    Generate a Kubernetes-compliant InferenceService name.

    Args:
        model_name: The MLflow model name
        model_version: The MLflow model version

    Returns:
        A valid InferenceService name combining model name and version
    """
    # Combine model name and version
    combined = f"{model_name}-v{model_version}"

    # Sanitize to comply with K8s naming rules
    return sanitize_k8s_name(combined)


def render_inference_service(
    model_name: str,
    model_version: str,
    storage_uri: str,
    run_id: str,
    experiment_id: str,
    namespace: str,
    name: str | None = None,
) -> str:
    """
    Render an InferenceService manifest from the Jinja2 template.

    Args:
        model_name: The MLflow model name
        model_version: The MLflow model version
        storage_uri: The storage URI for the model artifacts
        run_id: The MLflow run ID
        experiment_id: The MLflow experiment ID
        namespace: The Kubernetes namespace
        name: Optional custom name for the InferenceService (will be sanitized)

    Returns:
        The rendered YAML manifest as a string

    Raises:
        TemplateError: If template rendering fails
        ValueError: If template variables are invalid
    """
    # Generate name if not provided
    if name is None:
        name = generate_inference_service_name(model_name, model_version)
    else:
        name = sanitize_k8s_name(name)

    logger.info(f"Rendering InferenceService template for {name}")
    logger.debug(
        f"Template vars: namespace={namespace}, model={model_name}, "
        f"version={model_version}, storage_uri={storage_uri}"
    )

    # Prepare template variables
    template_vars: dict[str, Any] = {
        "name": name,
        "namespace": namespace,
        "model_name": model_name,
        "model_version": model_version,
        "storage_uri": storage_uri,
        "run_id": run_id,
        "experiment_id": experiment_id,
    }

    try:
        # Set up Jinja2 environment
        # Note: autoescape=False is safe here because we're rendering YAML for
        # Kubernetes resources, not HTML. All variables are from trusted sources
        # (MLflow metadata) and are sanitized for K8s naming conventions.
        env = Environment(
            loader=FileSystemLoader(TEMPLATES_DIR),
            autoescape=False,
        )

        # Load and render template
        template = env.get_template("inference_service.yaml.j2")
        rendered = template.render(**template_vars)

        logger.debug(f"Successfully rendered template for {name}")
        return rendered

    except TemplateError as e:
        logger.error(f"Failed to render InferenceService template: {e}")
        error_msg = f"Failed to render InferenceService template: {e}"
        raise TemplateError(error_msg) from e
    except Exception as e:
        logger.error(f"Invalid template variables: {e}")
        error_msg = f"Invalid template variables: {e}"
        raise ValueError(error_msg) from e
