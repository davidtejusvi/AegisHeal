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
