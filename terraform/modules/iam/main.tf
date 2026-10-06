locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

# ---------------------------------------------------------------------------
# Lambda Execution Role
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_execution" {
  name               = "${local.name_prefix}-iam-lambda-role"
  description        = "Base IAM role for Lambda functions (used as reference by other modules)"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_vpc_access" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

data "aws_iam_policy_document" "lambda_permissions" {
  # CloudWatch Logs
  statement {
    sid    = "CloudWatchLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]
    resources = ["arn:aws:logs:${var.aws_region}:${var.aws_account_id}:*"]
  }

  # EC2 describe / start / stop
  statement {
    sid    = "EC2Management"
    effect = "Allow"
    actions = [
      "ec2:DescribeInstances",
      "ec2:DescribeInstanceStatus",
      "ec2:StartInstances",
      "ec2:StopInstances",
      "ec2:RebootInstances",
      "ec2:DescribeVpcs",
      "ec2:DescribeSubnets",
      "ec2:DescribeSecurityGroups",
      "ec2:CreateNetworkInterface",
      "ec2:DescribeNetworkInterfaces",
      "ec2:DeleteNetworkInterface",
    ]
    resources = ["*"]
  }

  # SSM
  statement {
    sid    = "SSMAccess"
    effect = "Allow"
    actions = [
      "ssm:SendCommand",
      "ssm:GetCommandInvocation",
      "ssm:ListCommandInvocations",
      "ssm:DescribeInstanceInformation",
      "ssm:StartAutomationExecution",
      "ssm:GetAutomationExecution",
      "ssm:GetParameter",
      "ssm:GetParameters",
    ]
    resources = ["*"]
  }

  # RDS
  statement {
    sid    = "RDSReadRestart"
    effect = "Allow"
    actions = [
      "rds:DescribeDBInstances",
      "rds:DescribeDBClusters",
      "rds:RebootDBInstance",
    ]
    resources = ["arn:aws:rds:${var.aws_region}:${var.aws_account_id}:db:*"]
  }

  # CloudWatch Metrics & Alarms
  statement {
    sid    = "CloudWatchMetrics"
    effect = "Allow"
    actions = [
      "cloudwatch:PutMetricData",
      "cloudwatch:GetMetricData",
      "cloudwatch:GetMetricStatistics",
      "cloudwatch:ListMetrics",
      "cloudwatch:DescribeAlarms",
      "cloudwatch:SetAlarmState",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "lambda_permissions" {
  name        = "${local.name_prefix}-lambda-permissions"
  description = "Custom permissions for Lambda functions: CloudWatch, EC2, SSM, RDS"
  policy      = data.aws_iam_policy_document.lambda_permissions.json

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "lambda_custom" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = aws_iam_policy.lambda_permissions.arn
}

# ---------------------------------------------------------------------------
# EKS Node Role
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "eks_node_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eks_node" {
  name               = "${local.name_prefix}-eks-node-role"
  description        = "IAM role for EKS managed node group workers"
  assume_role_policy = data.aws_iam_policy_document.eks_node_assume.json

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "eks_worker_node" {
  role       = aws_iam_role.eks_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "eks_cni" {
  role       = aws_iam_role.eks_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "eks_ecr_readonly" {
  role       = aws_iam_role.eks_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "eks_ssm" {
  role       = aws_iam_role.eks_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# ---------------------------------------------------------------------------
# SSM Automation Role
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "ssm_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ssm.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ssm_automation" {
  name               = "${local.name_prefix}-ssm-automation-role"
  description        = "Role used by SSM Automation documents for remediation tasks"
  assume_role_policy = data.aws_iam_policy_document.ssm_assume.json

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

data "aws_iam_policy_document" "ssm_automation_permissions" {
  statement {
    sid    = "EC2Actions"
    effect = "Allow"
    actions = [
      "ec2:StartInstances",
      "ec2:StopInstances",
      "ec2:RebootInstances",
      "ec2:DescribeInstances",
      "ec2:DescribeInstanceStatus",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "SSMActions"
    effect = "Allow"
    actions = [
      "ssm:SendCommand",
      "ssm:GetCommandInvocation",
      "ssm:ListCommandInvocations",
      "ssm:DescribeAutomationExecutions",
      "ssm:GetAutomationExecution",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "CloudWatchLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["arn:aws:logs:${var.aws_region}:${var.aws_account_id}:*"]
  }

  statement {
    sid    = "LambdaInvoke"
    effect = "Allow"
    actions = [
      "lambda:InvokeFunction",
    ]
    resources = ["arn:aws:lambda:${var.aws_region}:${var.aws_account_id}:function:${local.name_prefix}-*"]
  }

  statement {
    sid    = "IAMPassRole"
    effect = "Allow"
    actions = [
      "iam:PassRole",
    ]
    resources = ["arn:aws:iam::${var.aws_account_id}:role/${local.name_prefix}-*"]
  }
}

resource "aws_iam_policy" "ssm_automation" {
  name        = "${local.name_prefix}-ssm-automation-policy"
  description = "Permissions for SSM Automation to manage EC2, Lambda, and CloudWatch"
  policy      = data.aws_iam_policy_document.ssm_automation_permissions.json

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "ssm_automation" {
  role       = aws_iam_role.ssm_automation.name
  policy_arn = aws_iam_policy.ssm_automation.arn
}

# ---------------------------------------------------------------------------
# Cross-Service Access Policy
# Anomaly Detector reads CloudWatch; Remediation Engine invokes EC2/EKS/Lambda
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "cross_service" {
  # Anomaly Detector – CloudWatch read access
  statement {
    sid    = "AnomalyDetectorCloudWatchRead"
    effect = "Allow"
    actions = [
      "cloudwatch:GetMetricData",
      "cloudwatch:GetMetricStatistics",
      "cloudwatch:ListMetrics",
      "cloudwatch:DescribeAlarms",
      "cloudwatch:DescribeAlarmsForMetric",
      "logs:GetLogEvents",
      "logs:FilterLogEvents",
      "logs:DescribeLogGroups",
      "logs:DescribeLogStreams",
    ]
    resources = ["*"]
  }

  # Remediation Engine – EC2 actions
  statement {
    sid    = "RemediationEngineEC2"
    effect = "Allow"
    actions = [
      "ec2:DescribeInstances",
      "ec2:DescribeInstanceStatus",
      "ec2:StartInstances",
      "ec2:StopInstances",
      "ec2:RebootInstances",
    ]
    resources = ["*"]
  }

  # Remediation Engine – EKS actions
  statement {
    sid    = "RemediationEngineEKS"
    effect = "Allow"
    actions = [
      "eks:DescribeCluster",
      "eks:ListClusters",
      "eks:ListNodegroups",
      "eks:DescribeNodegroup",
      "eks:UpdateNodegroupConfig",
    ]
    resources = ["arn:aws:eks:${var.aws_region}:${var.aws_account_id}:cluster/*"]
  }

  # Remediation Engine – Lambda invoke
  statement {
    sid    = "RemediationEngineLambdaInvoke"
    effect = "Allow"
    actions = [
      "lambda:InvokeFunction",
      "lambda:GetFunction",
      "lambda:ListFunctions",
    ]
    resources = ["arn:aws:lambda:${var.aws_region}:${var.aws_account_id}:function:${local.name_prefix}-*"]
  }

  # Auto-scaling access
  statement {
    sid    = "AutoScalingAccess"
    effect = "Allow"
    actions = [
      "autoscaling:DescribeAutoScalingGroups",
      "autoscaling:DescribeAutoScalingInstances",
      "autoscaling:SetDesiredCapacity",
      "autoscaling:TerminateInstanceInAutoScalingGroup",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "cross_service" {
  name        = "${local.name_prefix}-cross-service-access"
  description = "Cross-service policy: anomaly detector reads CloudWatch; remediation engine drives EC2/EKS/Lambda"
  policy      = data.aws_iam_policy_document.cross_service.json

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# IRSA locals
# ---------------------------------------------------------------------------
locals {
  oidc_provider_url = replace(var.cluster_oidc_issuer_url, "https://", "")
}

# ---------------------------------------------------------------------------
# IRSA Role — anomaly-detector
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "anomaly_detector_irsa_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:monitoring-platform:anomaly-detector"]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "anomaly_detector_irsa" {
  name               = "${local.name_prefix}-anomaly-detector-irsa"
  assume_role_policy = data.aws_iam_policy_document.anomaly_detector_irsa_assume.json

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "anomaly_detector_irsa" {
  role       = aws_iam_role.anomaly_detector_irsa.name
  policy_arn = aws_iam_policy.cross_service.arn
}

# ---------------------------------------------------------------------------
# IRSA Role — remediation-engine
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "remediation_engine_irsa_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:monitoring-platform:remediation-engine"]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "remediation_engine_irsa" {
  name               = "${local.name_prefix}-remediation-engine-irsa"
  assume_role_policy = data.aws_iam_policy_document.remediation_engine_irsa_assume.json

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "remediation_engine_irsa" {
  role       = aws_iam_role.remediation_engine_irsa.name
  policy_arn = aws_iam_policy.cross_service.arn
}
