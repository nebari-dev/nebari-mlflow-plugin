"""Kubernetes client for managing InferenceServices."""

import logging
from typing import Any, Dict, List, Optional

import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)


class KubernetesClientError(Exception):
    """Base exception for Kubernetes client errors."""
    pass


class InferenceServiceNotFoundError(KubernetesClientError):
    """Raised when an InferenceService is not found."""
    pass


class InferenceServiceAlreadyExistsError(KubernetesClientError):
    """Raised when attempting to create an InferenceService that already exists."""
    pass


class KubernetesClient:
    """Client for interacting with Kubernetes API to manage InferenceServices."""

    def __init__(self, namespace: str, in_cluster: bool = True):
        """
        Initialize Kubernetes client.

        Args:
            namespace: Kubernetes namespace for InferenceServices
            in_cluster: Whether to use in-cluster config (True) or local kubeconfig (False)

        Raises:
            KubernetesClientError: If unable to load Kubernetes configuration
        """
        self.namespace = namespace
        self.in_cluster = in_cluster

        try:
            # Load Kubernetes configuration
            if in_cluster:
                logger.info("Loading in-cluster Kubernetes configuration")
                config.load_incluster_config()
            else:
                logger.info("Loading local kubeconfig")
                config.load_kube_config()

            # Initialize API client for custom resources
            self.api_client = client.ApiClient()
            self.custom_api = client.CustomObjectsApi(self.api_client)

            # KServe InferenceService CRD details
            self.group = "serving.kserve.io"
            self.version = "v1beta1"
            self.plural = "inferenceservices"

            logger.info(
                f"Initialized Kubernetes client - namespace: {namespace}, "
                f"in_cluster: {in_cluster}"
            )
        except Exception as e:
            error_msg = f"Failed to initialize Kubernetes client: {str(e)}"
            logger.error(error_msg)
            raise KubernetesClientError(error_msg) from e

    async def create_inference_service(
        self, name: str, manifest: str
    ) -> dict[str, Any]:
        """
        Create an InferenceService from YAML manifest.

        Args:
            name: Name of the InferenceService
            manifest: YAML manifest as string

        Returns:
            Dictionary with status and details of the created InferenceService

        Raises:
            InferenceServiceAlreadyExistsError: If InferenceService already exists
            KubernetesClientError: For other Kubernetes API errors
        """
        logger.info(f"Creating InferenceService: {name} in namespace: {self.namespace}")
        logger.debug(f"Manifest: {manifest}")

        try:
            # Parse YAML manifest
            body = yaml.safe_load(manifest)

            # Validate that it's an InferenceService
            if body.get("kind") != "InferenceService":
                raise KubernetesClientError(
                    f"Invalid manifest: expected kind 'InferenceService', got '{body.get('kind')}'"
                )

            # Create the InferenceService
            response = self.custom_api.create_namespaced_custom_object(
                group=self.group,
                version=self.version,
                namespace=self.namespace,
                plural=self.plural,
                body=body,
            )

            logger.info(
                f"Successfully created InferenceService: {name} in namespace: {self.namespace}"
            )

            return {
                "status": "created",
                "name": name,
                "namespace": self.namespace,
                "uid": response.get("metadata", {}).get("uid"),
            }

        except ApiException as e:
            if e.status == 409:
                error_msg = f"InferenceService '{name}' already exists in namespace '{self.namespace}'"
                logger.warning(error_msg)
                raise InferenceServiceAlreadyExistsError(error_msg) from e
            else:
                error_msg = (
                    f"Kubernetes API error creating InferenceService '{name}': "
                    f"status={e.status}, reason={e.reason}, body={e.body}"
                )
                logger.error(error_msg)
                raise KubernetesClientError(error_msg) from e
        except yaml.YAMLError as e:
            error_msg = f"Failed to parse YAML manifest: {str(e)}"
            logger.error(error_msg)
            raise KubernetesClientError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error creating InferenceService '{name}': {str(e)}"
            logger.error(error_msg)
            raise KubernetesClientError(error_msg) from e

    async def delete_inference_service(self, name: str) -> dict[str, Any]:
        """
        Delete an InferenceService by name.

        This operation is idempotent - deleting a non-existent service succeeds.

        Args:
            name: Name of the InferenceService to delete

        Returns:
            Dictionary with status and details of the deletion

        Raises:
            KubernetesClientError: For Kubernetes API errors (except 404)
        """
        logger.info(f"Deleting InferenceService: {name} from namespace: {self.namespace}")

        try:
            # Delete the InferenceService
            self.custom_api.delete_namespaced_custom_object(
                group=self.group,
                version=self.version,
                namespace=self.namespace,
                plural=self.plural,
                name=name,
            )

            logger.info(
                f"Successfully deleted InferenceService: {name} from namespace: {self.namespace}"
            )

            return {
                "status": "deleted",
                "name": name,
                "namespace": self.namespace,
            }

        except ApiException as e:
            if e.status == 404:
                # Idempotent: treat 404 as success
                logger.info(
                    f"InferenceService '{name}' not found in namespace '{self.namespace}' "
                    f"(already deleted or never existed)"
                )
                return {
                    "status": "deleted",
                    "name": name,
                    "namespace": self.namespace,
                    "note": "already_deleted",
                }
            else:
                error_msg = (
                    f"Kubernetes API error deleting InferenceService '{name}': "
                    f"status={e.status}, reason={e.reason}, body={e.body}"
                )
                logger.error(error_msg)
                raise KubernetesClientError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error deleting InferenceService '{name}': {str(e)}"
            logger.error(error_msg)
            raise KubernetesClientError(error_msg) from e

    async def get_inference_service(self, name: str) -> dict[str, Any] | None:
        """
        Get an InferenceService by name.

        Args:
            name: Name of the InferenceService

        Returns:
            Dictionary with InferenceService details, or None if not found

        Raises:
            KubernetesClientError: For Kubernetes API errors (except 404)
        """
        logger.info(f"Getting InferenceService: {name} from namespace: {self.namespace}")

        try:
            response = self.custom_api.get_namespaced_custom_object(
                group=self.group,
                version=self.version,
                namespace=self.namespace,
                plural=self.plural,
                name=name,
            )

            logger.debug(f"Found InferenceService: {name}")

            # Extract relevant information
            metadata = response.get("metadata", {})
            status = response.get("status", {})

            return {
                "name": metadata.get("name"),
                "namespace": metadata.get("namespace"),
                "uid": metadata.get("uid"),
                "labels": metadata.get("labels", {}),
                "creation_timestamp": metadata.get("creationTimestamp"),
                "status": status,
            }

        except ApiException as e:
            if e.status == 404:
                logger.info(
                    f"InferenceService '{name}' not found in namespace '{self.namespace}'"
                )
                return None
            else:
                error_msg = (
                    f"Kubernetes API error getting InferenceService '{name}': "
                    f"status={e.status}, reason={e.reason}, body={e.body}"
                )
                logger.error(error_msg)
                raise KubernetesClientError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error getting InferenceService '{name}': {str(e)}"
            logger.error(error_msg)
            raise KubernetesClientError(error_msg) from e

    async def list_inference_services(
        self, label_selector: str | None = None
    ) -> list[dict[str, Any]]:
        """
        List all InferenceServices, optionally filtered by labels.

        Args:
            label_selector: Optional label selector (e.g., "managed-by=mlflow-kserve-webhook-listener")

        Returns:
            List of dictionaries with InferenceService details

        Raises:
            KubernetesClientError: For Kubernetes API errors
        """
        logger.info(
            f"Listing InferenceServices in namespace: {self.namespace} "
            f"with label_selector: {label_selector}"
        )

        try:
            # List InferenceServices
            response = self.custom_api.list_namespaced_custom_object(
                group=self.group,
                version=self.version,
                namespace=self.namespace,
                plural=self.plural,
                label_selector=label_selector,
            )

            items = response.get("items", [])
            logger.info(f"Found {len(items)} InferenceServices")

            # Extract relevant information from each item
            services = []
            for item in items:
                metadata = item.get("metadata", {})
                status = item.get("status", {})

                services.append({
                    "name": metadata.get("name"),
                    "namespace": metadata.get("namespace"),
                    "uid": metadata.get("uid"),
                    "labels": metadata.get("labels", {}),
                    "creation_timestamp": metadata.get("creationTimestamp"),
                    "status": status,
                })

            return services

        except ApiException as e:
            error_msg = (
                f"Kubernetes API error listing InferenceServices: "
                f"status={e.status}, reason={e.reason}, body={e.body}"
            )
            logger.error(error_msg)
            raise KubernetesClientError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error listing InferenceServices: {str(e)}"
            logger.error(error_msg)
            raise KubernetesClientError(error_msg) from e

    async def update_inference_service(
        self, name: str, manifest: str
    ) -> dict[str, Any]:
        """
        Update an existing InferenceService.

        If the InferenceService doesn't exist, it will be created instead.

        Args:
            name: Name of the InferenceService
            manifest: YAML manifest as string

        Returns:
            Dictionary with status and details of the updated InferenceService

        Raises:
            KubernetesClientError: For Kubernetes API errors
        """
        logger.info(f"Updating InferenceService: {name} in namespace: {self.namespace}")
        logger.debug(f"Manifest: {manifest}")

        try:
            # Parse YAML manifest
            body = yaml.safe_load(manifest)

            # Validate that it's an InferenceService
            if body.get("kind") != "InferenceService":
                raise KubernetesClientError(
                    f"Invalid manifest: expected kind 'InferenceService', got '{body.get('kind')}'"
                )

            # Check if InferenceService exists
            existing = await self.get_inference_service(name)

            if existing:
                # Update existing InferenceService (PATCH or replace)
                response = self.custom_api.patch_namespaced_custom_object(
                    group=self.group,
                    version=self.version,
                    namespace=self.namespace,
                    plural=self.plural,
                    name=name,
                    body=body,
                )

                logger.info(
                    f"Successfully updated InferenceService: {name} in namespace: {self.namespace}"
                )

                return {
                    "status": "updated",
                    "name": name,
                    "namespace": self.namespace,
                    "uid": response.get("metadata", {}).get("uid"),
                }
            else:
                # Create new InferenceService
                logger.info(
                    f"InferenceService '{name}' does not exist, creating instead of updating"
                )
                return await self.create_inference_service(name, manifest)

        except yaml.YAMLError as e:
            error_msg = f"Failed to parse YAML manifest: {str(e)}"
            logger.error(error_msg)
            raise KubernetesClientError(error_msg) from e
        except ApiException as e:
            error_msg = (
                f"Kubernetes API error updating InferenceService '{name}': "
                f"status={e.status}, reason={e.reason}, body={e.body}"
            )
            logger.error(error_msg)
            raise KubernetesClientError(error_msg) from e
        except KubernetesClientError:
            # Re-raise our own exceptions
            raise
        except Exception as e:
            error_msg = f"Unexpected error updating InferenceService '{name}': {str(e)}"
            logger.error(error_msg)
            raise KubernetesClientError(error_msg) from e
