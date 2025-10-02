locals {
  mlflow-prefix = "mlflow"
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
      "minio" = {
        "enabled" = true
        "image" = {
          "registry" = "docker.io"
          "repository" = "bitnamilegacy/minio"
          "tag" = "2025.7.23-debian-12-r3"
        }
        "auth" = {
          "rootUser" = "minio"
          "rootPassword" = var.minio_root_password
        }
        "defaultBuckets" = "mlflow"
        "defaultInitContainers" = {
          "volumePermissions" = {
            "image" = {
              "registry" = "docker.io"
              "repository" = "bitnamilegacy/os-shell"
              "tag" = "12-debian-12-r51"
            }
          }
        }
      }
    })
  ],
  var.overrides
  )
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
