output "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution IAM role"
  value       = aws_iam_role.lambda_execution.arn
}

output "eks_node_role_arn" {
  description = "ARN of the EKS node IAM role"
  value       = aws_iam_role.eks_node.arn
}

output "ssm_automation_role_arn" {
  description = "ARN of the SSM Automation IAM role"
  value       = aws_iam_role.ssm_automation.arn
}

output "cross_service_policy_arn" {
  description = "ARN of the cross-service access IAM policy"
  value       = aws_iam_policy.cross_service.arn
}

output "lambda_permissions_policy_arn" {
  description = "ARN of the Lambda custom permissions IAM policy"
  value       = aws_iam_policy.lambda_permissions.arn
}

output "anomaly_detector_irsa_role_arn" {
  description = "ARN of the IRSA role for anomaly-detector K8s ServiceAccount"
  value       = aws_iam_role.anomaly_detector_irsa.arn
}

output "remediation_engine_irsa_role_arn" {
  description = "ARN of the IRSA role for remediation-engine K8s ServiceAccount"
  value       = aws_iam_role.remediation_engine_irsa.arn
}
