locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }

  name_prefix = "${var.project_name}-${var.environment}"
}

# ---------------------------------------------------------------------------
# VPC Module
# ---------------------------------------------------------------------------
module "vpc" {
  source = "./modules/vpc"

  vpc_cidr     = var.vpc_cidr
  project_name = var.project_name
  environment  = var.environment
  azs          = ["${var.aws_region}a", "${var.aws_region}b"]
}

# ---------------------------------------------------------------------------
# IAM Module
# ---------------------------------------------------------------------------
data "aws_caller_identity" "current" {}

module "iam" {
  source = "./modules/iam"

  project_name            = var.project_name
  environment             = var.environment
  aws_region              = var.aws_region
  aws_account_id          = data.aws_caller_identity.current.account_id
  oidc_provider_arn       = module.eks.oidc_provider_arn
  cluster_oidc_issuer_url = module.eks.cluster_oidc_issuer_url

  depends_on = [module.eks]
}

# ---------------------------------------------------------------------------
# EKS Module
# ---------------------------------------------------------------------------
module "eks" {
  source = "./modules/eks"

  cluster_name       = "${local.name_prefix}-eks"
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  node_instance_type = var.eks_node_instance_type
  node_desired_count = var.eks_node_desired_count
  node_min_count     = var.eks_node_min_count
  node_max_count     = var.eks_node_max_count
  environment        = var.environment
  project_name       = var.project_name

  depends_on = [module.vpc]
}

# ---------------------------------------------------------------------------
# CloudWatch / Alerting Module
# ---------------------------------------------------------------------------
module "cloudwatch" {
  source = "./modules/cloudwatch"

  project_name   = var.project_name
  environment    = var.environment
  alert_email    = var.alert_email
  sns_topic_name = "${local.name_prefix}-alerts"
}

# ---------------------------------------------------------------------------
# RDS Module
# ---------------------------------------------------------------------------
module "rds" {
  source = "./modules/rds"

  project_name       = var.project_name
  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  vpc_cidr           = module.vpc.vpc_cidr_block
  multi_az           = var.environment == "prod" ? true : false
  instance_class     = var.environment == "prod" ? "db.t3.small" : "db.t3.micro"

  depends_on = [module.vpc]
}

# ---------------------------------------------------------------------------
# Lambda Module
# ---------------------------------------------------------------------------
module "lambda" {
  source = "./modules/lambda"

  project_name           = var.project_name
  environment            = var.environment
  vpc_id                 = module.vpc.vpc_id
  private_subnet_ids     = module.vpc.private_subnet_ids
  anomaly_detector_url   = "https://anomaly-detector.${local.name_prefix}.internal"
  remediation_engine_url = "https://remediation.${local.name_prefix}.internal"
  rds_endpoint           = module.rds.rds_endpoint
  sns_alert_topic_arn    = module.cloudwatch.sns_topic_arn

  depends_on = [module.vpc, module.cloudwatch, module.rds]

  # enable_ai_remediation gates whether Lambda functions are created.
  # Passed through to the lambda module so dev/staging can disable real actions.
  count = var.enable_ai_remediation ? 1 : 0
}
