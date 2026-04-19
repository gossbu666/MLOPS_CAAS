# ============================================================
#  CAAS — Terraform Outputs
#  Values shown after `terraform apply` — use these to configure
#  GitHub Secrets and .env files.
# ============================================================

output "s3_bucket_name" {
  description = "S3 bucket name — set as GitHub Secret S3_BUCKET_NAME"
  value       = aws_s3_bucket.caas_data.bucket
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.caas_data.arn
}

output "ec2_public_ip" {
  description = "EC2 public IP — set as GitHub Secret EC2_HOST"
  value       = aws_instance.caas_api.public_ip
}

output "ec2_public_dns" {
  description = "EC2 public DNS"
  value       = aws_instance.caas_api.public_dns
}

output "api_url" {
  description = "FastAPI base URL"
  value       = "http://${aws_instance.caas_api.public_ip}:${var.api_port}"
}

output "dashboard_url" {
  description = "Streamlit public dashboard URL"
  value       = "http://${aws_instance.caas_api.public_ip}:${var.dashboard_port}"
}

output "mlflow_url" {
  description = "MLflow tracking UI URL"
  value       = "http://${aws_instance.caas_api.public_ip}:${var.mlflow_port}"
}

output "health_check_url" {
  description = "API health check endpoint"
  value       = "http://${aws_instance.caas_api.public_ip}:${var.api_port}/health"
}

output "iam_role_arn" {
  description = "IAM role ARN attached to EC2"
  value       = aws_iam_role.caas_ec2_role.arn
}

output "github_secrets_summary" {
  description = "Copy these values into GitHub Secrets after terraform apply"
  value = {
    EC2_HOST       = aws_instance.caas_api.public_ip
    S3_BUCKET_NAME = aws_s3_bucket.caas_data.bucket
    AWS_REGION     = var.aws_region
  }
}
