"""Tests for template rendering utilities."""

import pytest
import yaml
from jinja2 import TemplateError
from src.templates import (
    generate_inference_service_name,
    render_inference_service,
    sanitize_k8s_name,
)


class TestSanitizeK8sName:
    """Tests for sanitize_k8s_name function."""

    def test_lowercase_conversion(self):
        """Test that names are converted to lowercase."""
        assert sanitize_k8s_name("MyModel") == "mymodel"
        assert sanitize_k8s_name("UPPERCASE") == "uppercase"

    def test_invalid_char_replacement(self):
        """Test that invalid characters are replaced with hyphens."""
        assert sanitize_k8s_name("my_model") == "my-model"
        assert sanitize_k8s_name("model@v1") == "model-v1"
        assert sanitize_k8s_name("model.name") == "model-name"
        assert sanitize_k8s_name("my model") == "my-model"

    def test_leading_trailing_hyphens_removed(self):
        """Test that leading and trailing hyphens are removed."""
        assert sanitize_k8s_name("-mymodel-") == "mymodel"
        assert sanitize_k8s_name("--model--") == "model"

    def test_consecutive_hyphens_collapsed(self):
        """Test that multiple consecutive hyphens are collapsed to one."""
        assert sanitize_k8s_name("my--model") == "my-model"
        assert sanitize_k8s_name("model___name") == "model-name"

    def test_max_length_truncation(self):
        """Test that names longer than 253 characters are truncated."""
        long_name = "a" * 300
        result = sanitize_k8s_name(long_name)
        assert len(result) == 253

        # Test truncation with trailing hyphen
        long_name_with_hyphen = "a" * 252 + "-b"
        result = sanitize_k8s_name(long_name_with_hyphen)
        assert len(result) <= 253
        assert not result.endswith("-")

    def test_empty_name_raises_error(self):
        """Test that empty or invalid-only names raise ValueError."""
        with pytest.raises(ValueError, match="Sanitized name cannot be empty"):
            sanitize_k8s_name("")

        with pytest.raises(ValueError, match="Sanitized name cannot be empty"):
            sanitize_k8s_name("---")

        with pytest.raises(ValueError, match="Sanitized name cannot be empty"):
            sanitize_k8s_name("___")

    def test_valid_name_unchanged(self):
        """Test that already valid names are preserved."""
        assert sanitize_k8s_name("valid-name") == "valid-name"
        assert sanitize_k8s_name("model-v1") == "model-v1"


class TestGenerateInferenceServiceName:
    """Tests for generate_inference_service_name function."""

    def test_basic_name_generation(self):
        """Test basic name generation from model and version."""
        result = generate_inference_service_name("mymodel", "1")
        assert result == "mymodel-v1"

    def test_sanitization_applied(self):
        """Test that sanitization is applied to generated names."""
        result = generate_inference_service_name("My_Model", "1.0")
        assert result == "my-model-v1-0"

    def test_complex_model_names(self):
        """Test name generation with complex model names."""
        result = generate_inference_service_name("ML Model v2.0", "3")
        assert result == "ml-model-v2-0-v3"

        result = generate_inference_service_name("my-model", "latest")
        assert result == "my-model-vlatest"


class TestRenderInferenceService:
    """Tests for render_inference_service function."""

    def test_basic_rendering(self):
        """Test basic template rendering with all required fields."""
        result = render_inference_service(
            model_name="test-model",
            model_version="1",
            storage_uri="s3://bucket/path",
            run_id="run123",
            experiment_id="exp456",
            namespace="default",
        )

        # Check that key fields are present in rendered YAML
        assert "apiVersion: serving.kserve.io/v1beta1" in result
        assert "kind: InferenceService" in result
        assert "name: test-model-v1" in result
        assert "namespace: default" in result
        assert "mlflow.org/model-name: test-model" in result
        assert 'mlflow.org/model-version: "1"' in result
        assert "mlflow.org/run-id: run123" in result
        assert "mlflow.org/experiment-id: exp456" in result
        assert "storageUri: s3://bucket/path" in result
        assert "managed-by: nebari-mlflow-webhook-listener" in result

    def test_custom_name(self):
        """Test rendering with custom InferenceService name."""
        result = render_inference_service(
            model_name="test-model",
            model_version="1",
            storage_uri="s3://bucket/path",
            run_id="run123",
            experiment_id="exp456",
            namespace="default",
            name="custom-service-name",
        )

        assert "name: custom-service-name" in result

    def test_custom_name_sanitization(self):
        """Test that custom names are sanitized."""
        result = render_inference_service(
            model_name="test-model",
            model_version="1",
            storage_uri="s3://bucket/path",
            run_id="run123",
            experiment_id="exp456",
            namespace="default",
            name="Custom_Name",
        )

        assert "name: custom-name" in result

    def test_special_characters_in_metadata(self):
        """Test rendering with special characters in metadata."""
        result = render_inference_service(
            model_name="my_model",
            model_version="2.0",
            storage_uri="s3://my-bucket/models/path",
            run_id="abc-123-def",
            experiment_id="exp-789",
            namespace="ml-namespace",
        )

        # Name should be sanitized
        assert "name: my-model-v2-0" in result
        # But labels should preserve original values
        assert "mlflow.org/model-name: my_model" in result
        assert 'mlflow.org/model-version: "2.0"' in result

    def test_template_not_found_error(self, tmp_path, monkeypatch):
        """Test error handling when template file is not found."""
        # Point to a non-existent directory
        monkeypatch.setattr("src.templates.TEMPLATES_DIR", tmp_path / "nonexistent")

        with pytest.raises(TemplateError):
            render_inference_service(
                model_name="test",
                model_version="1",
                storage_uri="s3://bucket",
                run_id="run123",
                experiment_id="exp456",
                namespace="default",
            )


