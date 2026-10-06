variable "project_name" {
  description = "Name of the project used for resource naming and tagging"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "aws_account_id" {
  description = "AWS account ID used to scope IAM policy resource ARNs"
  type        = string
  default     = "123456789012"
}

variable "aws_region" {
  description = "AWS region used to scope IAM policy resource ARNs"
  type        = string
  default     = "us-east-1"
}

variable "oidc_provider_arn" {
  description = "ARN of the EKS OIDC provider (for IRSA trust policies)"
  type        = string
  default     = ""
}

variable "cluster_oidc_issuer_url" {
  description = "OIDC issuer URL of the EKS cluster (without https://, used as condition variable)"
  type        = string
  default     = ""
}
