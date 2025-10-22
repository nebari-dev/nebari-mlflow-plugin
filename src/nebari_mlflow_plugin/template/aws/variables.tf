variable "enabled" {
  type        = bool
  description = "Whether to deploy MLflow on AWS"
}

variable "namespace" {
  type        = string
  description = "Kubernetes namespace for MLflow deployment"
}

variable "helm-release-name" {
  type        = string
  description = "Name for the Helm release"
}

variable "external_url" {
  description = "External URL for accessing MLflow"
  type        = string
}

variable "forwardauth-service-name" {
  type        = string
  description = "Name of the forward auth service for authentication"
}

variable "forwardauth-middleware-name" {
  type        = string
  description = "Name of the forward auth middleware for authentication"
}

variable "cluster_oidc_issuer_url" {
  description = "The URL on the EKS cluster for the OpenID Connect identity provider"
  type        = string
}

variable "project_name" {
  description = "Project name to assign to Nebari resources"
  type        = string
}

variable "region" {
  description = "AWS region for S3 bucket"
  type        = string
}

variable "enable_s3_encryption" {
  type        = bool
  default     = true
  description = "Enable KMS encryption for S3 bucket"
}

variable "overrides" {
  type        = list(string)
  default     = []
  description = "Helm chart value overrides"
}