class TestYAMLValidation:
    """Tests to verify that generated YAML is valid and well-formed."""

    def test_rendered_yaml_is_valid(self):
        """Test that rendered YAML can be parsed successfully."""
        result = render_inference_service(
            model_name="test-model",
            model_version="1",
            storage_uri="s3://bucket/path",
            run_id="run123",
            experiment_id="exp456",
            namespace="default",
        )

        # Should parse without errors
        parsed = yaml.safe_load(result)
        assert parsed is not None
        assert isinstance(parsed, dict)

    def test_yaml_structure_is_correct(self):
        """Test that parsed YAML has correct structure for InferenceService."""
        result = render_inference_service(
            model_name="iris-classifier",
            model_version="2",
            storage_uri="s3://mlflow-bucket/artifacts",
            run_id="abc123def456",
            experiment_id="exp789",
            namespace="ml-models",
        )

        parsed = yaml.safe_load(result)

        # Verify top-level structure
        assert parsed["apiVersion"] == "serving.kserve.io/v1beta1"
        assert parsed["kind"] == "InferenceService"

        # Verify metadata
        assert "metadata" in parsed
        assert parsed["metadata"]["name"] == "iris-classifier-v2"
        assert parsed["metadata"]["namespace"] == "ml-models"

        # Verify labels
        assert "labels" in parsed["metadata"]
        labels = parsed["metadata"]["labels"]
        assert labels["managed-by"] == "nebari-mlflow-webhook-listener"
        assert labels["mlflow.org/model-name"] == "iris-classifier"
        assert labels["mlflow.org/model-version"] == "2"
        assert labels["mlflow.org/run-id"] == "abc123def456"
        assert labels["mlflow.org/experiment-id"] == "exp789"

        # Verify spec
        assert "spec" in parsed
        assert "predictor" in parsed["spec"]
        assert "model" in parsed["spec"]["predictor"]
        model = parsed["spec"]["predictor"]["model"]
        assert model["modelFormat"]["name"] == "mlflow"
        assert model["storageUri"] == "s3://mlflow-bucket/artifacts"

    def test_yaml_with_special_characters_is_valid(self):
        """Test that YAML with special characters in values is still valid."""
        result = render_inference_service(
            model_name="my_complex-model.v2",
            model_version="1.0.3-alpha",
            storage_uri="s3://bucket/path/with-special_chars.model",
            run_id="run-123_abc",
            experiment_id="exp-456",
            namespace="kserve-test",
        )

        # Should parse without errors
        parsed = yaml.safe_load(result)
        assert parsed is not None

        # Verify special characters are preserved in labels
        labels = parsed["metadata"]["labels"]
        assert labels["mlflow.org/model-name"] == "my_complex-model.v2"
        assert labels["mlflow.org/model-version"] == "1.0.3-alpha"

    def test_multiple_renders_produce_valid_yaml(self):
        """Test that multiple different renders all produce valid YAML."""
        test_cases = [
            {
                "model_name": "model-a",
                "model_version": "1",
                "storage_uri": "s3://bucket/a",
                "run_id": "run1",
                "experiment_id": "exp1",
                "namespace": "ns1",
            },
            {
                "model_name": "MODEL_B",
                "model_version": "v2.0",
                "storage_uri": "gs://bucket/b/path",
                "run_id": "run-2-abc",
                "experiment_id": "exp_2",
                "namespace": "namespace-two",
            },
            {
                "model_name": "complex.model_name",
                "model_version": "latest",
                "storage_uri": "file:///path/to/model",
                "run_id": "abc123",
                "experiment_id": "999",
                "namespace": "default",
            },
        ]

        for test_case in test_cases:
            result = render_inference_service(**test_case)

            # Each should produce valid YAML
            parsed = yaml.safe_load(result)
            assert parsed is not None
            assert parsed["kind"] == "InferenceService"
            assert "metadata" in parsed
            assert "spec" in parsed
