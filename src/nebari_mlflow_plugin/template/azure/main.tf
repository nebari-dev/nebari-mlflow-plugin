provider "azurerm" {
  features {}
}

locals {
  mlflow-sa-name = "nebari-mlflow"
}

resource "helm_release" "mlflow" {
  count = var.enabled ? 1 : 0
  name       = var.helm-release-name
  namespace  = var.namespace
  repository = "oci://registry-1.docker.io/bitnamicharts"
  chart      = "mlflow"
  version    = "5.1.17"

  values = concat([
    file("${path.module}/shared_helm_values.yaml"),
    file("${path.module}/values.yaml"),
    jsonencode({
      "tracking" = {
        "podLabels" = {
          "azure.workload.identity/use" = "true"
        },
        "serviceAccount" = {
          "create" = true,
          "name"   = local.mlflow-sa-name
          "annotations" = {
            "azure.workload.identity/client-id" = resource.azurerm_user_assigned_identity.mlflow[count.index].client_id
          }
        }
      },
      "minio" = {
        "enabled" = false
      },
      "externalAzureBlob" = {
        "storageAccount" = azurerm_storage_account.mlflow[count.index].name
        "containerName" = azurerm_storage_container.mlflow[count.index].name
        "serveArtifacts" = true
      }
    })
  ],
  var.overrides
  )
}


locals {
  mlflow-prefix = "mlflow"
}

# Blob Storage =====================================================================

resource "azurerm_storage_account" "mlflow" {
  count = var.enabled ? 1 : 0

  name                     = var.storage_account_name
  resource_group_name      = var.storage_resource_group_name
  location                 = var.region
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_container" "mlflow" {
  count = var.enabled ? 1 : 0

  name                  = "nebari-mlflow"
  storage_account_name  = azurerm_storage_account.mlflow[count.index].name
  container_access_type = "private"
}

# managed identity 
resource "azurerm_user_assigned_identity" "mlflow" {
  count = var.enabled ? 1 : 0

  resource_group_name = var.storage_resource_group_name
  location            = var.region
  name                = "mlflow-storage-identity"

}

resource "azurerm_role_assignment" "mlflow" {
  count = var.enabled ? 1 : 0

  scope                = azurerm_storage_container.mlflow[count.index].resource_manager_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.mlflow[count.index].principal_id
}

# federated credential on the managed identity
resource "azurerm_federated_identity_credential" "mlflow" {
  count = var.enabled ? 1 : 0

  name                = "nebari-mlflow-federated-credential"
  resource_group_name = var.storage_resource_group_name
  audience            = ["api://AzureADTokenExchange"]
  issuer              = var.cluster_oidc_issuer_url
  parent_id           = azurerm_user_assigned_identity.mlflow[count.index].id
  subject             = "system:serviceaccount:${var.namespace}:${local.mlflow-sa-name}"

  depends_on = [ helm_release.mlflow ]
}


# Routing =====================================================================
resource "kubernetes_manifest" "mlflow-middleware-stripprefix" {
  count = var.enabled ? 1 : 0
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
  count = var.enabled ? 1 : 0
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


resource "kubernetes_manifest" "mlflow-ingressroute" {
  count = var.enabled ? 1 : 0
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
              name      = kubernetes_manifest.mlflow-add-slash[count.index].manifest.metadata.name
              namespace = var.namespace
            },
            {
              name      = kubernetes_manifest.mlflow-middleware-stripprefix[count.index].manifest.metadata.name
              namespace = var.namespace
            },
          ]

          services = [
            {
              name = "${var.helm-release-name}-tracking"
              port = 5000
            }
          ]
        }
      ]
    }
  }
}
