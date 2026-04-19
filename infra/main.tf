# ============================================================
#  CAAS — Main Terraform Configuration
#  ChiangMai Air Quality Alert System — AWS Infrastructure
#
#  Resources:
#    - S3 bucket        : data storage (raw, processed, models, results)
#    - IAM role/policy  : EC2 → S3 access without hardcoded credentials
#    - Security Group   : firewall for EC2 (API + SSH + MLflow ports)
#    - EC2 instance     : runs FastAPI inference server (t3.micro)
#
#  Usage:
#    terraform init
#    terraform plan
#    terraform apply
#    terraform destroy   # tear down when done (saves cost)
# ============================================================

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Course      = "AT82.9002-DataEngineering-MLOps"
    }
  }
}

# ── Data: current account + region ─────────────────────────
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ============================================================
#  S3 BUCKET — Data Lake
# ============================================================

resource "aws_s3_bucket" "caas_data" {
  bucket        = var.s3_bucket_name
  force_destroy = true   # allow terraform destroy to empty bucket

  lifecycle {
    prevent_destroy = false
  }
}

resource "aws_s3_bucket_versioning" "caas_data" {
  bucket = aws_s3_bucket.caas_data.id
  versioning_configuration {
    status = "Enabled"   # keeps model version history
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "caas_data" {
  bucket = aws_s3_bucket.caas_data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "caas_data" {
  bucket                  = aws_s3_bucket.caas_data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Folder structure inside the bucket (created via empty placeholder objects)
resource "aws_s3_object" "folders" {
  for_each = toset([
    "data/raw/",
    "data/processed/",
    "data/features/",
    "models/",
    "results/",
    "results/drift_reports/",
    "mlflow/",
  ])
  bucket  = aws_s3_bucket.caas_data.id
  key     = each.value
  content = ""
}

# ============================================================
#  IAM — EC2 Role + Policy (S3 access without hardcoded keys)
# ============================================================

resource "aws_iam_role" "caas_ec2_role" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "caas_s3_access" {
  name = "${var.project_name}-s3-access"
  role = aws_iam_role.caas_ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
        ]
        Resource = [
          aws_s3_bucket.caas_data.arn,
          "${aws_s3_bucket.caas_data.arn}/*",
        ]
      },
      {
        # Allow EC2 to describe itself (useful for health scripts)
        Effect   = "Allow"
        Action   = ["ec2:DescribeInstances"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "caas_ec2_profile" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.caas_ec2_role.name
}

# ============================================================
#  SECURITY GROUP — EC2 Firewall
# ============================================================

resource "aws_security_group" "caas_api" {
  name        = "${var.project_name}-api-sg"
  description = "CAAS FastAPI server — allow API, MLflow, and SSH"

  # FastAPI port
  ingress {
    description = "FastAPI inference server"
    from_port   = var.api_port
    to_port     = var.api_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Streamlit dashboard port
  ingress {
    description = "Streamlit public dashboard"
    from_port   = var.dashboard_port
    to_port     = var.dashboard_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # MLflow UI port
  ingress {
    description = "MLflow tracking UI"
    from_port   = var.mlflow_port
    to_port     = var.mlflow_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # SSH access
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  # All outbound traffic allowed (for API calls to air4thai, Open-Meteo, FIRMS)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ============================================================
#  EC2 INSTANCE — FastAPI Server
# ============================================================

resource "aws_instance" "caas_api" {
  ami                    = var.ec2_ami_id
  instance_type          = var.ec2_instance_type
  key_name               = var.ssh_key_name
  iam_instance_profile   = aws_iam_instance_profile.caas_ec2_profile.name
  vpc_security_group_ids = [aws_security_group.caas_api.id]

  # Bootstrap script: install Docker + compose + pull repo + start 3-service stack
  user_data = base64encode(<<-EOF
    #!/bin/bash
    set -e
    exec > >(tee /var/log/caas-bootstrap.log) 2>&1

    # Base dependencies (awscli is needed to pull models/data from S3)
    apt-get update -y
    apt-get install -y git awscli ca-certificates curl

    # Install Docker Engine + compose plugin via official convenience script
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sh /tmp/get-docker.sh
    systemctl enable docker
    systemctl start docker

    # Clone the CAAS repo
    git clone https://github.com/gossbu666/MLOPS_CAAS.git /home/ubuntu/caas
    chown -R ubuntu:ubuntu /home/ubuntu/caas
    cd /home/ubuntu/caas

    # Sync data from S3 (fail-soft: bucket may be empty on first boot)
    aws s3 sync s3://${var.s3_bucket_name}/models/            03_Data/models/            --region ${var.aws_region} || true
    aws s3 sync s3://${var.s3_bucket_name}/data/processed/    03_Data/processed/         --region ${var.aws_region} || true
    aws s3 sync s3://${var.s3_bucket_name}/results/           03_Data/results/           --region ${var.aws_region} || true
    aws s3 sync s3://${var.s3_bucket_name}/mlflow/            mlruns/                    --region ${var.aws_region} || true

    # Build + start all 3 services (api, dashboard, mlflow)
    docker compose up --build -d

    echo "CAAS stack started — api:${var.api_port}  dashboard:${var.dashboard_port}  mlflow:${var.mlflow_port}"
  EOF
  )

  root_block_device {
    volume_size = 20   # GB — enough for models + data
    volume_type = "gp3"
  }

  tags = {
    Name = "${var.project_name}-api-server"
  }
}
