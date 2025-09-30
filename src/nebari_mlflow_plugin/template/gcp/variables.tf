variable "enabled" {
  type = bool
  description = "Whether to deploy MLflow on GCP"
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

variable "cluster_oidc_issuer_url" {
  description = "The URL on the GKE cluster for the OpenID Connect identity provider"
  type        = string
}

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "bucket_name" {
  description = "GCS bucket name for MLflow artifacts"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "force_destroy_storage" {
  description = "Whether to destroy storage bucket when MLflow is disabled"
  type        = bool
  default     = false
}

variable "force_destroy_db_creds" {
  description = "Whether to destroy database credentials when MLflow is disabled"
  type        = bool
  default     = false
}