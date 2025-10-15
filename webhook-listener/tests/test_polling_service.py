"""Tests for the polling service."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.kubernetes_client import KubernetesClient
from src.mlflow_client import MLflowClient
from src.polling_service import PollingService


@pytest.fixture
def mock_mlflow_client():
    """Create a mock MLflow client."""
    client = MagicMock(spec=MLflowClient)
    client.get_models_with_deploy_tag = AsyncMock(return_value=[])
    client.get_run = AsyncMock(return_value={"experiment_id": "exp-123"})
    return client


@pytest.fixture
def mock_k8s_client():
    """Create a mock Kubernetes client."""
    client = MagicMock(spec=KubernetesClient)
    client.list_inference_services = AsyncMock(return_value=[])
    client.update_inference_service = AsyncMock(return_value={"status": "created", "uid": "uid-123"})
    client.delete_inference_service = AsyncMock(return_value={"status": "deleted"})
    return client


@pytest.fixture
def polling_service(mock_mlflow_client, mock_k8s_client):
    """Create a polling service instance."""
    return PollingService(
        mlflow_client=mock_mlflow_client,
        k8s_client=mock_k8s_client,
        interval=1  # Short interval for testing
    )


@pytest.mark.asyncio
async def test_polling_service_start_stop(polling_service):
    """Test starting and stopping the polling service."""
    assert not polling_service._running

    await polling_service.start()
    assert polling_service._running
    assert polling_service._task is not None

    # Allow one poll cycle
    await asyncio.sleep(0.1)

    await polling_service.stop()
    assert not polling_service._running


@pytest.mark.asyncio
async def test_polling_service_cannot_start_twice(polling_service):
    """Test that starting an already running service is a no-op."""
    await polling_service.start()
    assert polling_service._running

    # Try to start again
    await polling_service.start()
    assert polling_service._running

    await polling_service.stop()


@pytest.mark.asyncio
async def test_poll_and_reconcile_no_changes(polling_service, mock_mlflow_client, mock_k8s_client):
    """Test polling when there are no models to deploy or undeploy."""
    # No models in MLflow with deploy=true
    mock_mlflow_client.get_models_with_deploy_tag.return_value = []

    # No deployed services in Kubernetes
    mock_k8s_client.list_inference_services.return_value = []

    await polling_service._poll_and_reconcile()

    # Should have queried both systems
    mock_mlflow_client.get_models_with_deploy_tag.assert_called_once()
    mock_k8s_client.list_inference_services.assert_called_once()

    # Should not have deployed or undeployed anything
    mock_k8s_client.update_inference_service.assert_not_called()
    mock_k8s_client.delete_inference_service.assert_not_called()


@pytest.mark.asyncio
async def test_poll_and_reconcile_deploy_new_model(polling_service, mock_mlflow_client, mock_k8s_client):
    """Test deploying a new model found in MLflow."""
    # One model in MLflow with deploy=true
    mock_mlflow_client.get_models_with_deploy_tag.return_value = [
        {
            "name": "test-model",
            "version": "1",
            "run_id": "run-123",
            "source": "s3://bucket/path",
            "tags": {"deploy": "true"}
        }
    ]

    # No deployed services in Kubernetes
    mock_k8s_client.list_inference_services.return_value = []

    with patch("src.polling_service.render_inference_service") as mock_render:
        mock_render.return_value = "apiVersion: serving.kserve.io/v1beta1..."

        await polling_service._poll_and_reconcile()

    # Should have deployed the model
    mock_k8s_client.update_inference_service.assert_called_once()
    call_args = mock_k8s_client.update_inference_service.call_args
    assert "test-model" in call_args[0][0]  # Service name contains model name


@pytest.mark.asyncio
async def test_poll_and_reconcile_undeploy_removed_model(polling_service, mock_mlflow_client, mock_k8s_client):
    """Test undeploying a model that no longer has deploy=true."""
    # No models in MLflow with deploy=true
    mock_mlflow_client.get_models_with_deploy_tag.return_value = []

    # One deployed service in Kubernetes
    mock_k8s_client.list_inference_services.return_value = [
        {
            "name": "test-model-v1",
            "namespace": "default",
            "labels": {
                "mlflow.model": "test-model",
                "mlflow.version": "1",
                "managed-by": "mlflow-kserve-webhook-listener"
            }
        }
    ]

    await polling_service._poll_and_reconcile()

    # Should have undeployed the model
    mock_k8s_client.delete_inference_service.assert_called_once_with("test-model-v1")


@pytest.mark.asyncio
async def test_poll_and_reconcile_mixed_operations(polling_service, mock_mlflow_client, mock_k8s_client):
    """Test deploying new models while keeping existing ones."""
    # Two models in MLflow with deploy=true
    mock_mlflow_client.get_models_with_deploy_tag.return_value = [
        {
            "name": "model-a",
            "version": "1",
            "run_id": "run-a1",
            "source": "s3://bucket/model-a",
            "tags": {"deploy": "true"}
        },
        {
            "name": "model-b",
            "version": "2",
            "run_id": "run-b2",
            "source": "s3://bucket/model-b",
            "tags": {"deploy": "true"}
        }
    ]

    # One deployed service in Kubernetes (model-a is already deployed)
    mock_k8s_client.list_inference_services.return_value = [
        {
            "name": "model-a-v1",
            "namespace": "default",
            "labels": {
                "mlflow.model": "model-a",
                "mlflow.version": "1",
                "managed-by": "mlflow-kserve-webhook-listener"
            }
        }
    ]

    with patch("src.polling_service.render_inference_service") as mock_render:
        mock_render.return_value = "apiVersion: serving.kserve.io/v1beta1..."

        await polling_service._poll_and_reconcile()

    # Should have deployed only model-b (model-a already exists)
    mock_k8s_client.update_inference_service.assert_called_once()
    call_args = mock_k8s_client.update_inference_service.call_args
    assert "model-b" in call_args[0][0]  # Service name contains model-b

    # Should not have undeployed anything
    mock_k8s_client.delete_inference_service.assert_not_called()


@pytest.mark.asyncio
async def test_poll_and_reconcile_handles_errors(polling_service, mock_mlflow_client, mock_k8s_client):
    """Test that reconciliation continues even if individual operations fail."""
    # MLflow returns one model
    mock_mlflow_client.get_models_with_deploy_tag.return_value = [
        {
            "name": "test-model",
            "version": "1",
            "run_id": "run-123",
            "source": "s3://bucket/path",
            "tags": {"deploy": "true"}
        }
    ]

    # Kubernetes list succeeds but deploy fails
    mock_k8s_client.list_inference_services.return_value = []
    mock_k8s_client.update_inference_service.side_effect = Exception("Deploy failed")

    with patch("src.polling_service.render_inference_service") as mock_render:
        mock_render.return_value = "apiVersion: serving.kserve.io/v1beta1..."

        # Should not raise exception
        await polling_service._poll_and_reconcile()

    # Should have attempted to deploy
    mock_k8s_client.update_inference_service.assert_called_once()


@pytest.mark.asyncio
async def test_deploy_model_success(polling_service, mock_mlflow_client, mock_k8s_client):
    """Test successful model deployment."""
    models_data = [
        {
            "name": "test-model",
            "version": "1",
            "run_id": "run-123",
            "source": "s3://bucket/path",
            "tags": {"deploy": "true"}
        }
    ]

    with patch("src.polling_service.render_inference_service") as mock_render, \
         patch("src.polling_service.generate_inference_service_name") as mock_gen_name:

        mock_render.return_value = "apiVersion: serving.kserve.io/v1beta1..."
        mock_gen_name.return_value = "test-model-v1"

        await polling_service._deploy_model("test-model", "1", models_data)

    # Should have fetched run details
    mock_mlflow_client.get_run.assert_called_once_with("run-123")

    # Should have deployed
    mock_k8s_client.update_inference_service.assert_called_once_with(
        "test-model-v1",
        "apiVersion: serving.kserve.io/v1beta1..."
    )


@pytest.mark.asyncio
async def test_deploy_model_not_found(polling_service, mock_k8s_client):
    """Test deploying a model that's not in the models data."""
    models_data = []  # Empty list

    await polling_service._deploy_model("missing-model", "1", models_data)

    # Should not have attempted to deploy
    mock_k8s_client.update_inference_service.assert_not_called()


