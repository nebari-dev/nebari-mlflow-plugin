"""Tests for configuration module."""

import pytest
from pydantic import ValidationError


def test_settings_loads_from_env(test_env):
    """Test that Settings loads correctly from environment variables."""
    from src.config import Settings

    settings = Settings()

    assert settings.mlflow_tracking_uri == "http://test-mlflow:5000"
    assert settings.mlflow_webhook_secret == "test-secret"
    assert settings.mlflow_webhook_url == "http://test-listener:8000/webhook"
    assert settings.storage_uri_base == "gs://test-bucket"
    assert settings.kube_in_cluster is False
    assert settings.log_level == "DEBUG"


def test_settings_has_defaults(test_env):
    """Test that Settings has appropriate defaults."""
    from src.config import Settings

    settings = Settings()

    assert settings.app_host == "0.0.0.0"
    assert settings.app_port == 8000
    assert settings.kube_namespace == "kserve-mlflow-models"
    assert settings.predictor_cpu_request == "100m"
    assert settings.predictor_memory_request == "512Mi"


def test_settings_requires_tracking_uri(monkeypatch):
    """Test that mlflow_tracking_uri is required."""
    # Clear any .env file loading
    monkeypatch.delenv("MLFLOW_KSERVE_MLFLOW_TRACKING_URI", raising=False)
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_WEBHOOK_URL", "http://test:8000/webhook")
    monkeypatch.setenv("MLFLOW_KSERVE_STORAGE_URI_BASE", "gs://bucket")

    from src.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("mlflow_tracking_uri",) for e in errors)


def test_settings_requires_webhook_secret(monkeypatch):
    """Test that mlflow_webhook_secret is required."""
    monkeypatch.delenv("MLFLOW_KSERVE_MLFLOW_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_TRACKING_URI", "http://mlflow:5000")
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_WEBHOOK_URL", "http://test:8000/webhook")
    monkeypatch.setenv("MLFLOW_KSERVE_STORAGE_URI_BASE", "gs://bucket")

    from src.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("mlflow_webhook_secret",) for e in errors)


def test_settings_requires_storage_uri_base(monkeypatch):
    """Test that storage_uri_base is required."""
    monkeypatch.delenv("MLFLOW_KSERVE_STORAGE_URI_BASE", raising=False)
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_TRACKING_URI", "http://mlflow:5000")
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_WEBHOOK_URL", "http://test:8000/webhook")

    from src.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("storage_uri_base",) for e in errors)


def test_settings_requires_webhook_url(monkeypatch):
    """Test that mlflow_webhook_url is required."""
    monkeypatch.delenv("MLFLOW_KSERVE_MLFLOW_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_TRACKING_URI", "http://mlflow:5000")
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("MLFLOW_KSERVE_STORAGE_URI_BASE", "gs://bucket")

    from src.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("mlflow_webhook_url",) for e in errors)
