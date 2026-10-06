locals {
  functions = {
    auto-scaler = {
      description  = "Automatically scales EKS node groups based on AI-detected load anomalies"
      timeout      = 300
      memory_size  = 256
      schedule     = null  # triggered by EventBridge rule on CloudWatch alarm
    }
    instance-restarter = {
      description  = "Restarts unhealthy EC2 instances identified by the anomaly detector"
      timeout      = 120
      memory_size  = 128
      schedule     = null
    }
    alert-processor = {
      description  = "Processes SNS alerts and routes them to the remediation engine"
      timeout      = 60
      memory_size  = 128
      schedule     = null  # triggered by SNS
    }
    metrics-collector = {
      description  = "Collects custom application metrics and pushes them to CloudWatch"
      timeout      = 60
      memory_size  = 256
      schedule     = "rate(1 minute)"
    }
  }

  name_prefix = "${var.project_name}-${var.environment}"
}

# ---------------------------------------------------------------------------
# Lambda Execution IAM Role
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
  name               = "${local.name_prefix}-lambda-execution-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

data "aws_iam_policy_document" "lambda_custom" {
  # CloudWatch
  statement {
    sid    = "CloudWatchMetrics"
    effect = "Allow"
    actions = [
      "cloudwatch:PutMetricData",
      "cloudwatch:GetMetricStatistics",
      "cloudwatch:ListMetrics",
      "cloudwatch:DescribeAlarms",
      "cloudwatch:SetAlarmState",
    ]
    resources = ["*"]
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
      "ssm:DescribeInstanceInformation",
      "ssm:StartAutomationExecution",
      "ssm:GetAutomationExecution",
    ]
    resources = ["*"]
  }

  # EKS
  statement {
    sid    = "EKSAccess"
    effect = "Allow"
    actions = [
      "eks:DescribeCluster",
      "eks:ListNodegroups",
      "eks:DescribeNodegroup",
      "eks:UpdateNodegroupConfig",
    ]
    resources = ["*"]
  }

  # RDS
  statement {
    sid    = "RDSAccess"
    effect = "Allow"
    actions = [
      "rds:DescribeDBInstances",
      "rds:RebootDBInstance",
    ]
    resources = ["*"]
  }

  # Secrets Manager (retrieve RDS password)
  statement {
    sid    = "SecretsManager"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
    ]
    resources = ["*"]
  }

  # SNS publish
  statement {
    sid    = "SNSPublish"
    effect = "Allow"
    actions = [
      "sns:Publish",
    ]
    resources = [var.sns_alert_topic_arn]
  }
}

resource "aws_iam_role_policy" "lambda_custom" {
  name   = "${local.name_prefix}-lambda-custom-policy"
  role   = aws_iam_role.lambda_execution.id
  policy = data.aws_iam_policy_document.lambda_custom.json
}

