"""Tests for Kubernetes client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from kubernetes.client.rest import ApiException

from src.kubernetes_client import (
    KubernetesClient,
    KubernetesClientError,
    InferenceServiceNotFoundError,
    InferenceServiceAlreadyExistsError,
)


@pytest.fixture
def mock_k8s_config():
    """Mock Kubernetes configuration loading."""
    with patch("src.kubernetes_client.config") as mock_config:
        yield mock_config


@pytest.fixture
def mock_custom_api():
    """Mock Kubernetes CustomObjectsApi."""
    with patch("src.kubernetes_client.client.CustomObjectsApi") as mock_api:
        yield mock_api.return_value


@pytest.fixture
def k8s_client(mock_k8s_config, mock_custom_api):
    """Create a KubernetesClient instance with mocked dependencies."""
    return KubernetesClient(namespace="test-namespace", in_cluster=False)


@pytest.fixture
def sample_manifest():
    """Sample InferenceService manifest."""
    return """
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: test-service
  namespace: test-namespace
  labels:
    mlflow.model: iris-classifier
    mlflow.version: "3"
spec:
  predictor:
    model:
      modelFormat:
        name: mlflow
      protocolVersion: v2
      storageUri: gs://bucket/models/iris-classifier/v3
"""


@pytest.fixture
def sample_k8s_response():
    """Sample Kubernetes API response."""
    return {
        "apiVersion": "serving.kserve.io/v1beta1",
        "kind": "InferenceService",
        "metadata": {
            "name": "test-service",
            "namespace": "test-namespace",
            "uid": "test-uid-123",
            "creationTimestamp": "2025-10-14T10:00:00Z",
            "labels": {
                "mlflow.model": "iris-classifier",
                "mlflow.version": "3",
            },
        },
        "status": {
            "conditions": [
                {
                    "type": "Ready",
                    "status": "True",
                }
            ]
        },
    }


class TestKubernetesClientInit:
    """Tests for KubernetesClient initialization."""

    def test_init_in_cluster(self, mock_k8s_config):
        """Test initialization with in-cluster configuration."""
        client = KubernetesClient(namespace="test-ns", in_cluster=True)

        mock_k8s_config.load_incluster_config.assert_called_once()
        assert client.namespace == "test-ns"
        assert client.in_cluster is True
        assert client.group == "serving.kserve.io"
        assert client.version == "v1beta1"
        assert client.plural == "inferenceservices"

    def test_init_local_config(self, mock_k8s_config):
        """Test initialization with local kubeconfig."""
        client = KubernetesClient(namespace="test-ns", in_cluster=False)

        mock_k8s_config.load_kube_config.assert_called_once()
        assert client.namespace == "test-ns"
        assert client.in_cluster is False

    def test_init_config_error(self, mock_k8s_config):
        """Test initialization failure when config cannot be loaded."""
        mock_k8s_config.load_kube_config.side_effect = Exception("Config not found")

        with pytest.raises(KubernetesClientError, match="Failed to initialize"):
            KubernetesClient(namespace="test-ns", in_cluster=False)


class TestCreateInferenceService:
    """Tests for create_inference_service method."""

    @pytest.mark.asyncio
    async def test_create_success(self, k8s_client, mock_custom_api, sample_manifest, sample_k8s_response):
        """Test successful creation of InferenceService."""
        mock_custom_api.create_namespaced_custom_object.return_value = sample_k8s_response

        result = await k8s_client.create_inference_service("test-service", sample_manifest)

        assert result["status"] == "created"
        assert result["name"] == "test-service"
        assert result["namespace"] == "test-namespace"
        assert result["uid"] == "test-uid-123"

        mock_custom_api.create_namespaced_custom_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_already_exists(self, k8s_client, mock_custom_api, sample_manifest):
        """Test creation when InferenceService already exists."""
        api_exception = ApiException(status=409, reason="Conflict")
        mock_custom_api.create_namespaced_custom_object.side_effect = api_exception

        with pytest.raises(InferenceServiceAlreadyExistsError, match="already exists"):
            await k8s_client.create_inference_service("test-service", sample_manifest)

    @pytest.mark.asyncio
    async def test_create_invalid_manifest(self, k8s_client):
        """Test creation with invalid YAML manifest."""
        invalid_manifest = "invalid: yaml: [unclosed"

        with pytest.raises(KubernetesClientError, match="Failed to parse YAML"):
            await k8s_client.create_inference_service("test-service", invalid_manifest)

    @pytest.mark.asyncio
    async def test_create_wrong_kind(self, k8s_client):
        """Test creation with wrong resource kind."""
        wrong_manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: test
"""

        with pytest.raises(KubernetesClientError, match="expected kind 'InferenceService'"):
            await k8s_client.create_inference_service("test-service", wrong_manifest)

    @pytest.mark.asyncio
    async def test_create_api_error(self, k8s_client, mock_custom_api, sample_manifest):
        """Test creation with Kubernetes API error."""
        api_exception = ApiException(status=500, reason="Internal Server Error")
        mock_custom_api.create_namespaced_custom_object.side_effect = api_exception

        with pytest.raises(KubernetesClientError, match="Kubernetes API error"):
            await k8s_client.create_inference_service("test-service", sample_manifest)


