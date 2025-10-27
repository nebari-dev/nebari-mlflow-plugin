provider "aws" {
  region = var.region
}

locals {
  mlflow-sa-name = "nebari-mlflow"
  mlflow-prefix = "mlflow"
}

# --------------------------------------------------------------------------
# Create S3 Storage for Artifacts
# --------------------------------------------------------------------------

# Ensure bucket name uniqueness with random ID
resource "random_id" "bucket_name_suffix" {
  byte_length = 2
  keepers     = {}
}

resource "aws_s3_bucket" "artifact_storage" {
  bucket = "${var.project_name}-mlflow-artifacts-${random_id.bucket_name_suffix.hex}"
}

resource "aws_s3_bucket_ownership_controls" "artifact_storage" {
  bucket = aws_s3_bucket.artifact_storage.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "artifact_storage" {
  bucket = aws_s3_bucket.artifact_storage.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "artifact_storage" {
  bucket = aws_s3_bucket.artifact_storage.id
  versioning_configuration {
    status = "Enabled"
  }

  depends_on = [
    aws_s3_bucket_ownership_controls.artifact_storage,
    aws_s3_bucket_public_access_block.artifact_storage
  ]
}

# If enable_s3_encryption is true, create a key and apply Server Side Encryption to S3 bucket
resource "aws_kms_key" "mlflow_kms_key" {
  count       = var.enable_s3_encryption ? 1 : 0
  description = "This key is used to encrypt bucket objects for the AWS MLflow extension"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "mlflow_s3_encryption" {
  count  = var.enable_s3_encryption ? 1 : 0
  bucket = aws_s3_bucket.artifact_storage.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.mlflow_kms_key[0].arn
      sse_algorithm     = "aws:kms"
    }
  }
}

# --------------------------------------------------------------------------
# Create IAM Resources for IRSA (IAM Roles for Service Accounts)
# --------------------------------------------------------------------------

module "iam_assumable_role_admin" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-assumable-role-with-oidc"
  version = "~> 4.0"

  create_role                   = true
  role_name                     = "${var.project_name}-mlflow-irsa"
  provider_url                  = replace(var.cluster_oidc_issuer_url, "https://", "")
  role_policy_arns              = [aws_iam_policy.mlflow_s3.arn]
  oidc_fully_qualified_subjects = ["system:serviceaccount:${var.namespace}:${local.mlflow-sa-name}"]
}

# Create IAM Policy for S3 access
resource "aws_iam_policy" "mlflow_s3" {
  name_prefix = "${var.project_name}-s3-mlflow-bucket-access"
  description = "Grants workloads full access to S3 bucket for MLflow artifact storage"
  policy      = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListAllBuckets"
        Effect   = "Allow"
        Action   = "s3:ListAllMyBuckets"
        Resource = "*"
      },
      {
        Sid      = "ListObjectsInBucket"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.artifact_storage.arn
      },
      {
        Sid      = "AllObjectActions"
        Effect   = "Allow"
        Action   = "s3:*Object"
        Resource = "${aws_s3_bucket.artifact_storage.arn}/*"
      }
    ]
  })
}

# --------------------------------------------------------------------------
# Deploy MLflow using Bitnami Helm Chart
# --------------------------------------------------------------------------

resource "helm_release" "mlflow" {
  count      = var.enabled ? 1 : 0
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
        "serviceAccount" = {
          "create" = true,
          "name"   = local.mlflow-sa-name
          "annotations" = {
            "eks.amazonaws.com/role-arn" = module.iam_assumable_role_admin.iam_role_arn
          }
        }
      },
      "minio" = {
        "enabled" = false
      },
      "externalS3" = {
        "bucket" = aws_s3_bucket.artifact_storage.id
        "serveArtifacts" = true
      }
    })
  ],
  var.overrides
  )
}

# --------------------------------------------------------------------------
# Traefik Routing Configuration
# --------------------------------------------------------------------------

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
