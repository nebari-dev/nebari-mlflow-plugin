provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  mlflow-sa-name = "nebari-mlflow"
}

resource "helm_release" "mlflow" {
  count = var.enabled ? 1 : 0
  name       = var.helm-release-name
  namespace  = var.namespace
  repository = "https://charts.bitnami.com/bitnami"
  chart      = "mlflow"
  version    = "5.1.17"

  values = concat([
    file("${path.module}/values.yaml"),

    jsonencode({
      "image" = {
        "registry"   = "docker.io",
        "repository" = "bitnamilegacy/mlflow",
        "tag"        = "3.3.2-debian-12-r0"
      },
      "run" = {
        enabled = false
      },
      "tracking" = {
        "auth" = {
          "enabled" = false
        },
        "podLabels" = {
          "gke.io/gke-workload-identity" = "true"
        },
        "serviceAccount" = {
          "create" = true,
          "name"   = local.mlflow-sa-name
          "annotations" = {
            "iam.gke.io/gcp-service-account" = google_service_account.mlflow[count.index].email
          }        
        },
        "service" = {
          "type" = "ClusterIP",
          "ports" = {
            "http" = 5000
          } 
        }
      },
      "minio" = {
        "enabled" = false
      },
      "externalGCS" = {
        "bucket" = google_storage_bucket.mlflow[count.index].name
        "googleCloudProject" = var.project_id
        "serveArtifacts" = true
      },
      postgresql = {
        # TODO: Remove hardcoded image values after Helm chart update
        # This is a workaround due to bitnami charts deprecation
        # See: https://github.com/bitnami/charts/issues/35164
        # See: https://github.com/nebari-dev/nebari/issues/3120
        image = {
          registry   = "docker.io"
          repository = "bitnamilegacy/postgresql"
          tag        = "16.6.0-debian-12-r2"
        }
      }
    waitContainer = {
      # TODO: Remove hardcoded image values after Helm chart update
      # This is a workaround due to bitnami charts deprecation
      # See: https://github.com/bitnami/charts/issues/35164
      # See: https://github.com/nebari-dev/nebari/issues/3120
      image = {
        registry = "docker.io"
        repository = "bitnamilegacy/os-shell"
        tag = "12-debian-12-r20"
      }
    }
    })
  ], 
  var.overrides
  )
}


locals {
  mlflow-prefix = "mlflow"
}

# Cloud Storage =====================================================================

resource "google_storage_bucket" "mlflow" {
  count = var.enabled ? 1 : 0

  name          = var.bucket_name
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }
}

# Service Account for Workload Identity
resource "google_service_account" "mlflow" {
  count = var.enabled ? 1 : 0

  account_id   = "mlflow-storage-sa"
  display_name = "MLflow Storage Service Account"
  description  = "Service account for MLflow to access Cloud Storage"
}

# IAM binding for Cloud Storage access
resource "google_storage_bucket_iam_binding" "mlflow" {
  count = var.enabled ? 1 : 0

  bucket = google_storage_bucket.mlflow[count.index].name
  role   = "roles/storage.objectAdmin"

  members = [
    "serviceAccount:${google_service_account.mlflow[count.index].email}",
  ]
}

# Workload Identity binding
resource "google_service_account_iam_binding" "workload_identity" {
  count = var.enabled ? 1 : 0

  service_account_id = google_service_account.mlflow[count.index].name
  role               = "roles/iam.workloadIdentityUser"

  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[${var.namespace}/${local.mlflow-sa-name}]",
  ]
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