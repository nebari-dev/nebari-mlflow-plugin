locals {
  mlflow_sa_name = "${var.chart_name}-sa"
}

# --------------------------------------------------------------------------
# Create Storage
# --------------------------------------------------------------------------

# Ensure bucket name uniqueness with random ID
resource "random_id" "bucket_name_suffix" {
  byte_length = 2
  keepers     = {}
}

resource "aws_s3_bucket" "artifact_storage" {
  bucket = "${var.project_name}-mlflow-artifacts-${random_id.bucket_name_suffix.hex}"
  acl    = "private"

  versioning {
    enabled = true
  }
}

# If enable_s3_encryption is true, create a key and apply Server Side Encryption to S3 bucket
resource "aws_kms_key" "mlflow_kms_key" {
  count                   = var.enable_s3_encryption ? 1 : 0
  description             = "This key is used to encrypt bucket objects for the AWS MLflow extension"
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
# Create IAM Resources for IRSA
# --------------------------------------------------------------------------

module "iam_assumable_role_admin" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-assumable-role-with-oidc"
  version = "~> 4.0"

  create_role                   = true
  role_name                     = "${var.project_name}-mlflow-irsa"
  provider_url                  = replace(var.cluster_oidc_issuer_url, "https://", "")
  role_policy_arns              = [aws_iam_policy.mlflow_s3.arn]
  oidc_fully_qualified_subjects = ["system:serviceaccount:${var.namespace}:${local.mlflow_sa_name}"]
}


# Create IAM Policy for full access to S3 and attach to EKS node IAM Role

resource "aws_iam_policy" "mlflow_s3" {
  name_prefix = "${var.project_name}-s3-mlflow-bucket-access"
  description = "Grants workloads full access to S3 bucket for MLflow artifact storage"
  policy      = <<EOT
{
  "Version": "2012-10-17",
  "Statement": [
        {
            "Sid": "ListAllBuckets",
            "Effect": "Allow",
            "Action": "s3:ListAllMyBuckets",
            "Resource": "*"
        },
        {
            "Sid": "ListObjectsInBucket",
            "Effect": "Allow",
            "Action": "s3:ListBucket",
            "Resource": "${aws_s3_bucket.artifact_storage.arn}"
        },
        {
            "Sid": "AllObjectActions",
            "Effect": "Allow",
            "Action": "s3:*Object",
            "Resource": "${aws_s3_bucket.artifact_storage.arn}/*"
        }
    ]
}

  EOT
}

module "keycloak" {
  source = "./modules/keycloak"

  realm_id            = var.realm_id
  client_id           = var.client_id
  base_url            = var.base_url
  external_url        = var.external_url
  valid_redirect_uris = var.valid_redirect_uris
  signing_key_ref     = var.signing_key_ref
}

module "mlflow" {
  source = "./modules/mlflow"

  chart_name             = var.chart_name
  create_namespace       = var.create_namespace
  ingress_host           = var.ingress_host
  mlflow_sa_name         = local.mlflow_sa_name
  mlflow_sa_iam_role_arn = module.iam_assumable_role_admin.iam_role_arn
  namespace              = var.namespace
  s3_bucket_name         = aws_s3_bucket.artifact_storage.id
  keycloak_config        = module.keycloak.config
  overrides              = var.overrides
}