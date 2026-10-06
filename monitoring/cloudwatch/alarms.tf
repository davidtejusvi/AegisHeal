# ---------------------------------------------------------------------------
# Standalone additional CloudWatch alarms
# Run from monitoring/cloudwatch/ after the main platform is deployed.
# The SNS topic is referenced via a data source — no circular dependency.
# ---------------------------------------------------------------------------

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name (must match main platform deployment)"
  type        = string
  default     = "ai-monitoring-platform"
}

variable "environment" {
  description = "Environment (must match main platform deployment)"
  type        = string
  default     = "dev"
}

variable "eks_cluster_name" {
  description = "Name of the EKS cluster (used to scope CloudWatch dimensions)"
  type        = string
  default     = ""
}

variable "rds_instance_identifier" {
  description = "RDS DB instance identifier"
  type        = string
  default     = ""
}

locals {
  name_prefix      = "${var.project_name}-${var.environment}"
  sns_topic_name   = "${local.name_prefix}-alerts"
  eks_cluster_name = var.eks_cluster_name != "" ? var.eks_cluster_name : "${local.name_prefix}-eks"
  rds_id           = var.rds_instance_identifier != "" ? var.rds_instance_identifier : "${local.name_prefix}-postgres"
}

# ---------------------------------------------------------------------------
# Data source – existing SNS alerts topic created by the main module
# ---------------------------------------------------------------------------
data "aws_sns_topic" "alerts" {
  name = local.sns_topic_name
}

# ---------------------------------------------------------------------------
# EKS Node CPU High
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "eks_node_cpu_high" {
  alarm_name          = "${local.name_prefix}-eks-node-cpu-high"
  alarm_description   = "EKS node CPU utilization exceeds 80% for 3 consecutive minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "node_cpu_utilization"
  namespace           = "ContainerInsights"
  period              = 60
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = local.eks_cluster_name
  }

  alarm_actions = [data.aws_sns_topic.alerts.arn]
  ok_actions    = [data.aws_sns_topic.alerts.arn]

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# EKS Node Memory High
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "eks_node_memory_high" {
  alarm_name          = "${local.name_prefix}-eks-node-memory-high"
  alarm_description   = "EKS node memory utilization exceeds 85% for 3 consecutive minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "node_memory_utilization"
  namespace           = "ContainerInsights"
  period              = 60
  statistic           = "Average"
  threshold           = 85
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = local.eks_cluster_name
  }

  alarm_actions = [data.aws_sns_topic.alerts.arn]
  ok_actions    = [data.aws_sns_topic.alerts.arn]

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# RDS CPU High
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "rds_cpu_high" {
  alarm_name          = "${local.name_prefix}-rds-cpu-high"
  alarm_description   = "RDS CPU utilization exceeds 75% for 5 consecutive minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 75
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = local.rds_id
  }

  alarm_actions = [data.aws_sns_topic.alerts.arn]
  ok_actions    = [data.aws_sns_topic.alerts.arn]

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# RDS Free Storage Low
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "rds_storage_low" {
  alarm_name          = "${local.name_prefix}-rds-storage-low"
  alarm_description   = "RDS free storage drops below 5 GB"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 5368709120 # 5 GB in bytes
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = local.rds_id
  }

  alarm_actions = [data.aws_sns_topic.alerts.arn]

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# Lambda Error Rate High (across all platform functions)
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "lambda_error_rate_high" {
  alarm_name          = "${local.name_prefix}-lambda-error-rate-high"
  alarm_description   = "Lambda error rate exceeds 5% of invocations over 5 minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = 5
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "error_rate"
    expression  = "(errors / invocations) * 100"
    label       = "Lambda Error Rate (%)"
    return_data = true
  }

  metric_query {
    id = "errors"
    metric {
      metric_name = "Errors"
      namespace   = "AWS/Lambda"
      period      = 300
      stat        = "Sum"
      dimensions  = {}
    }
  }

  metric_query {
    id = "invocations"
    metric {
      metric_name = "Invocations"
      namespace   = "AWS/Lambda"
      period      = 300
      stat        = "Sum"
      dimensions  = {}
    }
  }

  alarm_actions = [data.aws_sns_topic.alerts.arn]
  ok_actions    = [data.aws_sns_topic.alerts.arn]

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# Lambda Duration High (metrics-collector)
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "lambda_duration_high" {
  alarm_name          = "${local.name_prefix}-lambda-duration-high"
  alarm_description   = "Lambda p99 duration exceeds 10s (approaching 15s limit)"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  extended_statistic  = "p99"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 60
  threshold           = 10000 # milliseconds
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = "${local.name_prefix}-metrics-collector"
  }

  alarm_actions = [data.aws_sns_topic.alerts.arn]
  ok_actions    = [data.aws_sns_topic.alerts.arn]

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# Lambda Throttles
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name          = "${local.name_prefix}-lambda-throttles"
  alarm_description   = "Lambda throttles exceed 10 in 5 minutes — consider raising concurrency limit"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  treat_missing_data  = "notBreaching"

  alarm_actions = [data.aws_sns_topic.alerts.arn]

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}
