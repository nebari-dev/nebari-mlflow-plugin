import inspect
import json

from nebari.schema import Base, ProviderEnum
from _nebari.stages.base import NebariTerraformStage
from nebari.hookspecs import NebariStage, hookimpl
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import field_validator

class MlflowConfigAWS(Base):
    enable_s3_encryption: Optional[bool] = True

class MlflowConfigAzure(Base):
    ...

class MlflowConfigGCP(Base):
    ...

class MlflowConfigLocal(Base):
    minio_root_password: str = "minio-secret-password"

class MlflowProvidersInputSchema(Base):
    enabled: bool = True
    overrides: Optional[Dict[str, Any]] = {}

    # provder specific config
    aws: Optional[MlflowConfigAWS] = None
    azure: Optional[MlflowConfigAzure] = None
    gcp: Optional[MlflowConfigGCP] = None
    local: Optional[MlflowConfigLocal] = None

class InputSchema(Base):
    mlflow: MlflowProvidersInputSchema

class MlflowStage(NebariTerraformStage):
    name = "mlflow"
    priority = 102
    wait = True  # wait for install to complete on nebari deploy
    input_schema = InputSchema

    @property
    def template_directory(self):
        return (
            Path(inspect.getfile(self.__class__)).parent
            / "template"
            / self.config.provider.value
        )

    def check(self, stage_outputs: Dict[str, Dict[str, Any]], disable_prompt=False) -> bool:
        # TODO: Module requires EKS cluster is configured for IRSA.  Once Nebari version with IRSA is released, should update
        # this error message and also minimum Nebari version in pyproject.toml
        if self.config.provider == ProviderEnum.aws:
            try:
                _ = stage_outputs["stages/02-infrastructure"]["cluster_oidc_issuer_url"]["value"]

            except KeyError:
                print(
                    "\nPrerequisite stage output(s) not found in stages/02-infrastructure: cluster_oidc_issuer_url.  Please ensure Nebari version is at least XX."
                )
                return False

            try:
                _ = self.config.escaped_project_name
                _ = self.config.provider

            except KeyError:
                print("\nBase config values not found: escaped_project_name, provider")
                return False
        elif self.config.provider == ProviderEnum.azure.value:
            try:
                _ = stage_outputs["stages/02-infrastructure"]["cluster_oidc_issuer_url"]["value"]
            except KeyError:
                print(
                    "\nPrerequisite stage output(s) not found in stages/02-infrastructure: cluster_oidc_issuer_url.  Please ensure Nebari version is at least XX."
                )
                return False

            try:
                _ = self.config.escaped_project_name
                _ = self.config.provider
            except KeyError:
                print("\nBase config values not found: escaped_project_name, provider")
                return False
        elif self.config.provider == ProviderEnum.gcp:
            try:
                _ = stage_outputs["stages/02-infrastructure"]["cluster_oidc_issuer_url"]["value"]
            except KeyError:
                print(
                    "\nPrerequisite stage output(s) not found in stages/02-infrastructure: cluster_oidc_issuer_url.  Please ensure Nebari version is at least XX."
                )
                return False

            try:
                _ = self.config.escaped_project_name
                _ = self.config.provider
            except KeyError:
                print("\nBase config values not found: escaped_project_name, provider")
                return False
        elif self.config.provider == ProviderEnum.local:
            # Local deployments don't require OIDC issuer URLs
            pass
        else:
            raise NotImplementedError(f"Provider {self.config.provider} not implemented")

        return True

    def input_vars(self, stage_outputs: Dict[str, Dict[str, Any]]):
        if self.config.provider == ProviderEnum.aws:
            cluster_oidc_issuer_url = stage_outputs["stages/02-infrastructure"]["cluster_oidc_issuer_url"]["value"]
            external_url = stage_outputs["stages/04-kubernetes-ingress"]["domain"]
            forwardauth_service_name = stage_outputs["stages/07-kubernetes-services"]["forward-auth-service"]["value"]["name"]
            forwardauth_middleware_name = stage_outputs["stages/07-kubernetes-services"]["forward-auth-middleware"]["value"]["name"]

            enable_s3_encryption = True
            if self.config.mlflow.aws:
                enable_s3_encryption = self.config.mlflow.aws.enable_s3_encryption

            return {
                "enabled": self.config.mlflow.enabled,
                "namespace": self.config.namespace,
                "external_url": external_url,
                "helm-release-name": self.config.project_name + '-mlflow',
                "forwardauth-service-name": forwardauth_service_name,
                "forwardauth-middleware-name": forwardauth_middleware_name,
                "cluster_oidc_issuer_url": cluster_oidc_issuer_url,
                "project_name": self.config.escaped_project_name,
                "region": self.config.amazon_web_services.region,
                "enable_s3_encryption": enable_s3_encryption,
                "overrides": [json.dumps(self.config.mlflow.overrides)],
            }
        elif self.config.provider == ProviderEnum.azure:
            cluster_oidc_issuer_url = stage_outputs["stages/02-infrastructure"]["cluster_oidc_issuer_url"]["value"]
            external_url = stage_outputs["stages/04-kubernetes-ingress"]["domain"]
            resource_group_name = stage_outputs["stages/02-infrastructure"]["resource_group_name"]["value"]
            forwardauth_service_name = stage_outputs["stages/07-kubernetes-services"]["forward-auth-service"]["value"]["name"]
            forwardauth_middleware_name = stage_outputs["stages/07-kubernetes-services"]["forward-auth-middleware"]["value"]["name"]

            return {
                "enabled": self.config.mlflow.enabled,
                "namespace": self.config.namespace,
                "external_url": external_url,
                "helm-release-name": self.config.project_name + '-mlflow',
                "forwardauth-service-name": forwardauth_service_name,
                "forwardauth-middleware-name": forwardauth_middleware_name,
                "cluster_oidc_issuer_url": cluster_oidc_issuer_url,
                "storage_resource_group_name": resource_group_name,
                "region": self.config.azure.region,
                "storage_account_name": self.config.project_name[:15] + 'mlfsa' + self.config.azure.storage_account_postfix,
                "overrides": [json.dumps(self.config.mlflow.overrides)],
            }
        elif self.config.provider == ProviderEnum.gcp:
            cluster_oidc_issuer_url = stage_outputs["stages/02-infrastructure"]["cluster_oidc_issuer_url"]["value"]
            external_url = stage_outputs["stages/04-kubernetes-ingress"]["domain"]
            project_id = stage_outputs["stages/02-infrastructure"]["project_id"]["value"]
            forwardauth_service_name = stage_outputs["stages/07-kubernetes-services"]["forward-auth-service"]["value"]["name"]
            forwardauth_middleware_name = stage_outputs["stages/07-kubernetes-services"]["forward-auth-middleware"]["value"]["name"]

            return {
                "enabled": self.config.mlflow.enabled,
                "namespace": self.config.namespace,
                "external_url": external_url,
                "helm-release-name": self.config.project_name + '-mlflow',
                "forwardauth-service-name": forwardauth_service_name,
                "forwardauth-middleware-name": forwardauth_middleware_name,
                "cluster_oidc_issuer_url": cluster_oidc_issuer_url,
                "project_id": project_id,
                "region": self.config.google_cloud_platform.region,
                "bucket_name": f"{self.config.project_name}-mlflow-artifacts",
                "overrides": [json.dumps(self.config.mlflow.overrides)],
            }
        elif self.config.provider == ProviderEnum.local:
            external_url = stage_outputs["stages/04-kubernetes-ingress"]["domain"]
            forwardauth_service_name = stage_outputs["stages/07-kubernetes-services"]["forward-auth-service"]["value"]["name"]
            forwardauth_middleware_name = stage_outputs["stages/07-kubernetes-services"]["forward-auth-middleware"]["value"]["name"]

            minio_password = self.config.mlflow.local.minio_root_password if self.config.mlflow.local else "minio-secret-password"

            return {
                "enabled": self.config.mlflow.enabled,
                "namespace": self.config.namespace,
                "external_url": external_url,
                "helm-release-name": self.config.project_name + '-mlflow',
                "forwardauth-service-name": forwardauth_service_name,
                "forwardauth-middleware-name": forwardauth_middleware_name,
                "minio_root_password": minio_password,
                "overrides": [json.dumps(self.config.mlflow.overrides)],
            }
        else:
            raise NotImplementedError(f"Provider {self.config.provider} not implemented")


@hookimpl
def nebari_stage() -> List[NebariStage]:
    return [MlflowStage]
