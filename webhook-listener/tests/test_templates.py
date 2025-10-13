"""Tests for template rendering functions."""

import pytest


def test_sanitize_k8s_name_lowercases():
    """Test that sanitize_k8s_name converts to lowercase (stub)."""
    from src.templates import sanitize_k8s_name

    result = sanitize_k8s_name("MyModel-V1")
    assert result == "mymodel-v1"


def test_sanitize_k8s_name_handles_lowercase():
    """Test that sanitize_k8s_name handles already lowercase names."""
    from src.templates import sanitize_k8s_name

    result = sanitize_k8s_name("my-model")
    assert result == "my-model"


def test_generate_inference_service_name():
    """Test generation of InferenceService names."""
    from src.templates import generate_inference_service_name

    name = generate_inference_service_name("iris-classifier", "3")
    assert name == "mlflow-iris-classifier-v3"


def test_generate_inference_service_name_with_mixed_case():
    """Test InferenceService name generation with mixed case input."""
    from src.templates import generate_inference_service_name

    name = generate_inference_service_name("MyModel", "1")
    assert name == "mlflow-mymodel-v1"


def test_render_inference_service_stub():
    """Test that render_inference_service returns YAML (stub)."""
    import asyncio
    from src.templates import render_inference_service

    yaml = asyncio.run(render_inference_service(
        template_path="dummy.yaml.j2",
        name="mlflow-test-v1",
        namespace="kserve-models",
        model_name="test-model",
        model_version="1",
        storage_uri="gs://bucket/path/to/model",
        run_id="abc123",
        experiment_id="1"
    ))

    # Verify it returns a string with YAML content (stub)
    assert isinstance(yaml, str)
    assert "apiVersion" in yaml
    assert "kind: \"InferenceService\"" in yaml
    assert "mlflow-test-v1" in yaml
    assert "kserve-models" in yaml
    assert "gs://bucket/path/to/model" in yaml
