output "dashboard_url" {
  description = "URL of the CloudWatch dashboard in the AWS Console"
  value       = "https://console.aws.amazon.com/cloudwatch/home#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}

output "sns_topic_arn" {
  description = "ARN of the SNS alerts topic"
  value       = aws_sns_topic.alerts.arn
}

output "alarm_arns" {
  description = "Map of alarm name to alarm ARN"
  value = {
    cpu_high           = aws_cloudwatch_metric_alarm.cpu_high.arn
    memory_high        = aws_cloudwatch_metric_alarm.memory_high.arn
    error_rate_high    = aws_cloudwatch_metric_alarm.error_rate_high.arn
    latency_p99_high   = aws_cloudwatch_metric_alarm.latency_p99_high.arn
    platform_composite = aws_cloudwatch_composite_alarm.platform_health.arn
  }
}

output "application_log_group_name" {
  description = "Name of the CloudWatch log group for application logs"
  value       = aws_cloudwatch_log_group.application.name
}

output "dashboard_name" {
  description = "Name of the CloudWatch dashboard"
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}