@pytest.mark.asyncio
async def test_deploy_model_handles_errors(polling_service, mock_mlflow_client, mock_k8s_client):
    """Test that deployment errors are handled gracefully."""
    models_data = [
        {
            "name": "test-model",
            "version": "1",
            "run_id": "run-123",
            "source": "s3://bucket/path",
            "tags": {"deploy": "true"}
        }
    ]

    # Make get_run fail
    mock_mlflow_client.get_run.side_effect = Exception("MLflow error")

    # Should not raise exception
    await polling_service._deploy_model("test-model", "1", models_data)

    # Should not have attempted to deploy
    mock_k8s_client.update_inference_service.assert_not_called()


@pytest.mark.asyncio
async def test_undeploy_model_success(polling_service, mock_k8s_client):
    """Test successful model undeployment."""
    await polling_service._undeploy_model("test-model", "1", "test-model-v1")

    # Should have deleted the service
    mock_k8s_client.delete_inference_service.assert_called_once_with("test-model-v1")


@pytest.mark.asyncio
async def test_undeploy_model_handles_errors(polling_service, mock_k8s_client):
    """Test that undeployment errors are handled gracefully."""
    mock_k8s_client.delete_inference_service.side_effect = Exception("Delete failed")

    # Should not raise exception
    await polling_service._undeploy_model("test-model", "1", "test-model-v1")

    # Should have attempted to delete
    mock_k8s_client.delete_inference_service.assert_called_once()


