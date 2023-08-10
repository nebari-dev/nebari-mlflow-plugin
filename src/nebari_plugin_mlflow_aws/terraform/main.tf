# --------------------------------------------------------------------------
# Create Storage and Associated IAM Updates
# --------------------------------------------------------------------------

# Ensure bucket name uniqueness with random ID
resource "random_id" "bucket_name_suffix" {
  byte_length = 2
  keepers     = {}
}

resource "aws_s3_bucket" "artifact_storage" {
  bucket = "nebari-mlflow-artifacts-${random_id.bucket_name_suffix.hex}"
  acl    = "private"

  versioning {
    enabled = true
  }
}

# Create IAM Policy for full access to S3 and attach to EKS node IAM Role

resource "aws_iam_policy" "mlflow_s3" {
  name_prefix = "s3-mlflow-bucket-access"
  description = "Grants workloads full access to S3 bucket for MLflow artifact storage"
  policy      = <<EOT
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": [
        "s3:ListAllMyBuckets"
      ],
      "Effect": "Allow",
      "Resource": "*"
    },
    {
      "Action": [
        "s3:*"
      ],
      "Effect": "Allow",
      "Resource": "${aws_s3_bucket.artifact_storage.arn}"
    }
  ]

}

  EOT
}

resource "aws_iam_role_policy_attachment" "node-group-policy" {
  policy_arn = aws_iam_policy.mlflow_s3.arn
  role       = var.node_group_iam_role_name
}

# --------------------------------------------------------------------------
# Modules shared by all clouds
# --------------------------------------------------------------------------

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

  ingress_host   = var.ingress_host
  s3_bucket_name = aws_s3_bucket.artifact_storage.id
  keycloak_config = module.keycloak.config
}