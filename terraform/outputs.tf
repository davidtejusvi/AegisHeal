output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "eks_cluster_name" {
  description = "Name of the EKS cluster"
  value       = module.eks.cluster_id
}

output "eks_cluster_endpoint" {
  description = "API endpoint of the EKS cluster"
  value       = module.eks.cluster_endpoint
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = module.rds.rds_endpoint
  sensitive   = true
}

output "cloudwatch_dashboard_url" {
  description = "URL to the CloudWatch monitoring dashboard"
  value       = module.cloudwatch.dashboard_url
}

output "lambda_function_arns" {
  description = "ARNs of all deployed Lambda functions"
  value       = module.lambda.lambda_arns
}

output "oidc_provider_arn" {
  description = "ARN of the EKS OIDC provider"
  value       = module.eks.oidc_provider_arn
}

output "sns_topic_arn" {
  description = "ARN of the SNS alerts topic"
  value       = module.cloudwatch.sns_topic_arn
}

output "anomaly_detector_irsa_role_arn" {
  description = "ARN of the IRSA role for anomaly-detector"
  value       = module.iam.anomaly_detector_irsa_role_arn
}

output "remediation_engine_irsa_role_arn" {
  description = "ARN of the IRSA role for remediation-engine"
  value       = module.iam.remediation_engine_irsa_role_arn
}
