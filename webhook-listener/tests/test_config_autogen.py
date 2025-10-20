"""Test auto-generation of webhook secret."""

import pytest


def test_webhook_secret_uses_provided_value(monkeypatch):
    """Test that explicitly provided webhook secret is used."""
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_TRACKING_URI", "http://mlflow:5000")
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_WEBHOOK_URL", "http://test:8000/webhook")
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_WEBHOOK_SECRET", "my-custom-secret")
    
    from src.config import Settings
    
    settings = Settings(_env_file=None)
    assert settings.mlflow_webhook_secret == "my-custom-secret"


def test_webhook_secret_generates_different_values(monkeypatch):
    """Test that auto-generated secrets are unique."""
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_TRACKING_URI", "http://mlflow:5000")
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_WEBHOOK_URL", "http://test:8000/webhook")
    monkeypatch.delenv("MLFLOW_KSERVE_MLFLOW_WEBHOOK_SECRET", raising=False)
    
    from src.config import Settings
    
    settings1 = Settings(_env_file=None)
    settings2 = Settings(_env_file=None)
    
    # Both should have secrets
    assert settings1.mlflow_webhook_secret is not None
    assert settings2.mlflow_webhook_secret is not None
    
    # They should be different (since each instance generates a new one)
    assert settings1.mlflow_webhook_secret != settings2.mlflow_webhook_secret


def test_webhook_secret_handles_empty_string(monkeypatch):
    """Test that empty string is treated as not provided."""
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_TRACKING_URI", "http://mlflow:5000")
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_WEBHOOK_URL", "http://test:8000/webhook")
    monkeypatch.setenv("MLFLOW_KSERVE_MLFLOW_WEBHOOK_SECRET", "")
    
    from src.config import Settings
    
    settings = Settings(_env_file=None)
    
    # Should have generated a secret
    assert settings.mlflow_webhook_secret is not None
    assert len(settings.mlflow_webhook_secret) > 0
    assert settings.mlflow_webhook_secret != ""