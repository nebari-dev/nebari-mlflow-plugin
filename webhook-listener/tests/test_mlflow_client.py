"""Tests for MLflow client webhook management."""

from unittest.mock import MagicMock, patch

import pytest
from mlflow.entities import Run, RunInfo
from mlflow.entities.model_registry import ModelVersion
from src.mlflow_client import MLflowClient, resolve_mlflow_artifacts_uri


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


# Tests for ensure_webhook_registered_with_timeout were removed
# That method has been replaced with the generic @with_timeout_and_retry decorator
# See tests/test_timeout_utils.py for decorator tests


@pytest.mark.asyncio
async def test_get_models_with_deploy_tag_success(mlflow_client):
    """Test getting models with deploy=true tag."""
    # Mock registered models
    mock_model1 = MagicMock()
    mock_model1.name = "model-a"

    mock_model2 = MagicMock()
    mock_model2.name = "model-b"

    mlflow_client._client.search_registered_models.return_value = [mock_model1, mock_model2]

    # Mock model versions for model-a (has deploy=true)
    mock_version_a1 = MagicMock()
    mock_version_a1.version = "1"
    mock_version_a1.run_id = "run-a1"
    mock_version_a1.source = "s3://bucket/model-a"
    mock_version_a1.tags = {"deploy": "true"}

    # Mock model versions for model-b (no deploy tag)
    mock_version_b1 = MagicMock()
    mock_version_b1.version = "1"
    mock_version_b1.run_id = "run-b1"
    mock_version_b1.source = "s3://bucket/model-b"
    mock_version_b1.tags = {}

    def search_versions_side_effect(filter_string):
        if "model-a" in filter_string:
            return [mock_version_a1]
        elif "model-b" in filter_string:
            return [mock_version_b1]
        return []

    mlflow_client._client.search_model_versions.side_effect = search_versions_side_effect

    result = await mlflow_client.get_models_with_deploy_tag()

    assert len(result) == 1
    assert result[0]["name"] == "model-a"
    assert result[0]["version"] == "1"
    assert result[0]["run_id"] == "run-a1"
    assert result[0]["source"] == "s3://bucket/model-a"
    assert result[0]["tags"]["deploy"] == "true"


@pytest.mark.asyncio
async def test_get_models_with_deploy_tag_no_models(mlflow_client):
    """Test getting models when none have deploy=true tag."""
    mlflow_client._client.search_registered_models.return_value = []

    result = await mlflow_client.get_models_with_deploy_tag()

    assert len(result) == 0


@pytest.mark.asyncio
async def test_get_models_with_deploy_tag_multiple_versions(mlflow_client):
    """Test getting multiple versions of same model with deploy tag."""
    # Mock registered model
    mock_model = MagicMock()
    mock_model.name = "test-model"

    mlflow_client._client.search_registered_models.return_value = [mock_model]

    # Mock multiple versions with deploy=true
    mock_version1 = MagicMock()
    mock_version1.version = "1"
    mock_version1.run_id = "run-1"
    mock_version1.source = "s3://bucket/v1"
    mock_version1.tags = {"deploy": "true"}

    mock_version2 = MagicMock()
    mock_version2.version = "2"
    mock_version2.run_id = "run-2"
    mock_version2.source = "s3://bucket/v2"
    mock_version2.tags = {"deploy": "true"}

    mock_version3 = MagicMock()
    mock_version3.version = "3"
    mock_version3.run_id = "run-3"
    mock_version3.source = "s3://bucket/v3"
    mock_version3.tags = {"deploy": "false"}  # Should be excluded

    mlflow_client._client.search_model_versions.return_value = [
        mock_version1, mock_version2, mock_version3
    ]

    result = await mlflow_client.get_models_with_deploy_tag()

    assert len(result) == 2
    assert result[0]["version"] == "1"
    assert result[1]["version"] == "2"


