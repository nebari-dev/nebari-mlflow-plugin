"""Tests for MLflow client webhook management."""

from unittest.mock import MagicMock, patch

import pytest
from src.mlflow_client import MLflowClient


@pytest.fixture
def mlflow_client():
    """Create a test MLflow client."""
    with patch("src.mlflow_client.MLflowSDKClient") as mock_sdk:
        mock_sdk_instance = MagicMock()
        mock_sdk.return_value = mock_sdk_instance
        client = MLflowClient(tracking_uri="http://test:5000")
        client._client = mock_sdk_instance
        yield client


def test_list_webhooks(mlflow_client):
    """Test listing webhooks."""
    mock_webhook1 = MagicMock()
    mock_webhook1.webhook_id = "webhook-1"
    mock_webhook1.url = "http://example.com/webhook1"

    mock_webhook2 = MagicMock()
    mock_webhook2.webhook_id = "webhook-2"
    mock_webhook2.url = "http://example.com/webhook2"

    mlflow_client._client.list_webhooks.return_value = [mock_webhook1, mock_webhook2]

    webhooks = mlflow_client.list_webhooks()

    assert len(webhooks) == 2
    assert webhooks[0].webhook_id == "webhook-1"
    assert webhooks[1].webhook_id == "webhook-2"


def test_get_webhook_by_url_found(mlflow_client):
    """Test finding a webhook by URL when it exists."""
    mock_webhook = MagicMock()
    mock_webhook.webhook_id = "webhook-1"
    mock_webhook.url = "http://example.com/webhook"

    mlflow_client._client.list_webhooks.return_value = [mock_webhook]

    result = mlflow_client.get_webhook_by_url("http://example.com/webhook")

    assert result is not None
    assert result.webhook_id == "webhook-1"


def test_get_webhook_by_url_not_found(mlflow_client):
    """Test finding a webhook by URL when it doesn't exist."""
    mock_webhook = MagicMock()
    mock_webhook.url = "http://example.com/other"

    mlflow_client._client.list_webhooks.return_value = [mock_webhook]

    result = mlflow_client.get_webhook_by_url("http://example.com/webhook")

    assert result is None


def test_create_webhook(mlflow_client):
    """Test creating a new webhook."""
    mock_webhook = MagicMock()
    mock_webhook.webhook_id = "new-webhook"

    mlflow_client._client.create_webhook.return_value = mock_webhook

    result = mlflow_client.create_webhook(
        name="test-webhook",
        url="http://example.com/webhook",
        events=["model_version_tag.set"],
        secret="test-secret",
        description="Test webhook"
    )

    assert result.webhook_id == "new-webhook"
    mlflow_client._client.create_webhook.assert_called_once()


def test_test_webhook_success(mlflow_client):
    """Test testing a webhook successfully."""
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.response_status = 200

    mlflow_client._client.test_webhook.return_value = mock_result

    result = mlflow_client.test_webhook("webhook-1")

    assert result.success is True
    assert result.response_status == 200


def test_test_webhook_failure(mlflow_client):
    """Test testing a webhook that fails."""
    mock_result = MagicMock()
    mock_result.success = False
    mock_result.error_message = "Connection refused"
    mock_result.response_status = None

    mlflow_client._client.test_webhook.return_value = mock_result

    result = mlflow_client.test_webhook("webhook-1")

    assert result.success is False
    assert result.error_message == "Connection refused"


def test_ensure_webhook_registered_creates_new(mlflow_client):
    """Test ensure_webhook_registered creates a new webhook when none exists."""
    # Mock: no existing webhooks
    mlflow_client._client.list_webhooks.return_value = []

    # Mock: successful webhook creation
    mock_webhook = MagicMock()
    mock_webhook.webhook_id = "new-webhook"
    mlflow_client._client.create_webhook.return_value = mock_webhook

    was_created, webhook = mlflow_client.ensure_webhook_registered(
        name="test-webhook",
        url="http://example.com/webhook",
        events=["model_version_tag.set"],
        secret="test-secret",
        test_on_create=False
    )

    assert was_created is True
    assert webhook.webhook_id == "new-webhook"
    mlflow_client._client.create_webhook.assert_called_once()


def test_ensure_webhook_registered_uses_existing(mlflow_client):
    """Test ensure_webhook_registered uses existing webhook when found."""
    # Mock: existing webhook found
    mock_webhook = MagicMock()
    mock_webhook.webhook_id = "existing-webhook"
    mock_webhook.url = "http://example.com/webhook"
    mlflow_client._client.list_webhooks.return_value = [mock_webhook]

    was_created, webhook = mlflow_client.ensure_webhook_registered(
        name="test-webhook",
        url="http://example.com/webhook",
        events=["model_version_tag.set"],
        secret="test-secret",
        test_on_create=False
    )

    assert was_created is False
    assert webhook.webhook_id == "existing-webhook"
    mlflow_client._client.create_webhook.assert_not_called()


def test_ensure_webhook_registered_with_test(mlflow_client):
    """Test ensure_webhook_registered with webhook testing enabled."""
    # Mock: no existing webhooks
    mlflow_client._client.list_webhooks.return_value = []

    # Mock: successful webhook creation
    mock_webhook = MagicMock()
    mock_webhook.webhook_id = "new-webhook"
    mlflow_client._client.create_webhook.return_value = mock_webhook

    # Mock: successful test
    mock_test_result = MagicMock()
    mock_test_result.success = True
    mock_test_result.response_status = 200
    mlflow_client._client.test_webhook.return_value = mock_test_result

    was_created, webhook = mlflow_client.ensure_webhook_registered(
        name="test-webhook",
        url="http://example.com/webhook",
        events=["model_version_tag.set"],
        secret="test-secret",
        test_on_create=True
    )

    assert was_created is True
    assert webhook.webhook_id == "new-webhook"
    mlflow_client._client.test_webhook.assert_called_once_with("new-webhook")
