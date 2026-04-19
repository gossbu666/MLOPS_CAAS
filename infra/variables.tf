# ============================================================
#  CAAS — Terraform Input Variables
# ============================================================

variable "aws_region" {
  description = "AWS region to deploy CAAS resources"
  type        = string
  default     = "ap-southeast-1"   # Singapore — closest to Chiang Mai
}

variable "project_name" {
  description = "Project identifier used in all resource names and tags"
  type        = string
  default     = "caas"
}

variable "environment" {
  description = "Deployment environment (dev / staging / prod)"
  type        = string
  default     = "prod"
}

variable "s3_bucket_name" {
  description = "Globally unique S3 bucket name for CAAS data and models"
  type        = string
  default     = "caas-mlops-st126055"
}

variable "ec2_instance_type" {
  description = "EC2 instance type for FastAPI + Streamlit + MLflow colocated server"
  type        = string
  default     = "t3.small"   # 2 vCPU, 2 GB RAM — headroom for FastAPI + Streamlit + MLflow
}

variable "ec2_ami_id" {
  description = "Ubuntu 22.04 LTS AMI ID (ap-southeast-1)"
  type        = string
  default     = "ami-0df7a207adb9748c7"   # Ubuntu 22.04 LTS, ap-southeast-1
}

variable "ssh_key_name" {
  description = "Name of the EC2 key pair for SSH access"
  type        = string
  default     = "caas-key"
}

variable "allowed_ssh_cidr" {
  description = "CIDR block allowed to SSH into EC2 (restrict to your IP in production)"
  type        = string
  default     = "0.0.0.0/0"   # Open for demo — restrict in real deployment
}

variable "api_port" {
  description = "Port the FastAPI server listens on (container + host)"
  type        = number
  default     = 8000
}

variable "dashboard_port" {
  description = "External port for the Streamlit dashboard (container 8501 → host 8502)"
  type        = number
  default     = 8502
}

variable "mlflow_port" {
  description = "External port for MLflow tracking UI (container 5000 → host 5001, avoids macOS AirPlay)"
  type        = number
  default     = 5001
}
