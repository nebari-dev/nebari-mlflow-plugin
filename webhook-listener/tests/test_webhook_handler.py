"""Tests for webhook handler and signature verification."""

import base64
import hashlib
import hmac
from unittest.mock import AsyncMock, patch

import pytest
from src.webhook_handler import (
    handle_tag_deleted_event,
    handle_tag_set_event,
    process_webhook_event,
    verify_mlflow_signature,
    verify_timestamp_freshness,
)


class TestVerifyMLflowSignature:
    """Test cases for MLflow webhook signature verification."""

    def test_valid_signature(self):
        """Test that a valid signature is accepted."""
        secret = "test-secret"
        delivery_id = "abc123"
        timestamp = "1234567890"
        payload = '{"test": "data"}'

        # Generate a valid signature
        signed_content = f"{delivery_id}.{timestamp}.{payload}"
        signature_digest = hmac.new(
            secret.encode("utf-8"), signed_content.encode("utf-8"), hashlib.sha256
        ).digest()
        signature = "v1," + base64.b64encode(signature_digest).decode("utf-8")

        result = verify_mlflow_signature(
            payload=payload,
            signature=signature,
            secret=secret,
            delivery_id=delivery_id,
            timestamp=timestamp,
        )

        assert result is True

    def test_invalid_signature(self):
        """Test that an invalid signature is rejected."""
        secret = "test-secret"
        delivery_id = "abc123"
        timestamp = "1234567890"
        payload = '{"test": "data"}'

        # Create an incorrect signature
        wrong_secret = "wrong-secret"
        signed_content = f"{delivery_id}.{timestamp}.{payload}"
        signature_digest = hmac.new(
            wrong_secret.encode("utf-8"), signed_content.encode("utf-8"), hashlib.sha256
        ).digest()
        signature = "v1," + base64.b64encode(signature_digest).decode("utf-8")

        result = verify_mlflow_signature(
            payload=payload,
            signature=signature,
            secret=secret,
            delivery_id=delivery_id,
            timestamp=timestamp,
        )

        assert result is False

    def test_missing_version_prefix(self):
        """Test that signatures without 'v1,' prefix are rejected."""
        secret = "test-secret"
        delivery_id = "abc123"
        timestamp = "1234567890"
        payload = '{"test": "data"}'

        # Create signature without version prefix
        signed_content = f"{delivery_id}.{timestamp}.{payload}"
        signature_digest = hmac.new(
            secret.encode("utf-8"), signed_content.encode("utf-8"), hashlib.sha256
        ).digest()
        signature = base64.b64encode(signature_digest).decode("utf-8")  # No 'v1,' prefix

        result = verify_mlflow_signature(
            payload=payload,
            signature=signature,
            secret=secret,
            delivery_id=delivery_id,
            timestamp=timestamp,
        )

        assert result is False

    def test_wrong_version_prefix(self):
        """Test that signatures with wrong version prefix are rejected."""
        secret = "test-secret"
        delivery_id = "abc123"
        timestamp = "1234567890"
        payload = '{"test": "data"}'

        # Create signature with wrong version
        signed_content = f"{delivery_id}.{timestamp}.{payload}"
        signature_digest = hmac.new(
            secret.encode("utf-8"), signed_content.encode("utf-8"), hashlib.sha256
        ).digest()
        signature = "v2," + base64.b64encode(signature_digest).decode("utf-8")

        result = verify_mlflow_signature(
            payload=payload,
            signature=signature,
            secret=secret,
            delivery_id=delivery_id,
            timestamp=timestamp,
        )

        assert result is False

    def test_tampered_payload(self):
        """Test that signature verification fails if payload is tampered with."""
        secret = "test-secret"
        delivery_id = "abc123"
        timestamp = "1234567890"
        original_payload = '{"test": "data"}'

        # Generate signature for original payload
        signed_content = f"{delivery_id}.{timestamp}.{original_payload}"
        signature_digest = hmac.new(
            secret.encode("utf-8"), signed_content.encode("utf-8"), hashlib.sha256
        ).digest()
        signature = "v1," + base64.b64encode(signature_digest).decode("utf-8")

        # Try to verify with tampered payload
        tampered_payload = '{"test": "modified"}'

        result = verify_mlflow_signature(
            payload=tampered_payload,
            signature=signature,
            secret=secret,
            delivery_id=delivery_id,
            timestamp=timestamp,
        )

        assert result is False

    def test_empty_signature(self):
        """Test that empty signature is rejected."""
        result = verify_mlflow_signature(
            payload='{"test": "data"}',
            signature="",
            secret="test-secret",
            delivery_id="abc123",
            timestamp="1234567890",
        )

        assert result is False

    def test_malformed_signature(self):
        """Test that malformed signature is rejected."""
        result = verify_mlflow_signature(
            payload='{"test": "data"}',
            signature="v1,not-valid-base64!!!",
            secret="test-secret",
            delivery_id="abc123",
            timestamp="1234567890",
        )

        assert result is False


