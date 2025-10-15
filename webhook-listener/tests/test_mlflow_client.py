"""Tests for MLflow client webhook management."""

from unittest.mock import MagicMock, patch

import pytest
from mlflow.entities import Run, RunInfo
from mlflow.entities.model_registry import ModelVersion
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


def test_delete_webhook(mlflow_client):
    """Test deleting a webhook by ID."""
    mlflow_client._client.delete_webhook.return_value = None

    mlflow_client.delete_webhook("webhook-1")

    mlflow_client._client.delete_webhook.assert_called_once_with("webhook-1")


def test_delete_webhook_error(mlflow_client):
    """Test delete_webhook with error."""
    mlflow_client._client.delete_webhook.side_effect = Exception("Webhook not found")

    with pytest.raises(Exception, match="Webhook not found"):
        mlflow_client.delete_webhook("invalid-webhook")


def test_delete_webhook_by_url_found(mlflow_client):
    """Test deleting a webhook by URL when it exists."""
    mock_webhook = MagicMock()
    mock_webhook.webhook_id = "webhook-1"
    mock_webhook.url = "http://example.com/webhook"

    mlflow_client._client.list_webhooks.return_value = [mock_webhook]
    mlflow_client._client.delete_webhook.return_value = None

    result = mlflow_client.delete_webhook_by_url("http://example.com/webhook")

    assert result is True
    mlflow_client._client.delete_webhook.assert_called_once_with("webhook-1")


def test_delete_webhook_by_url_not_found(mlflow_client):
    """Test deleting a webhook by URL when it doesn't exist."""
    mlflow_client._client.list_webhooks.return_value = []

    result = mlflow_client.delete_webhook_by_url("http://example.com/webhook")

    assert result is False
    mlflow_client._client.delete_webhook.assert_not_called()


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


@pytest.mark.asyncio
async def test_get_model_version(mlflow_client):
    """Test fetching model version details."""
    mock_model_version = ModelVersion(
        name="test-model",
        version="1",
        creation_timestamp=1234567890,
        last_updated_timestamp=1234567890,
        description="Test model",
        user_id="test-user",
        current_stage="Production",
        source="gs://test-bucket/1/abc123/artifacts/model",
        run_id="abc123",
        status="READY",
        status_message=None,
        tags={},
        run_link=None,
        aliases=[]
    )

    mlflow_client._client.get_model_version.return_value = mock_model_version

    result = await mlflow_client.get_model_version("test-model", "1")

    assert result["name"] == "test-model"
    assert result["version"] == "1"
    assert result["run_id"] == "abc123"
    assert result["status"] == "READY"
    assert result["source"] == "gs://test-bucket/1/abc123/artifacts/model"
    assert result["current_stage"] == "Production"
    mlflow_client._client.get_model_version.assert_called_once_with(name="test-model", version="1")


@pytest.mark.asyncio
async def test_get_model_version_error(mlflow_client):
    """Test get_model_version with error."""
    mlflow_client._client.get_model_version.side_effect = Exception("Model not found")

    with pytest.raises(Exception, match="Model not found"):
        await mlflow_client.get_model_version("test-model", "999")


@pytest.mark.asyncio
async def test_get_run(mlflow_client):
    """Test fetching run details."""
    mock_run_info = RunInfo(
        run_id="abc123",
        experiment_id="1",
        user_id="test-user",
        status="FINISHED",
        start_time=1234567890,
        end_time=1234567900,
        lifecycle_stage="active",
        artifact_uri="gs://test-bucket/1/abc123/artifacts"
    )
    mock_run = Run(run_info=mock_run_info, run_data=MagicMock())

    mlflow_client._client.get_run.return_value = mock_run

    result = await mlflow_client.get_run("abc123")

    assert result["run_id"] == "abc123"
    assert result["experiment_id"] == "1"
    assert result["artifact_uri"] == "gs://test-bucket/1/abc123/artifacts"
    assert result["status"] == "FINISHED"
    mlflow_client._client.get_run.assert_called_once_with(run_id="abc123")


@pytest.mark.asyncio
async def test_get_run_error(mlflow_client):
    """Test get_run with error."""
    mlflow_client._client.get_run.side_effect = Exception("Run not found")

    with pytest.raises(Exception, match="Run not found"):
        await mlflow_client.get_run("invalid-run-id")


@pytest.mark.asyncio
async def test_get_storage_uri(mlflow_client):
    """Test getting storage URI from model version source."""
    mock_model_version = ModelVersion(
        name="test-model",
        version="1",
        creation_timestamp=1234567890,
        last_updated_timestamp=1234567890,
        description="Test model",
        user_id="test-user",
        current_stage="Production",
        source="mlflow-artifacts:/1/models/m-abc123/artifacts",
        run_id="abc123",
        status="READY",
        status_message=None,
        tags={},
        run_link=None,
        aliases=[]
    )

    mlflow_client._client.get_model_version.return_value = mock_model_version

    result = await mlflow_client.get_storage_uri("test-model", "1")

    assert result == "mlflow-artifacts:/1/models/m-abc123/artifacts"


@pytest.mark.asyncio
async def test_get_storage_uri_error(mlflow_client):
    """Test get_storage_uri with error."""
    mlflow_client._client.get_model_version.side_effect = Exception("Model not found")

    with pytest.raises(Exception, match="Model not found"):
        await mlflow_client.get_storage_uri("test-model", "999")


@pytest.mark.asyncio
async def test_get_storage_uri_empty_source(mlflow_client):
    """Test get_storage_uri when source is empty."""
    mock_model_version = ModelVersion(
        name="test-model",
        version="1",
        creation_timestamp=1234567890,
        last_updated_timestamp=1234567890,
        description="Test model",
        user_id="test-user",
        current_stage="Production",
        source="",  # Empty source
        run_id="abc123",
        status="READY",
        status_message=None,
        tags={},
        run_link=None,
        aliases=[]
    )

    mlflow_client._client.get_model_version.return_value = mock_model_version

    with pytest.raises(ValueError, match="has no source URI"):
        await mlflow_client.get_storage_uri("test-model", "1")
