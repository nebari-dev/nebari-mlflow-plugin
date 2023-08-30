locals {

  # TODO: temporary image while team determines where to publish.
  # Official mlflow image on GCR needs extending because it does not include packages
  # required for AWS artifacts (boto3) and PostGres (pyschopg2)
  image_name = "docker.io/kennethfoster/nebari-mlflow-aws"
  image_tag  = "latest"

}

resource "kubernetes_namespace" "this" {
  count = var.create_namespace ? 1 : 0

  metadata {
    name = var.namespace
  }
}

resource "random_password" "mlflow_postgres" {
  length  = 32
  special = false
}

resource "helm_release" "mlflow" {
  name      = var.chart_name
  chart     = "${path.module}/chart"
  namespace = var.create_namespace ? kubernetes_namespace.this[0].metadata[0].name : var.namespace

  values = [
    yamlencode({
      logLevel = "info"
      timeout  = "3600"
      ingress = {
        enabled = "true"
        host    = var.ingress_host
      }
      auth = {
        enabled = "true"
        secret = {
          data = {
            client_id     = var.keycloak_config["client_id"]
            client_secret = var.keycloak_config["client_secret"]
            signing_key   = var.keycloak_config["signing_key"]

            issuer_url    = var.keycloak_config["issuer_url"]
            discovery_url = var.keycloak_config["discovery_url"]
            auth_url      = var.keycloak_config["auth_url"]
            token_url     = var.keycloak_config["token_url"]
            jwks_url      = var.keycloak_config["jwks_url"]
            logout_url    = var.keycloak_config["logout_url"]
            userinfo_url  = var.keycloak_config["userinfo_url"]
          }
        }
      }
      image = {
        repository = local.image_name
        tag        = local.image_tag
      }
      serviceAccount = {
        name = var.mlflow_sa_name
        annotations = {
          "eks.amazonaws.com/role-arn" = var.mlflow_sa_iam_role_arn
        }
      }
      storage = {
        artifacts = {
          artifactsDestination = "s3://${var.s3_bucket_name}"
          proxyArtifacts       = "true"
        }
      }
      db = {
        dbName   = "mlflow_db"
        username = "mlflow_user"
        password = random_password.mlflow_postgres.result
      }
      env = [
        {
          name  = "MLFLOW_HTTP_REQUEST_TIMEOUT"
          value = "3600"
        }
      ]
    }),
    yamlencode(var.overrides),
  ]
}