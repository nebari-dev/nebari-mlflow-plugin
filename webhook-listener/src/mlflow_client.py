"""MLflow API client for fetching model details."""

import asyncio
import logging
from typing import Any

from mlflow import MlflowClient as MLflowSDKClient

from src.config import settings

logger = logging.getLogger(__name__)


def resolve_mlflow_artifacts_uri(source_uri: str) -> str:
    """
    Resolve mlflow-artifacts:// URIs to actual cloud storage URIs.

    MLflow uses mlflow-artifacts:// as a logical URI scheme. KServe needs
    actual cloud storage URIs (gs://, s3://, etc.) to access model files.

    This function converts:
        mlflow-artifacts:/1/models/m-{uuid}/artifacts
    To:
        {artifacts_uri}/1/models/m-{uuid}/artifacts

    Args:
        source_uri: The source URI from MLflow (may use mlflow-artifacts://)

    Returns:
        Resolved storage URI that KServe can access
    """
    # If it's already a cloud storage URI, return as-is
    if not source_uri.startswith("mlflow-artifacts://") and not source_uri.startswith("mlflow-artifacts:/"):
        logger.debug(f"Storage URI already resolved: {source_uri}")
        return source_uri

    # Extract the path after mlflow-artifacts://
    # Handle both mlflow-artifacts:// and mlflow-artifacts:/ (single slash)
    mlflow_path = source_uri.replace("mlflow-artifacts://", "").replace("mlflow-artifacts:/", "")

    # Construct the actual storage URI
    artifacts_base = settings.artifacts_uri.rstrip("/")
    resolved_uri = f"{artifacts_base}/{mlflow_path}"

    logger.info(f"Resolved {source_uri} to {resolved_uri}")
    return resolved_uri


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

    async def get_storage_uri(
        self, model_name: str, version: str
    ) -> str:
        """
        Get the storage URI for model artifacts from the model version.

        The storage URI is obtained from the model version's source field.
        If the source uses the mlflow-artifacts:// scheme, it's converted to the
        actual cloud storage URI by fetching the run's artifact_uri.

        Args:
            model_name: Name of the registered model
            version: Version number of the model

        Returns:
            Storage URI path to the model artifacts (e.g., 'gs://bucket/path/artifacts')

        Raises:
            Exception: If the model version cannot be fetched or has no source
        """
        try:
            logger.info(f"Getting storage URI for {model_name} v{version}")

            # Fetch model version to get source URI
            model_version = await self.get_model_version(model_name, version)
            source_uri = model_version["source"]

            if not source_uri:
                error_msg = f"Model version {model_name} v{version} has no source URI"
                raise ValueError(error_msg)

            # Convert mlflow-artifacts:// URIs to actual storage URIs
            storage_uri = await self._resolve_storage_uri(source_uri, model_version["run_id"])

            logger.debug(f"Resolved storage URI: {storage_uri}")
            return storage_uri

        except Exception as e:
            logger.error(f"Failed to get storage URI for {model_name} v{version}: {e}")
            raise

    async def _resolve_storage_uri(self, source_uri: str, run_id: str) -> str:
        """
        Resolve mlflow-artifacts:// URIs to actual cloud storage URIs.

        Args:
            source_uri: The source URI from the model version (may use mlflow-artifacts://)
            run_id: The MLflow run ID

        Returns:
            Resolved storage URI (e.g., gs://bucket/path)
        """
        # If it's already a cloud storage URI, return as-is
        if not source_uri.startswith("mlflow-artifacts://"):
            logger.debug(f"Storage URI already resolved: {source_uri}")
            return source_uri

        # Extract the path after mlflow-artifacts://
        # Format: mlflow-artifacts:/experiment_id/run_id/artifacts/model
        mlflow_path = source_uri.replace("mlflow-artifacts://", "").replace("mlflow-artifacts:/", "")

        # Get the run to find the actual artifact_uri
        run = await self.get_run(run_id)
        artifact_uri = run["artifact_uri"]

        logger.debug(f"Run artifact_uri: {artifact_uri}")

        # If artifact_uri also uses mlflow-artifacts://, we can't resolve further
        if artifact_uri.startswith("mlflow-artifacts://") or artifact_uri.startswith("mlflow-artifacts:/"):
            logger.warning(
                f"Run artifact_uri also uses mlflow-artifacts:// scheme: {artifact_uri}. "
                "Cannot resolve to actual storage URI. Using source URI as-is."
            )
            return source_uri

        # The model_version source typically points to a registered model location like:
        # mlflow-artifacts:/1/models/m-{model_uuid}/artifacts
        # While the run artifact_uri points to the run artifacts like:
        # gs://bucket/1/{run_id}/artifacts

        # Extract the model path from the source_uri
        # We need to reconstruct the path based on where the model was logged in the run
        if "/models/" in mlflow_path:
            # This is a registered model path, use it as-is for now
            # In most cases, the model artifacts are stored alongside run artifacts
            return source_uri

        # For run artifacts, combine artifact_uri with the relative path
        # Remove leading slash from mlflow_path if present
        mlflow_path = mlflow_path.lstrip("/")

        # If artifact_uri ends with /artifacts, the model is typically in a subdirectory
        resolved_uri = f"{artifact_uri.rstrip('/')}/{mlflow_path}"

        logger.debug(f"Resolved {source_uri} to {resolved_uri}")
        return resolved_uri

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

    def delete_webhook(self, webhook_id: str) -> None:
        """
        Delete a webhook.

        Args:
            webhook_id: ID of the webhook to delete
        """
        try:
            logger.info(f"Deleting webhook {webhook_id}")
            self._client.delete_webhook(webhook_id)
            logger.info(f"Webhook {webhook_id} deleted successfully")
        except Exception as e:
            logger.error(f"Error deleting webhook {webhook_id}: {e}")
            raise

    def delete_webhook_by_url(self, url: str) -> bool:
        """
        Delete a webhook by its URL.

        Args:
            url: The webhook URL to search for and delete

        Returns:
            True if a webhook was found and deleted, False otherwise
        """
        try:
            webhook = self.get_webhook_by_url(url)
            if webhook:
                self.delete_webhook(webhook.webhook_id)
                return True
            logger.info(f"No webhook found with URL: {url}")
            return False
        except Exception as e:
            logger.error(f"Error deleting webhook by URL: {e}")
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


    async def get_models_with_deploy_tag(self) -> list[dict[str, Any]]:
        """
        Poll MLflow to find all model versions with deploy=true tag.

        Returns:
            List of dicts with model_name, version, and tags for models marked for deployment
        """
        try:
            logger.debug("Polling MLflow for models with deploy=true tag")

            # Run the synchronous SDK calls in a thread pool
            registered_models = await asyncio.to_thread(
                self._client.search_registered_models
            )

            models_to_deploy = []

            for model in registered_models:
                model_name = model.name

                # Get all versions for this model
                versions = await asyncio.to_thread(
                    self._client.search_model_versions,
                    f"name='{model_name}'"
                )

                for version in versions:
                    # Check if this version has deploy=true tag
                    tags = version.tags or {}
                    if tags.get("deploy") == "true":
                        logger.debug(
                            f"Found model with deploy=true: {model_name} v{version.version}"
                        )
                        models_to_deploy.append({
                            "name": model_name,
                            "version": str(version.version),
                            "run_id": version.run_id,
                            "source": version.source,
                            "tags": tags
                        })

            logger.info(f"Found {len(models_to_deploy)} models with deploy=true tag")
            return models_to_deploy

        except Exception as e:
            logger.error(f"Error polling MLflow for deploy tags: {e}", exc_info=True)
            return []
