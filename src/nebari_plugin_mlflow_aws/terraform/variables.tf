# KEYCLOAK SETTINGS
# -----------------
variable "realm_id" {
  description = "Keycloak realm_id"
  type        = string
}

variable "client_id" {
  description = "OpenID Client ID"
  type        = string
}

variable "base_url" {
  description = "Default URL to use when the auth server needs to redirect or link back to the client"
  type        = string
}

variable "create_namespace" {
  type = bool
}

variable "external_url" {
  description = "External url for keycloak auth endpoint"
  type        = string
}

variable "valid_redirect_uris" {
  description = "A list of valid URIs a browser is permitted to redirect to after a successful login or logout"
  type        = list(string)
}

variable "signing_key_ref" {
  description = ""
  type = object({
    name      = string
    kind      = string # nebari uses an old terraform version, can't use optional
    namespace = string
  })
  default = null
}

# MLFLOW SETTINGS
# -----------------
variable "ingress_host" {
  description = "DNS name for Traefik host"
  type        = string
}

variable "chart_name" {
  description = "Name for mlflow chart and its namespaced resources."
  type        = string
}

variable "project_name" {
  description = "Project name to assign to Nebari resources"
  type        = string
}

variable "namespace" {
  type = string
}

variable "enable_s3_encryption" {
  type = bool
  default = true
}

variable "overrides" {
  type    = any
  default = {}
}

# IRSA SETTINGS
# -----------------

variable "cluster_oidc_issuer_url" {
  description = "The URL on the EKS cluster for the OpenID Connect identity provider"
  type        = string
}