class TestVerifyTimestampFreshness:
    """Test cases for timestamp freshness verification."""

    @patch("time.time")
    def test_fresh_timestamp(self, mock_time):
        """Test that a fresh timestamp is accepted."""
        current_time = 1234567890
        mock_time.return_value = current_time

        # Timestamp from 100 seconds ago (well within 300 second limit)
        timestamp_str = str(current_time - 100)

        result = verify_timestamp_freshness(timestamp_str)

        assert result is True

    @patch("time.time")
    def test_timestamp_at_max_age(self, mock_time):
        """Test that a timestamp exactly at max age is accepted."""
        current_time = 1234567890
        mock_time.return_value = current_time

        # Timestamp exactly 300 seconds ago
        timestamp_str = str(current_time - 300)

        result = verify_timestamp_freshness(timestamp_str, max_age=300)

        assert result is True

    @patch("time.time")
    def test_timestamp_too_old(self, mock_time):
        """Test that an old timestamp is rejected."""
        current_time = 1234567890
        mock_time.return_value = current_time

        # Timestamp from 301 seconds ago (exceeds 300 second limit)
        timestamp_str = str(current_time - 301)

        result = verify_timestamp_freshness(timestamp_str, max_age=300)

        assert result is False

    @patch("time.time")
    def test_timestamp_in_future(self, mock_time):
        """Test that a future timestamp is rejected."""
        current_time = 1234567890
        mock_time.return_value = current_time

        # Timestamp from 100 seconds in the future
        timestamp_str = str(current_time + 100)

        result = verify_timestamp_freshness(timestamp_str)

        assert result is False

    @patch("time.time")
    def test_current_timestamp(self, mock_time):
        """Test that current timestamp is accepted."""
        current_time = 1234567890
        mock_time.return_value = current_time

        timestamp_str = str(current_time)

        result = verify_timestamp_freshness(timestamp_str)

        assert result is True

    def test_invalid_timestamp_format(self):
        """Test that invalid timestamp format is rejected."""
        result = verify_timestamp_freshness("not-a-number")

        assert result is False

    def test_empty_timestamp(self):
        """Test that empty timestamp is rejected."""
        result = verify_timestamp_freshness("")

        assert result is False

    def test_none_timestamp(self):
        """Test that None timestamp is rejected."""
        result = verify_timestamp_freshness(None)

        assert result is False

    @patch("time.time")
    def test_custom_max_age(self, mock_time):
        """Test timestamp verification with custom max age."""
        current_time = 1234567890
        mock_time.return_value = current_time

        # Timestamp from 400 seconds ago
        timestamp_str = str(current_time - 400)

        # Should fail with default 300 second max age
        assert verify_timestamp_freshness(timestamp_str) is False

        # Should succeed with 600 second max age
        assert verify_timestamp_freshness(timestamp_str, max_age=600) is True


