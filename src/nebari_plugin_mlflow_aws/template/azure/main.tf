provider "azurerm" {
  features {}
}

locals {
  mlflow-sa-name = "nebari-mlflow"
}

resource "helm_release" "mlflow" {
  name       = var.helm-release-name
  namespace  = var.namespace
  repository = "https://charts.bitnami.com/bitnami"
  chart      = "mlflow"
  version    = "1.0.5"

  values = concat([
    file("${path.module}/values.yaml"),

    jsonencode({
      "namespaceOverride" = "dev",
      "image" = {
        "repository" = "balast/mlflow",  # TODO: Change this to Quansight or Nebari image
        "tag"        = "2.12.1-debian-12-r0-azure"
      },
      "tracking" = {
        "auth" = {
          "enabled" = false  # TODO: enable this using forwardauth
        },
        "extraArgs" = ["--artifacts-destination", "wasbs://${azurerm_storage_container.mlflow.name}@${azurerm_storage_account.mlflow.name}.blob.core.windows.net/"]
        "podLabels" = {
          "azure.workload.identity/use" = "true"
        },
        "serviceAccount" = {
          "create" = true,
          "name"   = local.mlflow-sa-name
          "annotations" = {
            "azure.workload.identity/client-id" = resource.azurerm_user_assigned_identity.mlflow.client_id
          }

        }
      },
      "minio" = {
        "enabled" = false
      }
    })
  ], 
  # var.overrides
  )
}

# # Auth / Forward Auth
# module "keycloak" {
#   source = "../07-kubernetes-services/modules/kubernetes/services/keycloak-client"

#   realm_id            = var.realm_id
#   client_id           = var.client_id
#   # base_url            = var.base_url
#   external-url        = var.external_url
#   callback-url-paths  = var.valid_redirect_uris
#   # signing_key_ref     = var.signing_key_ref
# }

locals {
  mlflow-prefix = "mlflow"
}

# Blob Storage =====================================================================

resource "azurerm_storage_account" "mlflow" {
  name                     = var.storage_account_name
  resource_group_name      = var.storage_resource_group_name
  location                 = var.region
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_container" "mlflow" {
  name                  = "nebari-mlflow"
  storage_account_name  = azurerm_storage_account.mlflow.name
  container_access_type = "private"
}

# managed identity 
resource "azurerm_user_assigned_identity" "mlflow" {
  resource_group_name = var.storage_resource_group_name
  location            = var.region
  name                = "mlflow-storage-identity"

}

resource "azurerm_role_assignment" "mlflow" {
  scope                = azurerm_storage_container.mlflow.resource_manager_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.mlflow.principal_id
}

# federated credential on the managed identity
resource "azurerm_federated_identity_credential" "mlflow" {
  name                = "nebari-mlflow-federated-credential"
  resource_group_name = var.storage_resource_group_name
  audience            = ["api://AzureADTokenExchange"]
  issuer              = var.cluster_oidc_issuer_url
  parent_id           = azurerm_user_assigned_identity.mlflow.id
  subject             = "system:serviceaccount:${var.namespace}:${local.mlflow-sa-name}"

  depends_on = [ helm_release.mlflow ]
}


# Routing =====================================================================
resource "kubernetes_manifest" "mlflow-middleware-stripprefix" {
  manifest = {
    apiVersion = "traefik.containo.us/v1alpha1"
    kind       = "Middleware"
    metadata = {
      name      = "nebari-mlflow-stripprefix"
      namespace = var.namespace
    }
    spec = {
      stripPrefix = {
        prefixes = [
          "/${local.mlflow-prefix}/"
        ]
        forceSlash = false
      }
    }
  }
}

resource "kubernetes_manifest" "mlflow-add-slash" {
  manifest = {
    apiVersion = "traefik.containo.us/v1alpha1"
    kind       = "Middleware"
    metadata = {
      name      = "nebari-mlflow-add-slash"
      namespace = var.namespace
    }
    spec = {
      redirectRegex = {
        regex       = "^https://${var.external_url}/${local.mlflow-prefix}$"
        replacement = "https://${var.external_url}/${local.mlflow-prefix}/"
        permanent   = true
      }
    }
  }
}


resource "kubernetes_manifest" "mlflow-svc" {
  manifest = {
    "apiVersion" = "v1"
    "kind"       = "Service"
    "metadata" = {
      "name"      = "mlflow-svc"
      "namespace" = var.namespace
    }
    "spec" = {
      "ports" = [
        {
          "name"       = "mlflow-uis-port"
          "port"       = 5000
          "targetPort" = 5000
        },
      ]
      "selector" = {
        "app.kubernetes.io/component" = "tracking"
        "app.kubernetes.io/instance" = var.helm-release-name
      }
    }
  }
}

resource "kubernetes_manifest" "mlflow-ingressroute" {
  manifest = {
    apiVersion = "traefik.containo.us/v1alpha1"
    kind       = "IngressRoute"
    metadata = {
      name      = "mlflow-ingressroute"
      namespace = var.namespace
    }
    spec = {
      entryPoints = ["websecure"]
      routes = [
        {
          kind  = "Rule"
          match = "Host(`${var.external_url}`) && PathPrefix(`/${local.mlflow-prefix}`)"

          middlewares = [
            {
              name      = var.forwardauth-middleware-name
              namespace = var.namespace
            },            

            {
              name      = kubernetes_manifest.mlflow-add-slash.manifest.metadata.name
              namespace = var.namespace
            },
            {
              name      = kubernetes_manifest.mlflow-middleware-stripprefix.manifest.metadata.name
              namespace = var.namespace
            },
          ]

          services = [
            {
              name = kubernetes_manifest.mlflow-svc.manifest.metadata.name
              port = 5000
            }
          ]
        }
      ]
    }
  }
}