@pytest.mark.asyncio
async def test_get_models_with_deploy_tag_handles_errors(mlflow_client):
    """Test that get_models_with_deploy_tag handles errors gracefully."""
    mlflow_client._client.search_registered_models.side_effect = Exception("MLflow error")

    result = await mlflow_client.get_models_with_deploy_tag()

    # Should return empty list instead of raising
    assert len(result) == 0


@pytest.mark.asyncio
async def test_get_models_with_deploy_tag_none_tags(mlflow_client):
    """Test handling versions with None tags."""
    mock_model = MagicMock()
    mock_model.name = "test-model"

    mlflow_client._client.search_registered_models.return_value = [mock_model]

    # Mock version with None tags
    mock_version = MagicMock()
    mock_version.version = "1"
    mock_version.run_id = "run-1"
    mock_version.source = "s3://bucket/v1"
    mock_version.tags = None  # None instead of dict

    mlflow_client._client.search_model_versions.return_value = [mock_version]

    result = await mlflow_client.get_models_with_deploy_tag()

    # Should handle None tags gracefully
    assert len(result) == 0


class TestResolveMLflowArtifactsUri:
    """Tests for resolve_mlflow_artifacts_uri function."""

    @patch("src.mlflow_client.settings")
    def test_resolve_mlflow_artifacts_uri_with_double_slash(self, mock_settings):
        """Test resolving mlflow-artifacts:// URI with double slash."""
        mock_settings.artifacts_uri = "gs://nebari-mlflow-artifacts"

        source = "mlflow-artifacts://1/models/m-abc123/artifacts"
        result = resolve_mlflow_artifacts_uri(source)

        assert result == "gs://nebari-mlflow-artifacts/1/models/m-abc123/artifacts"

    @patch("src.mlflow_client.settings")
    def test_resolve_mlflow_artifacts_uri_with_single_slash(self, mock_settings):
        """Test resolving mlflow-artifacts:/ URI with single slash."""
        mock_settings.artifacts_uri = "gs://my-bucket"

        source = "mlflow-artifacts:/1/models/m-xyz789/artifacts"
        result = resolve_mlflow_artifacts_uri(source)

        assert result == "gs://my-bucket/1/models/m-xyz789/artifacts"

    @patch("src.mlflow_client.settings")
    def test_resolve_mlflow_artifacts_uri_with_trailing_slash_in_base(self, mock_settings):
        """Test that trailing slash in artifacts_uri is handled correctly."""
        mock_settings.artifacts_uri = "s3://my-bucket/"

        source = "mlflow-artifacts:/1/abc123/artifacts"
        result = resolve_mlflow_artifacts_uri(source)

        assert result == "s3://my-bucket/1/abc123/artifacts"

    @patch("src.mlflow_client.settings")
    def test_resolve_already_resolved_gs_uri(self, mock_settings):
        """Test that already resolved gs:// URIs are returned as-is."""
        mock_settings.artifacts_uri = "gs://nebari-mlflow-artifacts"

        source = "gs://nebari-mlflow-artifacts/1/487892df/artifacts/best_estimator"
        result = resolve_mlflow_artifacts_uri(source)

        assert result == source

    @patch("src.mlflow_client.settings")
    def test_resolve_already_resolved_s3_uri(self, mock_settings):
        """Test that already resolved s3:// URIs are returned as-is."""
        mock_settings.artifacts_uri = "s3://my-bucket"

        source = "s3://my-bucket/path/to/model"
        result = resolve_mlflow_artifacts_uri(source)

        assert result == source

    @patch("src.mlflow_client.settings")
    def test_resolve_with_azure_storage(self, mock_settings):
        """Test resolving with Azure blob storage URI."""
        mock_settings.artifacts_uri = "wasbs://container@account.blob.core.windows.net"

        source = "mlflow-artifacts:/1/models/m-abc123/artifacts"
        result = resolve_mlflow_artifacts_uri(source)

        assert result == "wasbs://container@account.blob.core.windows.net/1/models/m-abc123/artifacts"
