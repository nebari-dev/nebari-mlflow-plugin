output "config" {
  description = "configuration credentials for connecting to openid client"
  value = {
    client_id     = keycloak_openid_client.this.client_id
    client_secret = keycloak_openid_client.this.client_secret
    signing_key   = local.signing_key

    issuer_url    = "${local.external_url}realms/${local.realm_id}"
    discovery_url = "${local.external_url}realms/${local.realm_id}/.well-known/openid-configuration"
    auth_url      = "${local.external_url}realms/${local.realm_id}/protocol/openid-connect/auth"
    token_url     = "${local.external_url}realms/${local.realm_id}/protocol/openid-connect/token"
    jwks_url      = "${local.external_url}realms/${local.realm_id}/protocol/openid-connect/certs"
    logout_url    = "${local.external_url}realms/${local.realm_id}/protocol/openid-connect/logout"
    userinfo_url  = "${local.external_url}realms/${local.realm_id}/protocol/openid-connect/userinfo"
  }
  sensitive = true
}