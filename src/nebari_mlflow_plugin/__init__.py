import inspect
import json
import sys
import time

from nebari.schema import Base, ProviderEnum
from _nebari.stages.base import NebariTerraformStage
from nebari.hookspecs import NebariStage, hookimpl
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import field_validator

NUM_ATTEMPTS = 10
TIMEOUT = 10

CLIENT_NAME = "mlflow"

class MlflowConfigAWS(Base):
    enable_s3_encryption: Optional[bool] = True

class MlflowConfigAzure(Base):
    ...

class MlflowConfigGCP(Base):
    ...

class MlflowProvidersInputSchema(Base):
    enabled: bool = True
    overrides: Optional[Dict[str, Any]] = {}

    # provder specific config
    aws: Optional[MlflowConfigAWS] = None
    azure: Optional[MlflowConfigAzure] = None
    gcp: Optional[MlflowConfigGCP] = None

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

    def _attempt_keycloak_connection(
        self,
        keycloak_url,
        username,
        password,
        master_realm_name,
        client_id,
        client_realm_name,
        verify=False,
        num_attempts=NUM_ATTEMPTS,
        timeout=TIMEOUT,
    ):
        from keycloak import KeycloakAdmin
        from keycloak.exceptions import KeycloakError

        for i in range(num_attempts):
            try:
                realm_admin = KeycloakAdmin(
                    keycloak_url,
                    username=username,
                    password=password,
                    user_realm_name=master_realm_name,
                    realm_name=client_realm_name,
                    client_id=client_id,
                    verify=verify,
                )
                c = realm_admin.get_client_id(CLIENT_NAME)  # lookup client guid
                existing_client = realm_admin.get_client(c)  # query client info
                if existing_client != None and existing_client["name"] == CLIENT_NAME:
                    print(f"Attempt {i+1} succeeded connecting to keycloak and nebari client={CLIENT_NAME} exists")
                    return True
                else:
                    print(
                        f"Attempt {i+1} succeeded connecting to keycloak but nebari client={CLIENT_NAME} did not exist"
                    )
            except KeycloakError as e:
                print(f"Attempt {i+1} failed connecting to keycloak {client_realm_name} realm -- {e}")
            time.sleep(timeout)
        return False

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

            keycloak_config = self.get_keycloak_config(stage_outputs)

            if not self._attempt_keycloak_connection(
                keycloak_url=keycloak_config["keycloak_url"],
                username=keycloak_config["username"],
                password=keycloak_config["password"],
                master_realm_name=keycloak_config["master_realm_id"],
                client_id=keycloak_config["master_client_id"],
                client_realm_name=keycloak_config["realm_id"],
                verify=False,
            ):
                print(
                    f"ERROR: unable to connect to keycloak master realm and ensure that nebari client={CLIENT_NAME} exists"
                )
                sys.exit(1)

            print(f"Keycloak successfully configured with {CLIENT_NAME} client")
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
        else:
            raise NotImplementedError(f"Provider {self.config.provider} not implemented")

        return True

    def input_vars(self, stage_outputs: Dict[str, Dict[str, Any]]):
        if self.config.provider == ProviderEnum.aws:
            keycloak_config = self.get_keycloak_config(stage_outputs)

            if not self.config.provider == ProviderEnum.aws:
                raise KeyError(
                    "Plugin nebari_plugin_mlflow_aws developed for aws only.  Detected provider is {}.".format(
                        self.config.provider
                    )
                )

            # TODO: Module requires EKS cluster is configured for IRSA.  Once Nebari version with IRSA is released, should update
            # this error message and also minimum Nebari version in pyproject.toml
            try:
                _ = stage_outputs["stages/02-infrastructure"]["cluster_oidc_issuer_url"]["value"]

            except KeyError:
                raise Exception(
                    "Prerequisite stage output(s) not found in stages/02-infrastructure: cluster_oidc_issuer_url.  Please ensure Nebari version is at least XX."
                )

            try:
                domain = stage_outputs["stages/04-kubernetes-ingress"]["domain"]
                cluster_oidc_issuer_url = stage_outputs["stages/02-infrastructure"]["cluster_oidc_issuer_url"]["value"]

            except KeyError:
                raise Exception(
                    "Prerequisite stage output(s) not found: stages/02-infrastructure, stages/04-kubernetes-ingress"
                )

            chart_ns = self.config.mlflow.namespace
            create_ns = True
            if chart_ns == None or chart_ns == "" or chart_ns == self.config.namespace:
                chart_ns = self.config.namespace
                create_ns = False

            return {
                "chart_name": self.config.mlflow.name,
                "project_name": self.config.escaped_project_name,
                "region": self.config.amazon_web_services.region,
                "realm_id": keycloak_config["realm_id"],
                "client_id": CLIENT_NAME,
                "base_url": f"https://{keycloak_config['domain']}/mlflow",
                "external_url": keycloak_config["keycloak_url"],
                "valid_redirect_uris": [f"https://{keycloak_config['domain']}/mlflow/_oauth"],
                "signing_key_ref": {
                    "name": "forwardauth-deployment",
                    "kind": "Deployment",
                    "namespace": self.config.namespace,
                },
                "create_namespace": create_ns,
                "enable_s3_encryption": self.config.mlflow.enable_s3_encryption,
                "namespace": chart_ns,
                "ingress_host": domain,
                "cluster_oidc_issuer_url": cluster_oidc_issuer_url,
                "overrides": self.config.mlflow.values,
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
        else:
            raise NotImplementedError(f"Provider {self.config.provider} not implemented")

    def get_keycloak_config(self, stage_outputs: Dict[str, Dict[str, Any]]):
        directory = "stages/05-kubernetes-keycloak"

        return {
            "domain": stage_outputs["stages/04-kubernetes-ingress"]["domain"],
            "keycloak_url": f"{stage_outputs[directory]['keycloak_credentials']['value']['url']}/auth/",
            "username": stage_outputs[directory]["keycloak_credentials"]["value"]["username"],
            "password": stage_outputs[directory]["keycloak_credentials"]["value"]["password"],
            "master_realm_id": stage_outputs[directory]["keycloak_credentials"]["value"]["realm"],
            "master_client_id": stage_outputs[directory]["keycloak_credentials"]["value"]["client_id"],
            "realm_id": stage_outputs["stages/06-kubernetes-keycloak-configuration"]["realm_id"]["value"],
        }


@hookimpl
def nebari_stage() -> List[NebariStage]:
    return [MlflowStage]
