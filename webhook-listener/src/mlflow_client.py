"""MLflow API client for fetching model details."""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class MLflowClient:
    """Client for interacting with MLflow API."""

    def __init__(self, tracking_uri: str):
        """
        Initialize MLflow client.

        STUB: Currently just stores config.
        Real implementation will be added in Phase 4.
        """
        self.tracking_uri = tracking_uri
        logger.info(f"Initialized MLflow client (stub) - tracking_uri: {tracking_uri}")

    async def get_model_version(
        self, model_name: str, version: str
    ) -> Dict[str, Any]:
        """
        Fetch model version details from MLflow.

        STUB: Currently returns dummy data.
        Real implementation will be added in Phase 4.
        """
        logger.info(f"Fetching model version: {model_name} v{version} (stub)")

        # STUB: Return dummy model version data
        return {
            "name": model_name,
            "version": version,
            "run_id": "dummy-run-id-12345",
            "status": "READY",
            "source": f"gs://dummy-bucket/1/{model_name}/artifacts",
        }

    async def get_run(self, run_id: str) -> Dict[str, Any]:
        """
        Fetch run details from MLflow.

        STUB: Currently returns dummy data.
        Real implementation will be added in Phase 4.
        """
        logger.info(f"Fetching run: {run_id} (stub)")

        # STUB: Return dummy run data
        return {
            "run_id": run_id,
            "experiment_id": "1",
            "artifact_uri": f"gs://dummy-bucket/1/{run_id}/artifacts",
            "status": "FINISHED",
        }

    async def build_storage_uri(
        self, model_name: str, version: str, storage_uri_base: str
    ) -> str:
        """
        Construct the full storage URI for model artifacts.

        STUB: Currently returns a constructed path.
        Real implementation will be added in Phase 4.
        """
        logger.info(f"Building storage URI for {model_name} v{version} (stub)")

        # STUB: Return a dummy storage URI
        storage_uri = f"{storage_uri_base}/1/dummy-run-id/artifacts/model"
        logger.debug(f"Storage URI: {storage_uri}")
        return storage_uri
