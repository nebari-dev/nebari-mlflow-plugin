variable "enabled" {
  type = bool
  description = "Whether to deploy MLflow locally"
}

variable "namespace" {
  type = string
}

variable "helm-release-name" {
  type    = string
}

variable "external_url" {
  description = "External url for keycloak auth endpoint"
  type        = string
}

variable "forwardauth-service-name" {
  type = string
}

variable "forwardauth-middleware-name" {
  type = string
}

variable "minio_root_password" {
  description = "MinIO root password for artifact storage"
  type        = string
  sensitive   = true
}

variable "overrides" {
  type        = list(string)
  default     = []
  description = "Helm chart value overrides"
}