class TestDeleteInferenceService:
    """Tests for delete_inference_service method."""

    @pytest.mark.asyncio
    async def test_delete_success(self, k8s_client, mock_custom_api):
        """Test successful deletion of InferenceService."""
        result = await k8s_client.delete_inference_service("test-service")

        assert result["status"] == "deleted"
        assert result["name"] == "test-service"
        assert result["namespace"] == "test-namespace"

        mock_custom_api.delete_namespaced_custom_object.assert_called_once_with(
            group="serving.kserve.io",
            version="v1beta1",
            namespace="test-namespace",
            plural="inferenceservices",
            name="test-service",
        )

    @pytest.mark.asyncio
    async def test_delete_not_found_idempotent(self, k8s_client, mock_custom_api):
        """Test deletion of non-existent InferenceService (idempotent)."""
        api_exception = ApiException(status=404, reason="Not Found")
        mock_custom_api.delete_namespaced_custom_object.side_effect = api_exception

        result = await k8s_client.delete_inference_service("test-service")

        assert result["status"] == "deleted"
        assert result["note"] == "already_deleted"

    @pytest.mark.asyncio
    async def test_delete_api_error(self, k8s_client, mock_custom_api):
        """Test deletion with Kubernetes API error."""
        api_exception = ApiException(status=500, reason="Internal Server Error")
        mock_custom_api.delete_namespaced_custom_object.side_effect = api_exception

        with pytest.raises(KubernetesClientError, match="Kubernetes API error"):
            await k8s_client.delete_inference_service("test-service")


class TestGetInferenceService:
    """Tests for get_inference_service method."""

    @pytest.mark.asyncio
    async def test_get_success(self, k8s_client, mock_custom_api, sample_k8s_response):
        """Test successful retrieval of InferenceService."""
        mock_custom_api.get_namespaced_custom_object.return_value = sample_k8s_response

        result = await k8s_client.get_inference_service("test-service")

        assert result is not None
        assert result["name"] == "test-service"
        assert result["namespace"] == "test-namespace"
        assert result["uid"] == "test-uid-123"
        assert result["labels"]["mlflow.model"] == "iris-classifier"
        assert result["creation_timestamp"] == "2025-10-14T10:00:00Z"

    @pytest.mark.asyncio
    async def test_get_not_found(self, k8s_client, mock_custom_api):
        """Test retrieval of non-existent InferenceService."""
        api_exception = ApiException(status=404, reason="Not Found")
        mock_custom_api.get_namespaced_custom_object.side_effect = api_exception

        result = await k8s_client.get_inference_service("test-service")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_api_error(self, k8s_client, mock_custom_api):
        """Test retrieval with Kubernetes API error."""
        api_exception = ApiException(status=500, reason="Internal Server Error")
        mock_custom_api.get_namespaced_custom_object.side_effect = api_exception

        with pytest.raises(KubernetesClientError, match="Kubernetes API error"):
            await k8s_client.get_inference_service("test-service")


