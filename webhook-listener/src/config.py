"""Configuration module using Pydantic Settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # FastAPI Server
    app_host: str = Field(default="0.0.0.0", description="Host to bind the server to")
    app_port: int = Field(default=8000, description="Port to bind the server to")

    # MLflow Configuration
    mlflow_tracking_uri: str = Field(
        ..., description="MLflow tracking server URI (required)"
    )
    mlflow_webhook_secret: str = Field(
        ..., description="Secret for verifying MLflow webhook signatures (required)"
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
    storage_uri_base: str = Field(
        ..., description="Base URI for model storage (e.g., gs://bucket-name)"
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


# Global settings instance
settings = Settings()