class TestProcessWebhookEvent:
    """Test cases for webhook event processing."""

    @pytest.mark.asyncio
    async def test_process_webhook_event_tag_set(self):
        """Test webhook event processing for tag set event."""
        webhook_data = {
            "entity": "model_version_tag",
            "action": "set",
            "timestamp": 1234567890,
            "data": {
                "name": "iris-classifier",
                "version": "3",
                "key": "deploy",
                "value": "true",
            },
        }

        result = await process_webhook_event(webhook_data, "delivery-123")

        assert result["status"] == "success"
        assert result["entity"] == "model_version_tag"
        assert result["action"] == "set"
        assert result["delivery_id"] == "delivery-123"

    @pytest.mark.asyncio
    async def test_process_webhook_event_tag_deleted(self):
        """Test webhook event processing for tag deleted event."""
        webhook_data = {
            "entity": "model_version_tag",
            "action": "deleted",
            "timestamp": 1234567890,
            "data": {
                "name": "iris-classifier",
                "version": "3",
                "key": "deploy",
            },
        }

        result = await process_webhook_event(webhook_data, "delivery-123")

        assert result["status"] == "success"
        assert result["entity"] == "model_version_tag"
        assert result["action"] == "deleted"
        assert result["delivery_id"] == "delivery-123"

    @pytest.mark.asyncio
    async def test_process_webhook_event_unsupported_event(self):
        """Test webhook event processing with unsupported event type."""
        webhook_data = {
            "entity": "registered_model",
            "action": "created",
            "timestamp": 1234567890,
            "data": {
                "name": "iris-classifier",
            },
        }

        result = await process_webhook_event(webhook_data, "delivery-123")

        assert result["status"] == "success"
        assert result["entity"] == "registered_model"
        assert result["action"] == "created"
        assert "not handled" in result["message"]

    @pytest.mark.asyncio
    async def test_process_webhook_event_missing_fields(self):
        """Test webhook event processing with missing fields."""
        webhook_data = {}

        result = await process_webhook_event(webhook_data, "delivery-123")

        assert result["status"] == "success"
        assert result["entity"] is None
        assert result["action"] is None


