# Identidad del CI de GitHub Actions. Lo ideal sería OIDC (sin llaves), pero la
# organización de AWS de esta cuenta lo prohíbe con una SCP. Por eso el CI usa
# un usuario IAM cuya llave solo puede leer raw/ y escribir en secop_ci: si se
# filtrara, no alcanza producción. La llave se crea con el CLI y va directo a
# los secretos de GitHub, así que nunca queda en el state de Terraform.
resource "aws_iam_user" "github_ci" {
  name = "${local.prefix}-github-ci"
}

# Base aparte para el CI: dbt construye ahí sus tablas de prueba.
resource "aws_glue_catalog_database" "ci" {
  name = "secop_ci"
}

# Más estrecho que secop-risk-pipeline: lee raw/ y escribe solo en secop_ci.
data "aws_iam_policy_document" "github_ci" {
  statement {
    sid       = "ListarBuckets"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.lake.arn, aws_s3_bucket.athena_results.arn]
  }

  statement {
    sid       = "LeerRaw"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.lake.arn}/raw/*"]
  }

  statement {
    sid     = "EscribirCI"
    actions = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload"]
    resources = [
      "${aws_s3_bucket.lake.arn}/dbt/secop_ci/*",
      "${aws_s3_bucket.athena_results.arn}/*",
    ]
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
    sid = "LeerCatalogoRaw"
    actions = [
      "glue:GetDatabase",
      "glue:GetDatabases",
      "glue:GetTable",
      "glue:GetTables",
      "glue:GetPartition",
      "glue:GetPartitions",
      "glue:BatchGetPartition",
    ]
    resources = [
      "arn:aws:glue:${var.region}:${local.account_id}:catalog",
      "arn:aws:glue:${var.region}:${local.account_id}:database/secop_raw",
      "arn:aws:glue:${var.region}:${local.account_id}:table/secop_raw/*",
    ]
  }

  statement {
    sid = "EscribirCatalogoCI"
    actions = [
      "glue:GetDatabase",
      "glue:GetDatabases",
      "glue:GetTable",
      "glue:GetTables",
      "glue:CreateTable",
      "glue:UpdateTable",
      "glue:DeleteTable",
      "glue:GetTableVersions",
      "glue:DeleteTableVersion",
      "glue:BatchDeleteTableVersion",
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
      "arn:aws:glue:${var.region}:${local.account_id}:database/secop_ci",
      "arn:aws:glue:${var.region}:${local.account_id}:table/secop_ci/*",
    ]
  }
}

resource "aws_iam_user_policy" "github_ci" {
  name   = "dbt-ci"
  user   = aws_iam_user.github_ci.name
  policy = data.aws_iam_policy_document.github_ci.json
}

output "github_ci_user" {
  value = aws_iam_user.github_ci.name
}
