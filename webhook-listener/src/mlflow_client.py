"""MLflow API client for fetching model details."""

import logging
import re
from typing import Any

from mlflow import MlflowClient as MLflowSDKClient

logger = logging.getLogger(__name__)


class MLflowClient:
    """Client for interacting with MLflow API."""

    def __init__(self, tracking_uri: str):
        """
        Initialize MLflow client.

        Args:
            tracking_uri: MLflow tracking server URI
        """
        self.tracking_uri = tracking_uri
        self._client = MLflowSDKClient(tracking_uri=tracking_uri)
        logger.info(f"Initialized MLflow client - tracking_uri: {tracking_uri}")

    async def get_model_version(
        self, model_name: str, version: str
    ) -> dict[str, Any]:
        """
        Fetch model version details from MLflow.

        Args:
            model_name: Name of the registered model
            version: Version number of the model

        Returns:
            Dictionary containing model version details including run_id, status, and source

        Raises:
            Exception: If the model version cannot be fetched from MLflow
        """
        try:
            logger.info(f"Fetching model version: {model_name} v{version}")

            # Fetch model version from MLflow
            model_version = self._client.get_model_version(name=model_name, version=version)

            result = {
                "name": model_version.name,
                "version": model_version.version,
                "run_id": model_version.run_id,
                "status": model_version.status,
                "source": model_version.source,
                "current_stage": model_version.current_stage,
                "creation_timestamp": model_version.creation_timestamp,
                "last_updated_timestamp": model_version.last_updated_timestamp,
            }

            logger.debug(f"Model version details: run_id={result['run_id']}, status={result['status']}")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch model version {model_name} v{version}: {e}")
            raise

    async def get_run(self, run_id: str) -> dict[str, Any]:
        """
        Fetch run details from MLflow.

        Args:
            run_id: MLflow run ID

        Returns:
            Dictionary containing run details including experiment_id, artifact_uri, and status

        Raises:
            Exception: If the run cannot be fetched from MLflow
        """
        try:
            logger.info(f"Fetching run: {run_id}")

            # Fetch run from MLflow
            run = self._client.get_run(run_id=run_id)

            result = {
                "run_id": run.info.run_id,
                "experiment_id": run.info.experiment_id,
                "artifact_uri": run.info.artifact_uri,
                "status": run.info.status,
                "start_time": run.info.start_time,
                "end_time": run.info.end_time,
                "lifecycle_stage": run.info.lifecycle_stage,
            }

            logger.debug(f"Run details: experiment_id={result['experiment_id']}, artifact_uri={result['artifact_uri']}")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch run {run_id}: {e}")
            raise

    async def build_storage_uri(
        self, model_name: str, version: str, storage_uri_base: str | None = None
    ) -> str:
        """
        Construct the full storage URI for model artifacts.

        This method fetches the model version details and run information to build
        the complete storage URI where the model artifacts are stored.

        Args:
            model_name: Name of the registered model
            version: Version number of the model
            storage_uri_base: Optional base URI to override the artifact URI from MLflow.
                            If not provided, uses the artifact URI from the run.

        Returns:
            Full storage URI path to the model artifacts

        Raises:
            Exception: If the storage URI cannot be constructed
        """
        try:
            logger.info(f"Building storage URI for {model_name} v{version}")

            # Fetch model version to get run_id and source
            model_version = await self.get_model_version(model_name, version)
            run_id = model_version["run_id"]

            # If storage_uri_base is provided, use it; otherwise fetch from run
            if storage_uri_base:
                # Use the provided base URI and append the run-specific path
                run = await self.get_run(run_id)
                artifact_uri = run["artifact_uri"]

                # Extract the path after the base URI from artifact_uri
                # artifact_uri format: <base>/<experiment_id>/<run_id>/artifacts
                # We want to construct: <storage_uri_base>/<experiment_id>/<run_id>/artifacts/model
                match = re.search(r"/(\d+/[a-f0-9]+/artifacts)", artifact_uri)
                if match:
                    relative_path = match.group(1)
                    storage_uri = f"{storage_uri_base.rstrip('/')}/{relative_path}/model"
                else:
                    # Fallback: use model source if pattern doesn't match
                    storage_uri = model_version["source"]
            else:
                # Use the source directly from model version
                storage_uri = model_version["source"]

            logger.debug(f"Storage URI: {storage_uri}")
            return storage_uri

        except Exception as e:
            logger.error(f"Failed to build storage URI for {model_name} v{version}: {e}")
            raise

    def list_webhooks(self) -> list[Any]:
        """
        List all registered webhooks.

        Returns:
            List of webhook objects
        """
        try:
            webhooks = self._client.list_webhooks()
            logger.debug(f"Found {len(webhooks)} registered webhooks")
            return webhooks
        except Exception as e:
            logger.error(f"Error listing webhooks: {e}")
            raise

    def get_webhook_by_url(self, url: str) -> Any | None:
        """
        Find a webhook by its URL.

        Args:
            url: The webhook URL to search for

        Returns:
            Webhook object if found, None otherwise
        """
        try:
            webhooks = self.list_webhooks()
            for webhook in webhooks:
                if webhook.url == url:
                    logger.info(f"Found existing webhook with ID: {webhook.webhook_id}")
                    return webhook
            return None
        except Exception as e:
            logger.error(f"Error searching for webhook: {e}")
            raise

    def create_webhook(
        self,
        name: str,
        url: str,
        events: list[str],
        secret: str,
        description: str | None = None
    ) -> Any:
        """
        Create a new webhook.

        Args:
            name: Name for the webhook
            url: URL where webhooks will be sent
            events: List of event types to subscribe to
            secret: Secret for HMAC signature verification
            description: Optional description of the webhook

        Returns:
            Created webhook object
        """
        try:
            logger.info(f"Creating webhook '{name}' to {url}")
            logger.debug(f"Events: {events}")

            webhook = self._client.create_webhook(
                name=name,
                url=url,
                events=events,
                secret=secret,
                description=description
            )

            logger.info(f"Webhook created successfully with ID: {webhook.webhook_id}")
            return webhook
        except Exception as e:
            logger.error(f"Error creating webhook: {e}")
            raise

    def test_webhook(self, webhook_id: str) -> Any:
        """
        Test a webhook connection.

        Args:
            webhook_id: ID of the webhook to test

        Returns:
            Test result object
        """
        try:
            logger.info(f"Testing webhook {webhook_id}")
            test_result = self._client.test_webhook(webhook_id)
            logger.info(
                f"Webhook test result: success={test_result.success}, "
                f"status={test_result.response_status}"
            )
            if not test_result.success:
                logger.warning(f"Webhook test failed: {test_result.error_message}")
            return test_result
        except Exception as e:
            logger.error(f"Error testing webhook: {e}")
            raise

    def ensure_webhook_registered(
        self,
        name: str,
        url: str,
        events: list[str],
        secret: str,
        description: str | None = None,
        *,
        test_on_create: bool = True
    ) -> tuple[bool, Any | None]:
        """
        Ensure a webhook is registered, creating it if it doesn't exist.

        Args:
            name: Name for the webhook
            url: URL where webhooks will be sent
            events: List of event types to subscribe to
            secret: Secret for HMAC signature verification
            description: Optional description of the webhook
            test_on_create: Whether to test the webhook after creation

        Returns:
            Tuple of (was_created, webhook_object)
        """
        try:
            # Check if webhook already exists
            existing_webhook = self.get_webhook_by_url(url)

            if existing_webhook:
                logger.info(f"Webhook already registered with ID: {existing_webhook.webhook_id}")
                return (False, existing_webhook)

            # Create new webhook
            webhook = self.create_webhook(
                name=name,
                url=url,
                events=events,
                secret=secret,
                description=description
            )

            # Optionally test the webhook
            if test_on_create:
                try:
                    test_result = self.test_webhook(webhook.webhook_id)
                    if not test_result.success:
                        logger.warning(
                            "Webhook created but test failed. "
                            "This may be expected if the service is starting up."
                        )
                except Exception as e:
                    logger.warning("Webhook test failed: %s. Continuing anyway.", e)

            return (True, webhook)

        except Exception as e:
            logger.error(f"Error ensuring webhook registration: {e}")
            raise