class TestListInferenceServices:
    """Tests for list_inference_services method."""

    @pytest.mark.asyncio
    async def test_list_success(self, k8s_client, mock_custom_api, sample_k8s_response):
        """Test successful listing of InferenceServices."""
        mock_custom_api.list_namespaced_custom_object.return_value = {
            "items": [sample_k8s_response, sample_k8s_response]
        }

        result = await k8s_client.list_inference_services()

        assert len(result) == 2
        assert result[0]["name"] == "test-service"
        assert result[1]["name"] == "test-service"

    @pytest.mark.asyncio
    async def test_list_with_label_selector(self, k8s_client, mock_custom_api):
        """Test listing with label selector."""
        mock_custom_api.list_namespaced_custom_object.return_value = {"items": []}

        await k8s_client.list_inference_services(label_selector="managed-by=mlflow")

        mock_custom_api.list_namespaced_custom_object.assert_called_once()
        call_args = mock_custom_api.list_namespaced_custom_object.call_args
        assert call_args.kwargs["label_selector"] == "managed-by=mlflow"

    @pytest.mark.asyncio
    async def test_list_empty(self, k8s_client, mock_custom_api):
        """Test listing when no InferenceServices exist."""
        mock_custom_api.list_namespaced_custom_object.return_value = {"items": []}

        result = await k8s_client.list_inference_services()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_api_error(self, k8s_client, mock_custom_api):
        """Test listing with Kubernetes API error."""
        api_exception = ApiException(status=500, reason="Internal Server Error")
        mock_custom_api.list_namespaced_custom_object.side_effect = api_exception

        with pytest.raises(KubernetesClientError, match="Kubernetes API error"):
            await k8s_client.list_inference_services()


class TestUpdateInferenceService:
    """Tests for update_inference_service method."""

    @pytest.mark.asyncio
    async def test_update_existing_service(self, k8s_client, mock_custom_api, sample_manifest, sample_k8s_response):
        """Test updating an existing InferenceService."""
        # Mock get_inference_service to return existing service
        mock_custom_api.get_namespaced_custom_object.return_value = sample_k8s_response
        mock_custom_api.patch_namespaced_custom_object.return_value = sample_k8s_response

        result = await k8s_client.update_inference_service("test-service", sample_manifest)

        assert result["status"] == "updated"
        assert result["name"] == "test-service"
        mock_custom_api.patch_namespaced_custom_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_creates_if_not_exists(self, k8s_client, mock_custom_api, sample_manifest, sample_k8s_response):
        """Test update creates InferenceService if it doesn't exist."""
        # Mock get_inference_service to return None (not found)
        api_exception = ApiException(status=404, reason="Not Found")
        mock_custom_api.get_namespaced_custom_object.side_effect = api_exception
        mock_custom_api.create_namespaced_custom_object.return_value = sample_k8s_response

        result = await k8s_client.update_inference_service("test-service", sample_manifest)

        assert result["status"] == "created"
        mock_custom_api.create_namespaced_custom_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_invalid_manifest(self, k8s_client):
        """Test update with invalid YAML manifest."""
        invalid_manifest = "invalid: yaml: [unclosed"

        with pytest.raises(KubernetesClientError, match="Failed to parse YAML"):
            await k8s_client.update_inference_service("test-service", invalid_manifest)

    @pytest.mark.asyncio
    async def test_update_wrong_kind(self, k8s_client):
        """Test update with wrong resource kind."""
        wrong_manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: test
"""

        with pytest.raises(KubernetesClientError, match="expected kind 'InferenceService'"):
            await k8s_client.update_inference_service("test-service", wrong_manifest)

    @pytest.mark.asyncio
    async def test_update_api_error(self, k8s_client, mock_custom_api, sample_manifest, sample_k8s_response):
        """Test update with Kubernetes API error."""
        mock_custom_api.get_namespaced_custom_object.return_value = sample_k8s_response
        api_exception = ApiException(status=500, reason="Internal Server Error")
        mock_custom_api.patch_namespaced_custom_object.side_effect = api_exception

        with pytest.raises(KubernetesClientError, match="Kubernetes API error"):
            await k8s_client.update_inference_service("test-service", sample_manifest)
