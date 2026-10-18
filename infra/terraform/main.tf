data "aws_caller_identity" "current" {}

locals {
  prefix     = "secop-risk"
  account_id = data.aws_caller_identity.current.account_id
}

# ---------------------------------------------------------------------------
# S3: el lago (raw/ y las tablas Iceberg de dbt) y los resultados de Athena
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "lake" {
  bucket        = "${local.prefix}-lake-${local.account_id}"
  force_destroy = true # terraform destroy borra también los datos; se recrean con un backfill
}

resource "aws_s3_bucket" "athena_results" {
  bucket        = "${local.prefix}-athena-results-${local.account_id}"
  force_destroy = true
}

locals {
  buckets = {
    lake           = aws_s3_bucket.lake.id
    athena_results = aws_s3_bucket.athena_results.id
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  for_each = local.buckets

  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# SSE-S3 es gratis; una llave KMS propia costaría USD 1 al mes.
resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  for_each = local.buckets

  bucket = each.value

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "lake" {
  bucket = aws_s3_bucket.lake.id

  rule {
    id     = "abortar-subidas-incompletas"
    status = "Enabled"
    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

# Los resultados de Athena solo sirven unos días: se borran a los 7.
resource "aws_s3_bucket_lifecycle_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    id     = "borrar-a-los-7-dias"
    status = "Enabled"
    filter {}

    expiration {
      days = 7
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

# ---------------------------------------------------------------------------
# Glue Data Catalog (solo el catálogo: sin crawlers ni jobs)
# ---------------------------------------------------------------------------
resource "aws_glue_catalog_database" "this" {
  for_each = toset(["secop_raw", "secop_analytics"])

  name = each.key
}

# ---------------------------------------------------------------------------
# Athena: workgroup con límite de escaneo por consulta y configuración forzada
# ---------------------------------------------------------------------------
resource "aws_athena_workgroup" "secop" {
  name          = "secop"
  force_destroy = true

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = var.athena_scan_limit_gb * 1024 * 1024 * 1024

    engine_version {
      selected_engine_version = "Athena engine version 3"
    }

    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena_results.bucket}/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }
}

# ---------------------------------------------------------------------------
# IAM: permisos mínimos del pipeline. Se asignan al rol de Airflow (paso 4)
# y al de GitHub Actions por OIDC (paso 7).
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "pipeline" {
  statement {
    sid       = "ListarBuckets"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.lake.arn, aws_s3_bucket.athena_results.arn]
  }

  statement {
    sid       = "LeerEscribirObjetos"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload"]
    resources = ["${aws_s3_bucket.lake.arn}/*", "${aws_s3_bucket.athena_results.arn}/*"]
  }

  statement {
    sid = "ConsultarAthena"
    actions = [
      "athena:StartQueryExecution",
      "athena:StopQueryExecution",
      "athena:GetQueryExecution",
      "athena:GetQueryResults",
      "athena:BatchGetQueryExecution",
      "athena:ListQueryExecutions",
      "athena:GetWorkGroup",
    ]
    resources = [aws_athena_workgroup.secop.arn]
  }

  statement {
    sid = "CatalogoGlue"
    actions = [
      "glue:GetDatabase",
      "glue:GetDatabases",
      "glue:CreateDatabase",
      "glue:GetTable",
      "glue:GetTables",
      "glue:CreateTable",
      "glue:UpdateTable",
      "glue:DeleteTable",
      "glue:GetPartition",
      "glue:GetPartitions",
      "glue:BatchGetPartition",
      "glue:CreatePartition",
      "glue:BatchCreatePartition",
      "glue:UpdatePartition",
      "glue:DeletePartition",
      "glue:BatchDeletePartition",
    ]
    resources = [
      "arn:aws:glue:${var.region}:${local.account_id}:catalog",
      "arn:aws:glue:${var.region}:${local.account_id}:database/secop_*",
      "arn:aws:glue:${var.region}:${local.account_id}:table/secop_*/*",
    ]
  }
}

resource "aws_iam_policy" "pipeline" {
  name        = "${local.prefix}-pipeline"
  description = "Mínimo privilegio para el pipeline: solo los buckets, el workgroup y las bases secop_*."
  policy      = data.aws_iam_policy_document.pipeline.json
}

# ---------------------------------------------------------------------------
# Presupuesto mensual con alertas por correo
# ---------------------------------------------------------------------------
resource "aws_budgets_budget" "monthly" {
  name         = "${local.prefix}-mensual"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Sin contar créditos: así la alerta mide el gasto real aunque lo paguen los créditos.
  cost_types {
    include_credit = false
    include_refund = false
  }

  dynamic "notification" {
    for_each = [
      { threshold = 50, type = "ACTUAL" },
      { threshold = 80, type = "ACTUAL" },
      { threshold = 100, type = "ACTUAL" },
      { threshold = 100, type = "FORECASTED" },
    ]

    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value.threshold
      threshold_type             = "PERCENTAGE"
      notification_type          = notification.value.type
      subscriber_email_addresses = [var.alert_email]
    }
  }
}
