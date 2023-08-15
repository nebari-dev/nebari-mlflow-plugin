import inspect
import sys
import time

from nebari.schema import Base
from _nebari.stages.base import NebariTerraformStage
from nebari.hookspecs import NebariStage, hookimpl
from pathlib import Path
from typing import Any, Dict, List, Optional

NUM_ATTEMPTS = 10
TIMEOUT = 10

CLIENT_NAME = "mlflow"

#TODO this only works for AWS.  How to check

class MlflowConfig(Base):
    namespace: Optional[str] = None

class InputSchema(Base):
    ml_flow: MlflowConfig = MlflowConfig()

class MlflowStage(NebariTerraformStage):
    name = "mlflow"
    priority = 102
    wait = True # wait for install to complete on nebari deploy
    input_schema = InputSchema

    @property
    def template_directory(self):
        return Path(inspect.getfile(self.__class__)).parent / "terraform"
    
    def check(self, stage_outputs: Dict[str, Dict[str, Any]]) -> bool:
        from keycloak import KeycloakAdmin
        from keycloak.exceptions import KeycloakError
        
        try:
            _ = stage_outputs["stages/02-infrastructure"]["node_group_iam_policy_name"]
            _ = stage_outputs["stages/04-kubernetes-ingress"]["domain"]
            
        except KeyError:
            print(
                "\nPrerequisite stage output(s) not found: stages/02-infrastructure, 04-kubernetes-ingress"
            )
            return False

        keycloak_config = self.get_keycloak_config(stage_outputs)
        
        def _attempt_keycloak_connection(
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
            for i in range(num_attempts):
                try:
                    realm_admin = KeycloakAdmin(
                        keycloak_url,
                        username=username,
                        password=password,
                        realm_name=master_realm_name,
                        client_id=client_id,
                        verify=verify,
                    )
                    realm_admin.realm_name = client_realm_name # switch to nebari realm
                    c = realm_admin.get_client_id(CLIENT_NAME) # lookup client guid
                    existing_client = realm_admin.get_client(c) # query client info
                    if existing_client != None and existing_client["name"] == CLIENT_NAME:
                        print(
                            f"Attempt {i+1} succeeded connecting to keycloak and nebari client={CLIENT_NAME} exists"
                        )
                        return True
                    else:
                        print(
                            f"Attempt {i+1} succeeded connecting to keycloak but nebari client={CLIENT_NAME} did not exist"
                        )
                except KeycloakError as e:
                    print(f"Attempt {i+1} failed connecting to keycloak {client_realm_name} realm -- {e}")
                time.sleep(timeout)
            return False

        if not _attempt_keycloak_connection(
            keycloak_config["keycloak_url"],
            keycloak_config["username"],
            keycloak_config["password"],
            keycloak_config["master_realm_id"],
            keycloak_config["master_client_id"],
            keycloak_config["realm_id"],
            verify=False,
        ):
            print(
                f"ERROR: unable to connect to keycloak master realm and ensure that nebari client={CLIENT_NAME} exists"
            )
            sys.exit(1)

        print(f"Keycloak successfully configured with {CLIENT_NAME} client")
        return True

    def input_vars(self, stage_outputs: Dict[str, Dict[str, Any]]):
        keycloak_config = self.get_keycloak_config(stage_outputs)
        try:
            node_group_iam_role = stage_outputs["stages/02-infrastructure"]["node_group_iam_role_name"]["value"]
            domain = stage_outputs["stages/04-kubernetes-ingress"]["domain"]
        except KeyError:
            raise Exception("Prerequisite stage output(s) not found: stages/02-infrastructure, 04-kubernetes-ingress")

        chart_ns = self.config.ml_flow.namespace
        create_ns = True
        if chart_ns == None or chart_ns == "" or chart_ns == self.config.namespace:
            chart_ns = self.config.namespace
            create_ns = False

        return {
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
            "namespace": chart_ns,
            "node_group_iam_role_name": node_group_iam_role,
            "ingress_host": domain
        }

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
    return [ MlflowStage ]
