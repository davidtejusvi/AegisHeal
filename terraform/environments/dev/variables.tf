variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "ai-monitoring-platform"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the dev VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "eks_node_instance_type" {
  description = "EC2 instance type for EKS worker nodes (smaller for dev cost savings)"
  type        = string
  default     = "t3.medium"
}

variable "enable_ai_remediation" {
  description = "Enable AI-based automated remediation"
  type        = bool
  default     = true
}

variable "alert_email" {
  description = "Email address for dev alert notifications"
  type        = string
  default     = "dev-alerts@example.com"
}

variable "eks_node_desired_count" {
  description = "Desired number of EKS worker nodes (dev)"
  type        = number
  default     = 2
}

variable "eks_node_min_count" {
  description = "Minimum number of EKS worker nodes (dev)"
  type        = number
  default     = 1
}

variable "eks_node_max_count" {
  description = "Maximum number of EKS worker nodes (dev)"
  type        = number
  default     = 4
}
