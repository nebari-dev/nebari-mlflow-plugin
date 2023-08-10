resource "helm_release" "mlflow" {
  name  = "mlflow"
  chart = "${path.module}/chart"

  set {
    name  = "igress.enabled"
    value = "true"
  }
  set {
    name  = "igress.host"
    value = var.ingress_host
  }
  set {
    name  = "auth.enabled"
    value = "true"
  }
  set {
    name  = "env[0].name"
    value = "MLFLOW_HTTP_REQUEST_TIMEOUT"
  }
  set {
    name  = "env[0].value"
    value = "3600"
  }
  set {
    name  = "auth.enabled"
    value = "true"
  }
  set {
    name  = "logLevel"
    value = "info"
  }
  set {
    name  = "timeout"
    value = "3600"
  }

  # S3 storage
  # TODO - move the logic for setting storage path prefixes outside of Chart into Terraform to handle multiple clouds
  set {
    name  = "storage.artifactsDestination"
    value = "s3://${var.s3_bucket_name}"
  }

  set {
    name  = "storage.defaultArtifactRoot"
    value = "s3://${var.s3_bucket_name}"
  }

  dynamic "set" {
    for_each = var.keycloak_config
    content {
      name  = "auth.secret.data.${each.key}"
      value = each.value
    }
  }
}