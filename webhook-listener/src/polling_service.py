"""Polling service for checking MLflow models when webhooks are unavailable."""

import asyncio
import logging
from typing import Any

from src.config import settings
from src.kubernetes_client import KubernetesClient
from src.mlflow_client import MLflowClient, resolve_mlflow_artifacts_uri
from src.templates import generate_inference_service_name, render_inference_service

logger = logging.getLogger(__name__)


class PollingService:
    """Service that periodically polls MLflow for models with deploy tags."""

    def __init__(
        self,
        mlflow_client: MLflowClient,
        k8s_client: KubernetesClient,
        interval: int = 60
    ):
        """
        Initialize the polling service.

        Args:
            mlflow_client: MLflow client instance
            k8s_client: Kubernetes client instance
            interval: Polling interval in seconds
        """
        self.mlflow_client = mlflow_client
        self.k8s_client = k8s_client
        self.interval = interval
        self._task: asyncio.Task | None = None
        self._running = False
        # Track deployed models to avoid redundant operations
        self._deployed_models: set[tuple[str, str]] = set()

    async def start(self):
        """Start the polling service in the background."""
        if self._running:
            logger.warning("Polling service is already running")
            return

        logger.info(f"Starting polling service (interval: {self.interval}s)")
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self):
        """Stop the polling service."""
        if not self._running:
            return

        logger.info("Stopping polling service")
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self):
        """Main polling loop that runs in the background."""
        logger.info("Polling service started")

        while self._running:
            try:
                await self._poll_and_reconcile()
            except Exception as e:
                logger.error(f"Error in polling loop: {e}", exc_info=True)

            # Wait for next interval
            try:
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break

        logger.info("Polling service stopped")

    async def _poll_and_reconcile(self):
        """
        Poll MLflow for models with deploy tags and reconcile with Kubernetes.

        This method:
        1. Gets all models with deploy=true tag from MLflow
        2. Gets all managed InferenceServices from Kubernetes
        3. Creates/updates InferenceServices for models that should be deployed
        4. Deletes InferenceServices for models that should not be deployed
        """
        try:
            # Get models with deploy=true from MLflow
            models_to_deploy = await self.mlflow_client.get_models_with_deploy_tag()

            # Build set of (model_name, version) tuples for models that should be deployed
            desired_deployments = {
                (model["name"], model["version"])
                for model in models_to_deploy
            }

            # Get currently deployed services from Kubernetes
            deployed_services = await self.k8s_client.list_inference_services(
                label_selector="managed-by=mlflow-kserve-webhook-listener"
            )

            # Build set of currently deployed (model_name, version) tuples
            current_deployments = set()
            deployed_service_names = {}
            for svc in deployed_services:
                labels = svc.get("labels", {})
                model_name = labels.get("mlflow.model")
                version = labels.get("mlflow.version")
                if model_name and version:
                    current_deployments.add((model_name, version))
                    deployed_service_names[(model_name, version)] = svc["name"]

            # Find models that need to be deployed (in desired but not in current)
            to_deploy = desired_deployments - current_deployments

            # Find models that need to be undeployed (in current but not in desired)
            to_undeploy = current_deployments - desired_deployments

            if to_deploy or to_undeploy:
                logger.info(
                    f"Reconciliation needed: {len(to_deploy)} to deploy, "
                    f"{len(to_undeploy)} to undeploy"
                )

            # Deploy new models
            for model_name, version in to_deploy:
                await self._deploy_model(model_name, version, models_to_deploy)

            # Undeploy removed models
            for model_name, version in to_undeploy:
                service_name = deployed_service_names.get((model_name, version))
                if service_name:
                    await self._undeploy_model(model_name, version, service_name)

            # Update tracking set
            self._deployed_models = desired_deployments

        except Exception as e:
            logger.error(f"Error during poll and reconcile: {e}", exc_info=True)

    async def _deploy_model(
        self,
        model_name: str,
        version: str,
        models_data: list[dict[str, Any]]
    ):
        """
        Deploy a model to Kubernetes.

        Args:
            model_name: Name of the model
            version: Version of the model
            models_data: List of model data from MLflow
        """
        try:
            # Find the model data
            model_data = next(
                (m for m in models_data if m["name"] == model_name and m["version"] == version),
                None
            )

            if not model_data:
                logger.error(f"Model data not found for {model_name} v{version}")
                return

            logger.info(f"Deploying model via polling: {model_name} v{version}")

            run_id = model_data.get("run_id", "")
            source_uri = model_data["source"]

            # Resolve mlflow-artifacts:// URIs to actual cloud storage paths
            storage_uri = resolve_mlflow_artifacts_uri(source_uri)

            # Get run details to fetch experiment_id (if run_id is available)
            experiment_id = "unknown"
            if run_id:
                try:
                    run_details = await self.mlflow_client.get_run(run_id)
                    experiment_id = run_details["experiment_id"]
                except Exception as e:
                    logger.warning(
                        f"Could not fetch run details for {run_id}, using defaults: {e}"
                    )
                    run_id = "unknown"
            else:
                logger.warning(
                    f"Model {model_name} v{version} has no run_id, using 'unknown'"
                )
                run_id = "unknown"

            # Render the InferenceService manifest
            manifest = render_inference_service(
                model_name=model_name,
                model_version=version,
                storage_uri=storage_uri,
                run_id=run_id,
                experiment_id=experiment_id,
                namespace=settings.kube_namespace,
            )

            # Generate the InferenceService name
            service_name = generate_inference_service_name(model_name, version)

            # Deploy to Kubernetes (update creates if doesn't exist)
            result = await self.k8s_client.update_inference_service(service_name, manifest)

            logger.info(
                f"Successfully deployed InferenceService via polling: {service_name}"
            )

        except Exception as e:
            logger.error(
                f"Error deploying model via polling: {model_name} v{version}: {e}",
                exc_info=True
            )

    async def _undeploy_model(
        self,
        model_name: str,
        version: str,
        service_name: str
    ):
        """
        Undeploy a model from Kubernetes.

        Args:
            model_name: Name of the model
            version: Version of the model
            service_name: Name of the InferenceService
        """
        try:
            logger.info(f"Undeploying model via polling: {model_name} v{version}")

            result = await self.k8s_client.delete_inference_service(service_name)

            logger.info(
                f"Successfully undeployed InferenceService via polling: {service_name}"
            )

        except Exception as e:
            logger.error(
                f"Error undeploying model via polling: {model_name} v{version}: {e}",
                exc_info=True
            )
