output "bucket_name" {
  description = "Name of the GCS bucket created for MLflow artifacts"
  value       = var.enabled ? google_storage_bucket.mlflow[0].name : null
}

output "service_account_email" {
  description = "Email of the GCP service account created for MLflow"
  value       = var.enabled ? google_service_account.mlflow[0].email : null
}