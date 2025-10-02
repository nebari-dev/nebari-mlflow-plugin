output "minio_endpoint" {
  description = "MinIO endpoint for MLflow artifacts"
  value       = var.enabled ? "${var.helm-release-name}-minio:9000" : null
}
