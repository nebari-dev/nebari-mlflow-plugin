variable "create_namespace" {
  type = bool
}

variable "ingress_host" {
  description = "DNS name for Traefik host"
  type        = string
}

variable "s3_bucket_name" {
  description = "Name of S3 bucket for MLFlow artifacts"
  type        = string
}

variable "keycloak_config" {
  description = "Keycloak configuration settings"
  type        = map(string)
}

variable "namespace" {
  type = string
}

variable "mlflow_sa_name" {
  description = "Name of K8S service account for MLflow workloads"
  type = string
}