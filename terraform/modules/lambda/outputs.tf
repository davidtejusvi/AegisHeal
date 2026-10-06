output "lambda_arns" {
  description = "Map of Lambda function name to its ARN"
  value       = { for name, fn in aws_lambda_function.main : name => fn.arn }
}

output "lambda_role_arn" {
  description = "ARN of the shared Lambda execution IAM role"
  value       = aws_iam_role.lambda_execution.arn
}

output "lambda_function_names" {
  description = "Map of Lambda function name to its AWS function name"
  value       = { for name, fn in aws_lambda_function.main : name => fn.function_name }
}

output "lambda_security_group_id" {
  description = "Security group ID attached to VPC-bound Lambda functions"
  value       = aws_security_group.lambda.id
}

output "metrics_collector_schedule_arn" {
  description = "ARN of the EventBridge rule that triggers the metrics-collector"
  value       = aws_cloudwatch_event_rule.metrics_collector_schedule.arn
}
