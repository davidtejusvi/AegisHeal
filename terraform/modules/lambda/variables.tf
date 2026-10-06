variable "project_name" {
  description = "Name of the project used for resource naming and tagging"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC where Lambda functions will run"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for VPC-attached Lambda functions"
  type        = list(string)
}

variable "anomaly_detector_url" {
  description = "Endpoint URL of the anomaly detection service"
  type        = string
}

variable "remediation_engine_url" {
  description = "Endpoint URL of the automated remediation engine"
  type        = string
}

variable "rds_endpoint" {
  description = "Connection endpoint of the RDS instance for Lambda functions that need DB access"
  type        = string
}

variable "sns_alert_topic_arn" {
  description = "ARN of the SNS topic that receives alerting notifications"
  type        = string
}
