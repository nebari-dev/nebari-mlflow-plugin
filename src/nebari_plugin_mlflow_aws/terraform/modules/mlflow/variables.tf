variable "ingress_host" {
  description = "DNS name for Traefik host"
  type        = string
}

# TODO - generalize for multi-cloud
variable "s3_bucket_name" {
  description = "Name of S3 bucket for MLFlow artifacts"
  type        = string
}

variable "keycloak_config" {
  description = "Keycloak configuration settings"
  type        = map(string)
}