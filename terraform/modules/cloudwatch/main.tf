locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

# ---------------------------------------------------------------------------
# SNS Topic + Email Subscription
# ---------------------------------------------------------------------------
resource "aws_sns_topic" "alerts" {
  name              = var.sns_topic_name
  kms_master_key_id = "alias/aws/sns"

  tags = {
    Name        = var.sns_topic_name
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ---------------------------------------------------------------------------
# CloudWatch Log Group for application logs
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "application" {
  name              = "/aws/application/${local.name_prefix}"
  retention_in_days = 90

  tags = {
    Name        = "${local.name_prefix}-application-logs"
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "anomaly_detector" {
  name              = "/aws/application/${local.name_prefix}/anomaly-detector"
  retention_in_days = 30

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "remediation_engine" {
  name              = "/aws/application/${local.name_prefix}/remediation-engine"
  retention_in_days = 30

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# Metric Alarms
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  alarm_name          = "${local.name_prefix}-cpu-utilization-high"
  alarm_description   = "Triggers when average EC2/EKS node CPU exceeds 80%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "memory_high" {
  alarm_name          = "${local.name_prefix}-memory-utilization-high"
  alarm_description   = "Triggers when memory utilization exceeds 85%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "MemoryUtilization"
  namespace           = "CWAgent"
  period              = 60
  statistic           = "Average"
  threshold           = 85
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "error_rate_high" {
  alarm_name          = "${local.name_prefix}-error-rate-high"
  alarm_description   = "Triggers when application error rate exceeds 5%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ErrorRate"
  namespace           = "${var.project_name}/Application"
  period              = 60
  statistic           = "Average"
  threshold           = 5
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "latency_p99_high" {
  alarm_name          = "${local.name_prefix}-latency-p99-high"
  alarm_description   = "Triggers when p99 latency exceeds 2000ms"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  extended_statistic  = "p99"
  metric_name         = "Latency"
  namespace           = "${var.project_name}/Application"
  period              = 60
  threshold           = 2000
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# Composite Alarm – fires when ANY individual alarm is in ALARM state
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_composite_alarm" "platform_health" {
  alarm_name        = "${local.name_prefix}-platform-health"
  alarm_description = "Composite alarm: platform is degraded when any component alarm triggers"

  alarm_rule = join(" OR ", [
    "ALARM(${aws_cloudwatch_metric_alarm.cpu_high.alarm_name})",
    "ALARM(${aws_cloudwatch_metric_alarm.memory_high.alarm_name})",
    "ALARM(${aws_cloudwatch_metric_alarm.error_rate_high.alarm_name})",
    "ALARM(${aws_cloudwatch_metric_alarm.latency_p99_high.alarm_name})",
  ])

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# CloudWatch Dashboard
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.name_prefix}-overview"

  dashboard_body = jsonencode({
    widgets = [
      # Row 1 – CPU Utilization
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "CPU Utilization (%)"
          view   = "timeSeries"
          stacked = false
          region = "us-east-1"
          metrics = [
            ["AWS/EC2", "CPUUtilization", { "stat" = "Average", "period" = 60, "label" = "EC2 CPU Avg" }],
            ["AWS/EC2", "CPUUtilization", { "stat" = "Maximum", "period" = 60, "label" = "EC2 CPU Max" }],
          ]
          annotations = {
            horizontal = [{ value = 80, color = "#ff0000", label = "CPU 80% threshold" }]
          }
        }
      },
      # Row 1 – Memory Utilization
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Memory Utilization (%)"
          view   = "timeSeries"
          stacked = false
          region = "us-east-1"
          metrics = [
            ["CWAgent", "MemoryUtilization", { "stat" = "Average", "period" = 60, "label" = "Memory Avg" }],
            ["CWAgent", "MemoryUtilization", { "stat" = "Maximum", "period" = 60, "label" = "Memory Max" }],
          ]
          annotations = {
            horizontal = [{ value = 85, color = "#ff0000", label = "Memory 85% threshold" }]
          }
        }
      },
      # Row 2 – Error Rate
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Application Error Rate (%)"
          view   = "timeSeries"
          stacked = false
          region = "us-east-1"
          metrics = [
            ["${var.project_name}/Application", "ErrorRate", { "stat" = "Average", "period" = 60, "label" = "Error Rate" }],
          ]
          annotations = {
            horizontal = [{ value = 5, color = "#ff0000", label = "Error Rate 5% threshold" }]
          }
        }
      },
      # Row 2 – Latency
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Request Latency (ms)"
          view   = "timeSeries"
          stacked = false
          region = "us-east-1"
          metrics = [
            ["${var.project_name}/Application", "Latency", { "stat" = "p50", "period" = 60, "label" = "p50 Latency" }],
            ["${var.project_name}/Application", "Latency", { "stat" = "p99", "period" = 60, "label" = "p99 Latency" }],
          ]
          annotations = {
            horizontal = [{ value = 2000, color = "#ff0000", label = "p99 2000ms threshold" }]
          }
        }
      },
      # Row 3 – Alarm Status
      {
        type   = "alarm"
        x      = 0
        y      = 12
        width  = 24
        height = 4
        properties = {
          title = "Platform Alarm Status"
          alarms = [
            "arn:aws:cloudwatch:us-east-1::alarm:${local.name_prefix}-cpu-utilization-high",
            "arn:aws:cloudwatch:us-east-1::alarm:${local.name_prefix}-memory-utilization-high",
            "arn:aws:cloudwatch:us-east-1::alarm:${local.name_prefix}-error-rate-high",
            "arn:aws:cloudwatch:us-east-1::alarm:${local.name_prefix}-latency-p99-high",
          ]
        }
      },
    ]
  })
}
