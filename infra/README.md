# CAAS — Infrastructure as Code (Terraform)

Provisions all AWS resources needed to run CAAS in production.

## Resources Created

| Resource | Type | Purpose |
|----------|------|---------|
| `caas-mlops-bucket` | S3 Bucket | Data lake — raw, processed, models, results |
| `caas-ec2-role` | IAM Role | Lets EC2 access S3 without hardcoded keys |
| `caas-api-sg` | Security Group | Firewall — opens port 8000 (API), 5000 (MLflow), 22 (SSH) |
| `caas-api-server` | EC2 t3.small | Runs FastAPI + Docker, bootstraps from S3 on start |

## Prerequisites

1. [Install Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
2. [Configure AWS credentials](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
   ```bash
   aws configure   # enter Access Key ID + Secret + region ap-southeast-1
   ```
3. Create an EC2 key pair in the AWS console → save as `caas-key.pem`

## Usage

```bash
cd infra/

# 1. Download provider plugins
terraform init

# 2. Preview what will be created (no changes yet)
terraform plan

# 3. Create all resources (~3 min)
terraform apply

# 4. Copy outputs to GitHub Secrets:
#    EC2_HOST       → Outputs: ec2_public_ip
#    S3_BUCKET_NAME → Outputs: s3_bucket_name
#    AWS_REGION     → ap-southeast-1

# 5. Tear down when done (saves cost)
terraform destroy
```

## Estimated Cost

| Resource | Cost |
|----------|------|
| EC2 t3.small | ~$0.023/hr → ~$0.55/day |
| S3 (5 GB) | ~$0.115/month → ~$0.004/day |
| Data transfer | First 100 GB free |
| **Total** | **~$0.55/day** |

> Tip: Stop the EC2 instance when not presenting to avoid charges.
> `aws ec2 stop-instances --instance-ids <id>`

## After Apply — Upload Models to S3

```bash
# From project root
aws s3 sync 03_Data/models/     s3://caas-mlops-bucket/models/
aws s3 sync 03_Data/processed/  s3://caas-mlops-bucket/data/processed/
aws s3 sync 03_Data/results/    s3://caas-mlops-bucket/results/
```
