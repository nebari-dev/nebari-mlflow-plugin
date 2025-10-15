"""Tests for FastAPI endpoints."""
import base64
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch


def test_health_endpoint(client):
    """Test the /health endpoint returns simple health status."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@patch("src.main.KubernetesClient")
@patch("src.main.MLflowClient")
def test_detailed_health_endpoint(mock_mlflow_client, mock_k8s_client, client):
    """Test the /health/detailed endpoint returns detailed health status."""
    # Mock MLflow connectivity success
    mock_mlflow_instance = mock_mlflow_client.return_value
    mock_mlflow_instance.list_webhooks.return_value = ["webhook1", "webhook2"]

    # Mock Kubernetes connectivity success
    mock_k8s_instance = mock_k8s_client.return_value
    mock_k8s_instance.list_inference_services = AsyncMock(return_value=[
        {"name": "service1", "labels": {}},
        {"name": "service2", "labels": {}}
    ])

    response = client.get("/health/detailed")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["mlflow_connected"] is True
    assert data["kubernetes_connected"] is True
    assert "details" in data
    assert data["details"]["mlflow"]["webhook_count"] == 2
    assert data["details"]["kubernetes"]["managed_services_count"] == 2


@patch("src.main.KubernetesClient")
@patch("src.main.MLflowClient")
def test_detailed_health_endpoint_mlflow_failure(mock_mlflow_client, mock_k8s_client, client):
    """Test the /health/detailed endpoint when MLflow is unavailable."""
    # Mock MLflow connectivity failure
    mock_mlflow_instance = mock_mlflow_client.return_value
    mock_mlflow_instance.list_webhooks.side_effect = Exception("MLflow connection failed")

    # Mock Kubernetes connectivity success
    mock_k8s_instance = mock_k8s_client.return_value
    mock_k8s_instance.list_inference_services = AsyncMock(return_value=[])

    response = client.get("/health/detailed")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["mlflow_connected"] is False
    assert data["kubernetes_connected"] is True
    assert "mlflow_error" in data["details"]


@patch("src.main.KubernetesClient")
@patch("src.main.MLflowClient")
def test_detailed_health_endpoint_kubernetes_failure(mock_mlflow_client, mock_k8s_client, client):
    """Test the /health/detailed endpoint when Kubernetes is unavailable."""
    # Mock MLflow connectivity success
    mock_mlflow_instance = mock_mlflow_client.return_value
    mock_mlflow_instance.list_webhooks.return_value = []

    # Mock Kubernetes connectivity failure
    mock_k8s_client.side_effect = Exception("Kubernetes connection failed")

    response = client.get("/health/detailed")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["mlflow_connected"] is True
    assert data["kubernetes_connected"] is False
    assert "kubernetes_error" in data["details"]


@patch("src.main.KubernetesClient")
def test_services_endpoint(mock_k8s_client, client):
    """Test the /services endpoint returns list of managed InferenceServices."""
    # Mock Kubernetes client to return sample services
    mock_k8s_instance = mock_k8s_client.return_value
    mock_k8s_instance.list_inference_services = AsyncMock(return_value=[
        {
            "name": "mlflow-model1-v1",
            "namespace": "kserve-mlflow-models",
            "labels": {
                "mlflow.model": "model1",
                "mlflow.version": "1",
                "mlflow.run-id": "run123"
            },
            "status": {
                "conditions": [
                    {"type": "Ready", "status": "True"}
                ],
                "url": "https://model1.example.com"
            },
            "creation_timestamp": "2024-01-01T00:00:00Z"
        },
        {
            "name": "mlflow-model2-v2",
            "namespace": "kserve-mlflow-models",
            "labels": {
                "mlflow.model": "model2",
                "mlflow.version": "2",
                "mlflow.run-id": "run456"
            },
            "status": {
                "conditions": [
                    {"type": "Ready", "status": "False"}
                ]
            },
            "creation_timestamp": "2024-01-02T00:00:00Z"
        }
    ])
    
    response = client.get("/services")

    assert response.status_code == 200
    data = response.json()
    assert "services" in data
    assert isinstance(data["services"], list)
    assert len(data["services"]) == 2
    assert data["total"] == 2
    
    # Check first service
    service1 = data["services"][0]
    assert service1["name"] == "mlflow-model1-v1"
    assert service1["model_name"] == "model1"
    assert service1["model_version"] == "1"
    assert service1["run_id"] == "run123"
    assert service1["status"] == "Ready"
    assert service1["url"] == "https://model1.example.com"
    
    # Check second service
    service2 = data["services"][1]
    assert service2["name"] == "mlflow-model2-v2"
    assert service2["model_name"] == "model2"
    assert service2["model_version"] == "2"
    assert service2["status"] == "Not Ready"
    assert service2["url"] is None


@patch("src.main.KubernetesClient")
def test_services_endpoint_empty_list(mock_k8s_client, client):
    """Test the /services endpoint when no services are deployed."""
    # Mock Kubernetes client to return empty list
    mock_k8s_instance = mock_k8s_client.return_value
    mock_k8s_instance.list_inference_services = AsyncMock(return_value=[])
    
    response = client.get("/services")

    assert response.status_code == 200
    data = response.json()
    assert "services" in data
    assert isinstance(data["services"], list)
    assert len(data["services"]) == 0
    assert data["total"] == 0


@patch("src.main.KubernetesClient")
def test_services_endpoint_error_handling(mock_k8s_client, client):
    """Test the /services endpoint handles errors gracefully."""
    # Mock Kubernetes client to raise an exception
    mock_k8s_instance = mock_k8s_client.return_value
    mock_k8s_instance.list_inference_services = AsyncMock(side_effect=Exception("Kubernetes API error"))
    
    response = client.get("/services")

    assert response.status_code == 500
    data = response.json()
    assert "Error listing InferenceServices" in data["detail"]


class TestWebhookEndpointSignatureVerification:
    """Test webhook endpoint with signature verification."""

    def _generate_valid_signature(self, payload: dict, delivery_id: str, timestamp: str, secret: str) -> str:
        """Helper to generate a valid MLflow webhook signature."""
        # Use separators to match FastAPI/Starlette JSON encoding (no spaces after separators)
        payload_str = json.dumps(payload, separators=(",", ":"))
        signed_content = f"{delivery_id}.{timestamp}.{payload_str}"
        signature_digest = hmac.new(
            secret.encode("utf-8"),
            signed_content.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return "v1," + base64.b64encode(signature_digest).decode("utf-8")

    @patch("src.webhook_handler.time.time")
    def test_webhook_with_valid_signature(self, mock_time, client, sample_webhook_payload):
        """Test webhook endpoint accepts request with valid signature."""
        mock_time.return_value = 1234567890

        delivery_id = "test-delivery-123"
        timestamp = "1234567890"
        secret = "test-secret"

        signature = self._generate_valid_signature(
            sample_webhook_payload, delivery_id, timestamp, secret
        )

        response = client.post(
            "/webhook",
            json=sample_webhook_payload,
            headers={
                "x-mlflow-signature": signature,
                "x-mlflow-delivery-id": delivery_id,
                "x-mlflow-timestamp": timestamp,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["delivery_id"] == delivery_id

    @patch("src.webhook_handler.time.time")
    def test_webhook_with_invalid_signature(self, mock_time, client, sample_webhook_payload):
        """Test webhook endpoint rejects request with invalid signature."""
        mock_time.return_value = 1234567890

        delivery_id = "test-delivery-456"
        timestamp = "1234567890"
        wrong_secret = "wrong-secret"

        # Generate signature with wrong secret
        signature = self._generate_valid_signature(
            sample_webhook_payload, delivery_id, timestamp, wrong_secret
        )

        response = client.post(
            "/webhook",
            json=sample_webhook_payload,
            headers={
                "x-mlflow-signature": signature,
                "x-mlflow-delivery-id": delivery_id,
                "x-mlflow-timestamp": timestamp,
            },
        )

        assert response.status_code == 401
        assert "Invalid webhook signature" in response.json()["detail"]

    def test_webhook_missing_signature_header(self, client, sample_webhook_payload):
        """Test webhook endpoint rejects request without signature header."""
        response = client.post(
            "/webhook",
            json=sample_webhook_payload,
            headers={
                "x-mlflow-delivery-id": "test-789",
                "x-mlflow-timestamp": "1234567890",
            },
        )

        assert response.status_code == 400
        assert "Missing required headers" in response.json()["detail"]

    def test_webhook_missing_delivery_id_header(self, client, sample_webhook_payload):
        """Test webhook endpoint rejects request without delivery ID header."""
        response = client.post(
            "/webhook",
            json=sample_webhook_payload,
            headers={
                "x-mlflow-signature": "v1,somesig",
                "x-mlflow-timestamp": "1234567890",
            },
        )

        assert response.status_code == 400
        assert "Missing required headers" in response.json()["detail"]

    def test_webhook_missing_timestamp_header(self, client, sample_webhook_payload):
        """Test webhook endpoint rejects request without timestamp header."""
        response = client.post(
            "/webhook",
            json=sample_webhook_payload,
            headers={
                "x-mlflow-signature": "v1,somesig",
                "x-mlflow-delivery-id": "test-101",
            },
        )

        assert response.status_code == 400
        assert "Missing required headers" in response.json()["detail"]

    @patch("src.webhook_handler.time.time")
    def test_webhook_with_stale_timestamp(self, mock_time, client, sample_webhook_payload):
        """Test webhook endpoint rejects request with stale timestamp."""
        current_time = 1234567890
        mock_time.return_value = current_time

        # Timestamp from 400 seconds ago (exceeds 300 second limit)
        delivery_id = "test-stale-123"
        stale_timestamp = str(current_time - 400)
        secret = "test-secret"

        signature = self._generate_valid_signature(
            sample_webhook_payload, delivery_id, stale_timestamp, secret
        )

        response = client.post(
            "/webhook",
            json=sample_webhook_payload,
            headers={
                "x-mlflow-signature": signature,
                "x-mlflow-delivery-id": delivery_id,
                "x-mlflow-timestamp": stale_timestamp,
            },
        )

        assert response.status_code == 401
        assert "timestamp is stale" in response.json()["detail"]

    @patch("src.webhook_handler.time.time")
    def test_webhook_with_future_timestamp(self, mock_time, client, sample_webhook_payload):
        """Test webhook endpoint rejects request with future timestamp."""
        current_time = 1234567890
        mock_time.return_value = current_time

        # Timestamp from 100 seconds in the future
        delivery_id = "test-future-123"
        future_timestamp = str(current_time + 100)
        secret = "test-secret"

        signature = self._generate_valid_signature(
            sample_webhook_payload, delivery_id, future_timestamp, secret
        )

        response = client.post(
            "/webhook",
            json=sample_webhook_payload,
            headers={
                "x-mlflow-signature": signature,
                "x-mlflow-delivery-id": delivery_id,
                "x-mlflow-timestamp": future_timestamp,
            },
        )

        assert response.status_code == 401
        assert "timestamp is stale" in response.json()["detail"]

    @patch("src.webhook_handler.time.time")
    def test_webhook_with_tampered_payload(self, mock_time, client, sample_webhook_payload):
        """Test webhook endpoint rejects request with tampered payload."""
        mock_time.return_value = 1234567890

        delivery_id = "test-tampered-123"
        timestamp = "1234567890"
        secret = "test-secret"

        # Generate signature for original payload
        signature = self._generate_valid_signature(
            sample_webhook_payload, delivery_id, timestamp, secret
        )

        # Tamper with the payload
        tampered_payload = sample_webhook_payload.copy()
        tampered_payload["data"]["version"] = "999"  # Change version

        response = client.post(
            "/webhook",
            json=tampered_payload,
            headers={
                "x-mlflow-signature": signature,
                "x-mlflow-delivery-id": delivery_id,
                "x-mlflow-timestamp": timestamp,
            },
        )

        assert response.status_code == 401
        assert "Invalid webhook signature" in response.json()["detail"]


class TestWebhookEndpointEventRouting:
    """Test webhook endpoint event routing."""

    def _generate_valid_signature(self, payload: dict, delivery_id: str, timestamp: str, secret: str) -> str:
        """Helper to generate a valid MLflow webhook signature."""
        # Use separators to match FastAPI/Starlette JSON encoding (no spaces after separators)
        payload_str = json.dumps(payload, separators=(",", ":"))
        signed_content = f"{delivery_id}.{timestamp}.{payload_str}"
        signature_digest = hmac.new(
            secret.encode("utf-8"),
            signed_content.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return "v1," + base64.b64encode(signature_digest).decode("utf-8")

    @patch("src.webhook_handler.mlflow_client")
    @patch("src.webhook_handler.time.time")
    def test_webhook_deploy_tag_set_true(self, mock_time, mock_mlflow_client, client):
        """Test webhook endpoint handles deploy tag set to true."""
        mock_time.return_value = 1234567890

        # Mock MLflow client responses
        mock_mlflow_client.get_model_version = AsyncMock(return_value={
            "name": "test-model",
            "version": "1",
            "run_id": "test-run-123",
            "status": "READY",
            "source": "file:///mlflow/artifacts/1/test-run-123/artifacts/model",
        })
        mock_mlflow_client.get_run = AsyncMock(return_value={
            "run_id": "test-run-123",
            "experiment_id": "1",
            "artifact_uri": "file:///mlflow/artifacts/1/test-run-123/artifacts",
        })

        payload = {
            "entity": "model_version_tag",
            "action": "set",
            "timestamp": 1234567890,
            "data": {
                "name": "test-model",
                "version": "1",
                "key": "deploy",
                "value": "true",
                "run_id": "test-run-123",
                "experiment_id": "1",
            },
        }

        delivery_id = "deploy-true-123"
        timestamp = "1234567890"
        signature = self._generate_valid_signature(payload, delivery_id, timestamp, "test-secret")

        response = client.post(
            "/webhook",
            json=payload,
            headers={
                "x-mlflow-signature": signature,
                "x-mlflow-delivery-id": delivery_id,
                "x-mlflow-timestamp": timestamp,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["handler_result"]["action"] == "deployed"
        assert data["handler_result"]["model_name"] == "test-model"
        assert data["handler_result"]["version"] == "1"

    @patch("src.webhook_handler.time.time")
    def test_webhook_deploy_tag_set_false(self, mock_time, client):
        """Test webhook endpoint handles deploy tag set to false."""
        mock_time.return_value = 1234567890

        payload = {
            "entity": "model_version_tag",
            "action": "set",
            "timestamp": 1234567890,
            "data": {
                "name": "test-model",
                "version": "2",
                "key": "deploy",
                "value": "false",
            },
        }

        delivery_id = "deploy-false-123"
        timestamp = "1234567890"
        signature = self._generate_valid_signature(payload, delivery_id, timestamp, "test-secret")

        response = client.post(
            "/webhook",
            json=payload,
            headers={
                "x-mlflow-signature": signature,
                "x-mlflow-delivery-id": delivery_id,
                "x-mlflow-timestamp": timestamp,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["handler_result"]["action"] == "undeployed"

    @patch("src.webhook_handler.time.time")
    def test_webhook_deploy_tag_deleted(self, mock_time, client):
        """Test webhook endpoint handles deploy tag deletion."""
        mock_time.return_value = 1234567890

        payload = {
            "entity": "model_version_tag",
            "action": "deleted",
            "timestamp": 1234567890,
            "data": {
                "name": "test-model",
                "version": "3",
                "key": "deploy",
            },
        }

        delivery_id = "deploy-deleted-123"
        timestamp = "1234567890"
        signature = self._generate_valid_signature(payload, delivery_id, timestamp, "test-secret")

        response = client.post(
            "/webhook",
            json=payload,
            headers={
                "x-mlflow-signature": signature,
                "x-mlflow-delivery-id": delivery_id,
                "x-mlflow-timestamp": timestamp,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["handler_result"]["action"] == "undeployed"

    @patch("src.webhook_handler.time.time")
    def test_webhook_non_deploy_tag_ignored(self, mock_time, client):
        """Test webhook endpoint ignores non-deploy tags."""
        mock_time.return_value = 1234567890

        payload = {
            "entity": "model_version_tag",
            "action": "set",
            "timestamp": 1234567890,
            "data": {
                "name": "test-model",
                "version": "4",
                "key": "stage",
                "value": "production",
            },
        }

        delivery_id = "non-deploy-123"
        timestamp = "1234567890"
        signature = self._generate_valid_signature(payload, delivery_id, timestamp, "test-secret")

        response = client.post(
            "/webhook",
            json=payload,
            headers={
                "x-mlflow-signature": signature,
                "x-mlflow-delivery-id": delivery_id,
                "x-mlflow-timestamp": timestamp,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["handler_result"]["action"] == "ignored"

    @patch("src.webhook_handler.time.time")
    def test_webhook_unsupported_event_type(self, mock_time, client):
        """Test webhook endpoint handles unsupported event types gracefully."""
        mock_time.return_value = 1234567890

        payload = {
            "entity": "registered_model",
            "action": "created",
            "timestamp": 1234567890,
            "data": {"name": "new-model"},
        }

        delivery_id = "unsupported-123"
        timestamp = "1234567890"
        signature = self._generate_valid_signature(payload, delivery_id, timestamp, "test-secret")

        response = client.post(
            "/webhook",
            json=payload,
            headers={
                "x-mlflow-signature": signature,
                "x-mlflow-delivery-id": delivery_id,
                "x-mlflow-timestamp": timestamp,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "not handled" in data["message"]