@pytest.mark.asyncio
async def test_polling_loop_continues_on_error(polling_service, mock_mlflow_client):
    """Test that the polling loop continues even if reconciliation fails."""
    # Make reconciliation fail
    mock_mlflow_client.get_models_with_deploy_tag.side_effect = Exception("MLflow down")

    await polling_service.start()

    # Let it run for a bit
    await asyncio.sleep(0.5)

    # Should still be running despite errors
    assert polling_service._running

    await polling_service.stop()


@pytest.mark.asyncio
async def test_deployed_models_tracking(polling_service, mock_mlflow_client, mock_k8s_client):
    """Test that the service tracks deployed models."""
    # First reconciliation: deploy a model
    mock_mlflow_client.get_models_with_deploy_tag.return_value = [
        {
            "name": "test-model",
            "version": "1",
            "run_id": "run-123",
            "source": "s3://bucket/path",
            "tags": {"deploy": "true"}
        }
    ]
    mock_k8s_client.list_inference_services.return_value = []

    with patch("src.polling_service.render_inference_service") as mock_render:
        mock_render.return_value = "apiVersion: serving.kserve.io/v1beta1..."
        await polling_service._poll_and_reconcile()

    # Should track the deployed model
    assert ("test-model", "1") in polling_service._deployed_models

    # Second reconciliation: model removed from MLflow
    mock_mlflow_client.get_models_with_deploy_tag.return_value = []
    mock_k8s_client.list_inference_services.return_value = [
        {
            "name": "test-model-v1",
            "namespace": "default",
            "labels": {
                "mlflow.model": "test-model",
                "mlflow.version": "1",
                "managed-by": "mlflow-kserve-webhook-listener"
            }
        }
    ]

    await polling_service._poll_and_reconcile()

    # Should no longer track the model
    assert ("test-model", "1") not in polling_service._deployed_models
