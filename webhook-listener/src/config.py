"""Configuration module using Pydantic Settings."""

import logging
import secrets

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # FastAPI Server
    app_host: str = Field(default="0.0.0.0", description="Host to bind the server to")
    app_port: int = Field(default=8000, description="Port to bind the server to")

    # SSL/TLS Configuration (optional)
    ssl_certfile: str | None = Field(
        default=None, description="Path to SSL certificate file (optional)"
    )
    ssl_keyfile: str | None = Field(
        default=None, description="Path to SSL private key file (optional)"
    )

    # MLflow Configuration
    mlflow_tracking_uri: str = Field(
        ..., description="MLflow tracking server URI (required)"
    )
    mlflow_webhook_secret: str | None = Field(
        default=None,
        description="Secret for verifying MLflow webhook signatures (auto-generated if not provided)"
    )
    mlflow_webhook_url: str = Field(
        ..., description="URL where this service receives webhooks (required)"
    )
    mlflow_webhook_name: str = Field(
        default="mlflow-kserve-webhook",
        description="Name for the registered webhook"
    )

    # Kubernetes Configuration
    kube_namespace: str = Field(
        default="kserve-mlflow-models",
        description="Kubernetes namespace for InferenceServices",
    )
    kube_in_cluster: bool = Field(
        default=True, description="Use in-cluster Kubernetes configuration"
    )

    # InferenceService Configuration
    inference_service_template: str = Field(
        default="templates/inference_service.yaml.j2",
        description="Path to InferenceService Jinja2 template",
    )

    # Optional: Resource limits
    predictor_cpu_request: str = Field(
        default="100m", description="CPU request for predictor"
    )
    predictor_cpu_limit: str = Field(
        default="1", description="CPU limit for predictor"
    )
    predictor_memory_request: str = Field(
        default="512Mi", description="Memory request for predictor"
    )
    predictor_memory_limit: str = Field(
        default="2Gi", description="Memory limit for predictor"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    model_config = SettingsConfigDict(
        env_prefix="MLFLOW_KSERVE_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("mlflow_webhook_secret", mode="before")
    @classmethod
    def generate_webhook_secret(cls, v):
        """Generate a secure random secret if none provided."""
        if v is None or v == "":
            # Generate a cryptographically secure random secret
            # Using 32 bytes (256 bits) for strong security
            generated_secret = secrets.token_urlsafe(32)
            logger.info("Webhook secret for HMAC verification auto-generated")
            return generated_secret
        return v


# Global settings instance
settings = Settings()
