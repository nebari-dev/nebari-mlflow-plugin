import pytest
from unittest.mock import Mock
from nebari_mlflow_plugin import MlflowStage, MlflowProvidersInputSchema, MlflowConfigAWS

def create_test_config(namespace, domain, escaped_project_name, project_name, provider, mlflow=None):
    """Helper function to create a mock config object"""
    config = Mock()
    config.namespace = namespace
    config.domain = domain
    config.escaped_project_name = escaped_project_name
    config.project_name = project_name
    config.provider = provider
    config.mlflow = mlflow or MlflowProvidersInputSchema()

    # Add provider-specific attributes
    aws_config = Mock()
    aws_config.region = "us-east-1"
    config.amazon_web_services = aws_config

    azure_config = Mock()
    azure_config.region = "eastus"
    azure_config.storage_account_postfix = "abc123"
    config.azure = azure_config

    gcp_config = Mock()
    gcp_config.region = "us-central1"
    config.google_cloud_platform = gcp_config

    return config

def test_ctor():
    sut = MlflowStage(output_directory = None, config = None)
    assert sut.name == "mlflow"
    assert sut.priority == 102

def test_input_vars_aws():
    config = create_test_config(
        namespace="nebari-ns",
        domain="my-test-domain.com",
        escaped_project_name="testprojectname",
        project_name="testproject",
        provider="aws"
    )
    sut = MlflowStage(output_directory = None, config = config)

    stage_outputs = get_stage_outputs_aws()
    sut.check(stage_outputs)
    result = sut.input_vars(stage_outputs)

    assert result["enabled"] == True
    assert result["namespace"] == "nebari-ns"
    assert result["external_url"] == "my-test-domain.com"
    assert result["helm-release-name"] == "testproject-mlflow"
    assert result["forwardauth-service-name"] == "forwardauth-service"
    assert result["forwardauth-middleware-name"] == "forwardauth-middleware"
    assert result["cluster_oidc_issuer_url"] == "https://test-oidc-url.com"
    assert result["project_name"] == "testprojectname"
    assert result["region"] == "us-east-1"
    assert result["enable_s3_encryption"] == True
    assert result["overrides"] == ['{}']

def test_input_vars_azure():
    config = create_test_config(
        namespace="nebari-ns",
        domain="my-test-domain.com",
        escaped_project_name="testprojectname",
        project_name="testproject",
        provider="azure"
    )
    sut = MlflowStage(output_directory = None, config = config)

    stage_outputs = get_stage_outputs_azure_gcp()
    result = sut.input_vars(stage_outputs)

    assert result["enabled"] == True
    assert result["namespace"] == "nebari-ns"
    assert result["external_url"] == "my-test-domain.com"

def test_input_vars_gcp():
    config = create_test_config(
        namespace="nebari-ns",
        domain="my-test-domain.com",
        escaped_project_name="testprojectname",
        project_name="testproject",
        provider="gcp"
    )
    sut = MlflowStage(output_directory = None, config = config)

    stage_outputs = get_stage_outputs_azure_gcp()
    result = sut.input_vars(stage_outputs)

    assert result["enabled"] == True
    assert result["namespace"] == "nebari-ns"
    assert result["external_url"] == "my-test-domain.com"
    assert result["bucket_name"] == "testproject-mlflow-artifacts"

def test_chart_overrides_aws():
    config = create_test_config(
        namespace="nebari-ns",
        domain="my-test-domain.com",
        escaped_project_name="testprojectname",
        project_name="testproject",
        provider="aws",
        mlflow=MlflowProvidersInputSchema(overrides={"foo": "bar"})
    )
    sut = MlflowStage(output_directory = None, config = config)

    stage_outputs = get_stage_outputs_aws()
    result = sut.input_vars(stage_outputs)
    assert result["overrides"] == ['{"foo": "bar"}']

def test_s3_encryption_config():
    config = create_test_config(
        namespace="nebari-ns",
        domain="my-test-domain.com",
        escaped_project_name="testprojectname",
        project_name="testproject",
        provider="aws",
        mlflow=MlflowProvidersInputSchema(aws=MlflowConfigAWS(enable_s3_encryption=False))
    )
    sut = MlflowStage(output_directory = None, config = config)

    stage_outputs = get_stage_outputs_aws()
    result = sut.input_vars(stage_outputs)
    assert result["enable_s3_encryption"] == False

def get_stage_outputs_aws():
    return {
        "stages/02-infrastructure": {
            "cluster_oidc_issuer_url": {
                "value": "https://test-oidc-url.com"
            }
        },
        "stages/04-kubernetes-ingress": {
            "domain": "my-test-domain.com"
        },
        "stages/07-kubernetes-services": {
            "forward-auth-service": {
                "value": {
                    "name": "forwardauth-service"
                }
            },
            "forward-auth-middleware": {
                "value": {
                    "name": "forwardauth-middleware"
                }
            }
        }
    }

def get_stage_outputs_azure_gcp():
    return {
        "stages/02-infrastructure": {
            "cluster_oidc_issuer_url": {
                "value": "https://test-oidc-url.com"
            },
            "resource_group_name": {
                "value": "test-rg"
            },
            "project_id": {
                "value": "test-project-123"
            }
        },
        "stages/04-kubernetes-ingress": {
            "domain": "my-test-domain.com"
        },
        "stages/07-kubernetes-services": {
            "forward-auth-service": {
                "value": {
                    "name": "forwardauth-service"
                }
            },
            "forward-auth-middleware": {
                "value": {
                    "name": "forwardauth-middleware"
                }
            }
        }
    }
