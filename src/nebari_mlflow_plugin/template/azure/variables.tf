variable "enabled" {
  type = bool
  description = "Whether to deploy MLflow on Azure"
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
  description = "The URL on the AKS cluster for the OpenID Connect identity provider"
  type        = string
}

variable "storage_resource_group_name" {
  type = string
}

variable "storage_account_name" {
  type = string
}

variable "region" {
  type = string
}

variable "overrides" {
  type    = any
  default = {}
  description = "Helm chart value overrides"
}
