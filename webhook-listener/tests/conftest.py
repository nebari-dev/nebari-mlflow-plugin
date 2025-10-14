"""Pytest configuration and fixtures."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_env(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_TRACKING_URI", "http://test-mlflow:5000")
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_WEBHOOK_URL", "http://test-listener:8000/webhook")
    monkeypatch.setenv("MLFLOW_KSERVE_STORAGE_URI_BASE", "gs://test-bucket")
    monkeypatch.setenv("MLFLOW_KSERVE_KUBE_IN_CLUSTER", "false")
    monkeypatch.setenv("MLFLOW_KSERVE_LOG_LEVEL", "DEBUG")


@pytest.fixture
def client(test_env):
    """Create a test client for the FastAPI app."""
    # Mock MLflow webhook registration to avoid errors during tests
    mock_webhook = MagicMock()
    mock_webhook.webhook_id = "test-webhook-id"

    with patch("src.main.MLflowClient") as mock_mlflow_client:
        mock_client_instance = MagicMock()
        mock_client_instance.ensure_webhook_registered.return_value = (True, mock_webhook)
        mock_mlflow_client.return_value = mock_client_instance

        # Import here to ensure env vars are set first
        from src.main import app

        return TestClient(app)


@pytest.fixture
def sample_webhook_payload():
    """Sample webhook payload for testing."""
    return {
        "entity": "model_version_tag",
        "action": "set",
        "timestamp": 1234567890,
        "data": {
            "name": "iris-classifier",
            "version": "3",
            "key": "deploy",
            "value": "true",
            "run_id": "487892dfbe01444bbe535773ee32b14c",
            "experiment_id": "1"
        }
    }
