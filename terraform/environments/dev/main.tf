terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
  }

  # Uncomment to use S3 backend for dev state:
  # backend "s3" {
  #   bucket         = "my-terraform-state"
  #   key            = "monitoring-platform/dev/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

module "platform" {
  source = "../../"

  project_name           = var.project_name
  environment            = var.environment
  aws_region             = var.aws_region
  vpc_cidr               = var.vpc_cidr
  eks_node_instance_type = var.eks_node_instance_type
  enable_ai_remediation  = var.enable_ai_remediation
  alert_email            = var.alert_email
}