class TestHandleTagSetEvent:
    """Test cases for tag set event handler."""

    @pytest.mark.asyncio
    @patch("src.webhook_handler.k8s_client")
    @patch("src.webhook_handler.mlflow_client")
    async def test_handle_tag_set_event_deploy_true(self, mock_mlflow_client, mock_k8s_client):
        """Test handling of deploy tag set to true."""
        # Mock MLflow client responses (need to use AsyncMock for async methods)
        mock_mlflow_client.get_model_version = AsyncMock(return_value={
            "name": "iris-classifier",
            "version": "3",
            "run_id": "test-run-123",
            "status": "READY",
            "source": "mlflow-artifacts:/1/models/m-abc123/artifacts",
        })
        mock_mlflow_client.get_run = AsyncMock(return_value={
            "run_id": "test-run-123",
            "experiment_id": "1",
            "artifact_uri": "mlflow-artifacts:/1/abc123/artifacts",
        })

        # Mock Kubernetes client
        mock_k8s_client.update_inference_service = AsyncMock(return_value={
            "status": "updated",
            "name": "iris-classifier-v3",
            "namespace": "kserve-mlflow-models",
            "uid": "test-uid-123",
        })

        data = {
            "name": "iris-classifier",
            "version": "3",
            "key": "deploy",
            "value": "true",
        }

        result = await handle_tag_set_event(data)

        assert result["action"] == "deployed"
        assert result["model_name"] == "iris-classifier"
        assert result["version"] == "3"
        assert result["service_name"] == "iris-classifier-v3"
        assert result["status"] == "updated"
        mock_mlflow_client.get_model_version.assert_called_once_with("iris-classifier", "3")
        mock_mlflow_client.get_run.assert_called_once_with("test-run-123")
        mock_k8s_client.update_inference_service.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.webhook_handler.k8s_client")
    async def test_handle_tag_set_event_deploy_false(self, mock_k8s_client):
        """Test handling of deploy tag set to false."""
        # Mock Kubernetes client
        mock_k8s_client.delete_inference_service = AsyncMock(return_value={
            "status": "deleted",
            "name": "iris-classifier-v3",
            "namespace": "kserve-mlflow-models",
        })

        data = {
            "name": "iris-classifier",
            "version": "3",
            "key": "deploy",
            "value": "false",
        }

        result = await handle_tag_set_event(data)

        assert result["action"] == "undeployed"
        assert result["service_name"] == "iris-classifier-v3"
        mock_k8s_client.delete_inference_service.assert_called_once_with("iris-classifier-v3")
        assert result["model_name"] == "iris-classifier"
        assert result["version"] == "3"

    @pytest.mark.asyncio
    async def test_handle_tag_set_event_non_deploy_tag(self):
        """Test handling of non-deploy tag (should be ignored)."""
        data = {
            "name": "iris-classifier",
            "version": "3",
            "key": "stage",
            "value": "production",
        }

        result = await handle_tag_set_event(data)

        assert result["action"] == "ignored"
        assert "not 'deploy'" in result["reason"]

    @pytest.mark.asyncio
    async def test_handle_tag_set_event_invalid_value(self):
        """Test handling of deploy tag with invalid value."""
        data = {
            "name": "iris-classifier",
            "version": "3",
            "key": "deploy",
            "value": "maybe",
        }

        result = await handle_tag_set_event(data)

        assert result["action"] == "ignored"
        assert "not 'true' or 'false'" in result["reason"]

    @pytest.mark.asyncio
    async def test_handle_tag_set_event_empty_data(self):
        """Test handling of tag set event with empty data."""
        data = {}

        result = await handle_tag_set_event(data)

        assert result["action"] == "ignored"

    @pytest.mark.asyncio
    @patch("src.webhook_handler.mlflow_client")
    async def test_handle_tag_set_event_mlflow_error(self, mock_mlflow_client):
        """Test handling of deploy tag when MLflow API fails."""
        # Mock MLflow client to raise an exception
        mock_mlflow_client.get_model_version = AsyncMock(side_effect=Exception("MLflow API error"))

        data = {
            "name": "iris-classifier",
            "version": "3",
            "key": "deploy",
            "value": "true",
        }

        result = await handle_tag_set_event(data)

        assert result["action"] == "error"
        assert result["model_name"] == "iris-classifier"
        assert result["version"] == "3"
        assert "Failed to fetch model details from MLflow" in result["message"]


class TestHandleTagDeletedEvent:
    """Test cases for tag deleted event handler."""

    @pytest.mark.asyncio
    @patch("src.webhook_handler.k8s_client")
    async def test_handle_tag_deleted_event_deploy_tag(self, mock_k8s_client):
        """Test handling of deploy tag deletion."""
        # Mock Kubernetes client
        mock_k8s_client.delete_inference_service = AsyncMock(return_value={
            "status": "deleted",
            "name": "iris-classifier-v3",
            "namespace": "kserve-mlflow-models",
        })

        data = {
            "name": "iris-classifier",
            "version": "3",
            "key": "deploy",
        }

        result = await handle_tag_deleted_event(data)

        assert result["action"] == "undeployed"
        assert result["model_name"] == "iris-classifier"
        assert result["version"] == "3"
        assert result["service_name"] == "iris-classifier-v3"
        mock_k8s_client.delete_inference_service.assert_called_once_with("iris-classifier-v3")

    @pytest.mark.asyncio
    async def test_handle_tag_deleted_event_non_deploy_tag(self):
        """Test handling of non-deploy tag deletion (should be ignored)."""
        data = {
            "name": "iris-classifier",
            "version": "3",
            "key": "stage",
        }

        result = await handle_tag_deleted_event(data)

        assert result["action"] == "ignored"
        assert "not 'deploy'" in result["reason"]

    @pytest.mark.asyncio
    async def test_handle_tag_deleted_event_empty_data(self):
        """Test handling of tag deleted event with empty data."""
        data = {}

        result = await handle_tag_deleted_event(data)

        assert result["action"] == "ignored"
