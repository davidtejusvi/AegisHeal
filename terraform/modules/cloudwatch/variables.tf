variable "project_name" {
  description = "Name of the project used for resource naming and tagging"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "alert_email" {
  description = "Email address that will receive SNS alarm notifications"
  type        = string
}

variable "sns_topic_name" {
  description = "Name of the SNS topic created for platform alerts"
  type        = string
}
