output "rds_endpoint" {
  description = "Connection endpoint (host:port) for the RDS PostgreSQL instance"
  value       = aws_db_instance.main.endpoint
  sensitive   = true
}

output "rds_port" {
  description = "Port number of the RDS instance"
  value       = aws_db_instance.main.port
}

output "rds_secret_arn" {
  description = "ARN of the Secrets Manager secret that stores the RDS master password"
  value       = aws_secretsmanager_secret.rds_master.arn
}

output "db_name" {
  description = "Name of the default database"
  value       = aws_db_instance.main.db_name
}

output "rds_instance_id" {
  description = "Identifier of the RDS DB instance"
  value       = aws_db_instance.main.identifier
}

output "rds_security_group_id" {
  description = "Security group ID attached to the RDS instance"
  value       = aws_security_group.rds.id
}
