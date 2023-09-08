import pytest
from nebari_plugin_mlflow_aws import MlflowStage, MlflowConfig, InputSchema

class TestConfig(InputSchema):
    __test__ = False
    namespace: str
    domain: str
    escaped_project_name: str = ""
    provider: str
    mlflow: MlflowConfig = MlflowConfig()

@pytest.fixture(autouse=True)
def mock_keycloak_connection(monkeypatch):
    monkeypatch.setattr("nebari_plugin_mlflow_aws.MlflowStage._attempt_keycloak_connection", lambda *args, **kwargs: True)

def test_ctor():
    sut = MlflowStage(output_directory = None, config = None)
    assert sut.name == "mlflow"
    assert sut.priority == 102

def test_input_vars():
    config = TestConfig(namespace = "nebari-ns", domain = "my-test-domain.com", escaped_project_name="testprojectname", provider="aws")
    sut = MlflowStage(output_directory = None, config = config)
    

    stage_outputs = get_stage_outputs()
    sut.check(stage_outputs)
    result = sut.input_vars(stage_outputs)
    assert result["chart_name"] == "mlflow"
    assert result["project_name"] == "testprojectname"
    assert result["realm_id"] == "test-realm"
    assert result["client_id"] == "mlflow"
    assert result["base_url"] == "https://my-test-domain.com/mlflow"
    assert result["external_url"] == "https://my-test-domain.com/auth/"
    assert result["valid_redirect_uris"] == ["https://my-test-domain.com/mlflow/_oauth"]
    assert result["signing_key_ref"] == {'kind': 'Deployment', 'name': 'forwardauth-deployment', 'namespace': 'nebari-ns'}
    assert result["create_namespace"] == False
    assert result["namespace"] == "nebari-ns"
    assert result["ingress_host"] == "my-test-domain.com"
    assert result["cluster_oidc_issuer_url"] == "https://test-oidc-url.com"
    assert result["overrides"] == {}

def test_incompatible_cloud():
    with pytest.raises(KeyError) as e_info:
        config = TestConfig(namespace = "nebari-ns", domain = "my-test-domain.com", escaped_project_name="testprojectname", provider="gcp")
        sut = MlflowStage(output_directory = None, config = config)

        stage_outputs = get_stage_outputs()
        _ = sut.input_vars(stage_outputs)

    assert str(e_info.value) == "'Plugin nebari_plugin_mlflow_aws developed for aws only.  Detected provider is gcp.'"
 
def test_default_namespace():
    config = TestConfig(namespace = "nebari-ns", domain = "my-test-domain.com", provider="aws")
    sut = MlflowStage(output_directory = None, config = config)

    stage_outputs = get_stage_outputs()
    result = sut.input_vars(stage_outputs)
    assert result["create_namespace"] == False
    assert result["namespace"] == "nebari-ns"

def test_chart_namespace():
    config = TestConfig(namespace = "nebari-ns", domain = "my-test-domain.com", provider="aws", mlflow = MlflowConfig(namespace = "mlflow-ns"))
    sut = MlflowStage(output_directory = None, config = config)

    stage_outputs = get_stage_outputs()
    result = sut.input_vars(stage_outputs)
    assert result["create_namespace"] == True
    assert result["namespace"] == "mlflow-ns"

def test_chart_overrides():
    config = TestConfig(namespace = "nebari-ns", domain = "my-test-domain.com", provider="aws", mlflow = MlflowConfig(values = { "foo": "bar" }))
    sut = MlflowStage(output_directory = None, config = config)

    stage_outputs = get_stage_outputs()
    result = sut.input_vars(stage_outputs)
    assert result["overrides"] == { "foo": "bar" }

def get_stage_outputs():
    return {
        "stages/02-infrastructure": {
            "cluster_oidc_issuer_url": {
                "value": "https://test-oidc-url.com"
            }
        },
        "stages/04-kubernetes-ingress": {
            "domain": "my-test-domain.com"
        },
        "stages/05-kubernetes-keycloak": {
            "keycloak_credentials": {
                "value": {
                    "url": "https://my-test-domain.com",
                    "username": "testuser",
                    "password": "testpassword",
                    "realm": "testmasterrealm",
                    "client_id": "testmasterclientid"
                }
            }
        },
        "stages/06-kubernetes-keycloak-configuration": {
            "realm_id": {
                "value": "test-realm"
            }
        }
    }