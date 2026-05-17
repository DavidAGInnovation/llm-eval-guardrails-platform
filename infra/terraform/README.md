# Terraform Starter (AWS ECS)

This folder provides a minimal ECS cluster/log-group baseline for deploying the API and worker.

## Usage

```bash
terraform init
terraform plan
terraform apply
```

Extend this with:
- ECS task definitions for API + worker
- ECS services
- RDS Postgres
- ElastiCache Redis
- IAM roles and secrets from AWS Secrets Manager