# ---------------------------------------------------------------------------
# Security Group for Lambda functions (VPC-attached)
# ---------------------------------------------------------------------------
resource "aws_security_group" "lambda" {
  name        = "${local.name_prefix}-lambda-sg"
  description = "Security group for Lambda functions running inside the VPC"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = {
    Name        = "${local.name_prefix}-lambda-sg"
    Project     = var.project_name
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# Dummy archive for Lambda deployment packages
# (Replace with real build artifacts in CI/CD)
# ---------------------------------------------------------------------------
data "archive_file" "lambda_dummy" {
  for_each = local.functions

  type        = "zip"
  output_path = "${path.module}/dummy_${each.key}.zip"

  source {
    content  = <<-PYTHON
      import json, os, logging

      logger = logging.getLogger()
      logger.setLevel(logging.INFO)

      def lambda_handler(event, context):
          logger.info("Function: ${each.key}")
          logger.info("Event: %s", json.dumps(event))
          return {"statusCode": 200, "body": json.dumps({"function": "${each.key}", "status": "ok"})}
    PYTHON
    filename = "handler.py"
  }
}

# ---------------------------------------------------------------------------
# CloudWatch Log Groups
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "lambda" {
  for_each = local.functions

  name              = "/aws/lambda/${local.name_prefix}-${each.key}"
  retention_in_days = 30

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# Lambda Functions
# ---------------------------------------------------------------------------
resource "aws_lambda_function" "main" {
  for_each = local.functions

  function_name = "${local.name_prefix}-${each.key}"
  description   = each.value.description
  role          = aws_iam_role.lambda_execution.arn
  runtime       = "python3.11"
  handler       = "handler.lambda_handler"
  timeout       = each.value.timeout
  memory_size   = each.value.memory_size

  filename         = data.archive_file.lambda_dummy[each.key].output_path
  source_code_hash = data.archive_file.lambda_dummy[each.key].output_base64sha256

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      ENVIRONMENT            = var.environment
      PROJECT_NAME           = var.project_name
      ANOMALY_DETECTOR_URL   = var.anomaly_detector_url
      REMEDIATION_ENGINE_URL = var.remediation_engine_url
      RDS_ENDPOINT           = var.rds_endpoint
      SNS_ALERT_TOPIC_ARN    = var.sns_alert_topic_arn
      LOG_LEVEL              = var.environment == "prod" ? "WARNING" : "DEBUG"
    }
  }

  tracing_config {
    mode = "Active"
  }

  tags = {
    Name        = "${local.name_prefix}-${each.key}"
    Project     = var.project_name
    Environment = var.environment
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda,
    aws_iam_role_policy_attachment.lambda_basic,
  ]
}

# ---------------------------------------------------------------------------
# EventBridge – Scheduled rule for metrics-collector (every 1 minute)
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "metrics_collector_schedule" {
  name                = "${local.name_prefix}-metrics-collector-schedule"
  description         = "Trigger metrics-collector Lambda every minute"
  schedule_expression = "rate(1 minute)"
  state               = "ENABLED"

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_cloudwatch_event_target" "metrics_collector" {
  rule      = aws_cloudwatch_event_rule.metrics_collector_schedule.name
  target_id = "metrics-collector-lambda"
  arn       = aws_lambda_function.main["metrics-collector"].arn
}

resource "aws_lambda_permission" "metrics_collector_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.main["metrics-collector"].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.metrics_collector_schedule.arn
}

# ---------------------------------------------------------------------------
# EventBridge – rule for anomaly-triggered auto-scaler
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "auto_scaler_trigger" {
  name        = "${local.name_prefix}-auto-scaler-trigger"
  description = "Trigger auto-scaler Lambda on CloudWatch alarm state change"
  state       = "ENABLED"

  event_pattern = jsonencode({
    source      = ["aws.cloudwatch"]
    detail-type = ["CloudWatch Alarm State Change"]
    detail = {
      state = {
        value = ["ALARM"]
      }
    }
  })

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_cloudwatch_event_target" "auto_scaler" {
  rule      = aws_cloudwatch_event_rule.auto_scaler_trigger.name
  target_id = "auto-scaler-lambda"
  arn       = aws_lambda_function.main["auto-scaler"].arn
}

resource "aws_lambda_permission" "auto_scaler_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.main["auto-scaler"].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.auto_scaler_trigger.arn
}

# ---------------------------------------------------------------------------
# SNS Subscription – alert-processor triggered by SNS topic
# ---------------------------------------------------------------------------
resource "aws_sns_topic_subscription" "alert_processor" {
  topic_arn = var.sns_alert_topic_arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.main["alert-processor"].arn
}

resource "aws_lambda_permission" "alert_processor_sns" {
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.main["alert-processor"].function_name
  principal     = "sns.amazonaws.com"
  source_arn    = var.sns_alert_topic_arn
}

# ---------------------------------------------------------------------------
# EventBridge – instance-restarter triggered on EC2 state-change events
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "instance_restarter_trigger" {
  name        = "${local.name_prefix}-instance-restarter-trigger"
  description = "Trigger instance-restarter on EC2 instance health change"
  state       = "ENABLED"

  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Instance State-change Notification"]
    detail = {
      state = ["stopped", "stopping"]
    }
  })

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_cloudwatch_event_target" "instance_restarter" {
  rule      = aws_cloudwatch_event_rule.instance_restarter_trigger.name
  target_id = "instance-restarter-lambda"
  arn       = aws_lambda_function.main["instance-restarter"].arn
}

resource "aws_lambda_permission" "instance_restarter_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.main["instance-restarter"].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.instance_restarter_trigger.arn
}
