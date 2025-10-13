"""Tests for FastAPI endpoints."""

import pytest


def test_health_endpoint(client):
    """Test the /health endpoint returns expected stub response."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["mlflow_connected"] is True
    assert data["kubernetes_connected"] is True


def test_services_endpoint(client):
    """Test the /services endpoint returns empty list (stub)."""
    response = client.get("/services")

    assert response.status_code == 200
    data = response.json()
    assert "services" in data
    assert isinstance(data["services"], list)
    assert len(data["services"]) == 0


def test_webhook_endpoint_accepts_valid_payload(client, sample_webhook_payload):
    """Test the /webhook endpoint accepts a valid payload."""
    response = client.post(
        "/webhook",
        json=sample_webhook_payload,
        headers={
            "x-mlflow-signature": "v1,dummysig",
            "x-mlflow-delivery-id": "test-delivery-123",
            "x-mlflow-timestamp": "1234567890",
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["entity"] == "model_version_tag"
    assert data["action"] == "set"
    assert data["delivery_id"] == "test-delivery-123"


def test_webhook_endpoint_parses_entity_and_action(client):
    """Test that webhook endpoint correctly parses entity and action."""
    payload = {
        "entity": "registered_model",
        "action": "created",
        "timestamp": 1234567890,
        "data": {"name": "test-model"}
    }

    response = client.post(
        "/webhook",
        json=payload,
        headers={
            "x-mlflow-signature": "v1,sig",
            "x-mlflow-delivery-id": "test-123",
            "x-mlflow-timestamp": "1234567890",
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["entity"] == "registered_model"
    assert data["action"] == "created"


def test_webhook_endpoint_handles_deploy_tag(client):
    """Test webhook endpoint with deploy tag set to true."""
    payload = {
        "entity": "model_version_tag",
        "action": "set",
        "timestamp": 1234567890,
        "data": {
            "name": "test-model",
            "version": "1",
            "key": "deploy",
            "value": "true"
        }
    }

    response = client.post(
        "/webhook",
        json=payload,
        headers={
            "x-mlflow-signature": "v1,sig",
            "x-mlflow-delivery-id": "test-456",
            "x-mlflow-timestamp": "1234567890",
        }
    )

    assert response.status_code == 200
    # Currently stub, just verify it processes
    assert response.json()["status"] == "success"
