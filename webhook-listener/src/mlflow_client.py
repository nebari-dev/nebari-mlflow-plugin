"""MLflow API client for fetching model details."""

import logging
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

    async def get_run(self, run_id: str) -> dict[str, Any]:
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
