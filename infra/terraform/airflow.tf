# ---------------------------------------------------------------------------
# Identidad de Airflow: un rol con la política de mínimo privilegio del
# pipeline. Airflow lo asume desde tu sesión de `aws login` (perfil
# secop-airflow), así que no existen llaves permanentes.
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "airflow_confianza" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account_id}:root"] # identidades de esta cuenta con permiso para asumirlo
    }
  }
}

resource "aws_iam_role" "airflow" {
  name                 = "${local.prefix}-airflow"
  description          = "Rol que usa Airflow local para correr el pipeline."
  assume_role_policy   = data.aws_iam_policy_document.airflow_confianza.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy_attachment" "airflow_pipeline" {
  role       = aws_iam_role.airflow.name
  policy_arn = aws_iam_policy.pipeline.arn
}

# ---------------------------------------------------------------------------
# Alertas de falla: SNS a tu correo. Las primeras 1.000 notificaciones por
# correo de cada mes son gratis.
# ---------------------------------------------------------------------------
resource "aws_sns_topic" "alertas" {
  name = "${local.prefix}-alertas"
}

resource "aws_sns_topic_subscription" "alertas_correo" {
  topic_arn = aws_sns_topic.alertas.arn
  protocol  = "email"
  endpoint  = var.alert_email # llega un correo para confirmar la suscripción
}

data "aws_iam_policy_document" "airflow_alertas" {
  statement {
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alertas.arn]
  }
}

resource "aws_iam_role_policy" "airflow_alertas" {
  name   = "publicar-alertas"
  role   = aws_iam_role.airflow.id
  policy = data.aws_iam_policy_document.airflow_alertas.json
}

output "airflow_role_arn" {
  value = aws_iam_role.airflow.arn
}

output "alertas_topic_arn" {
  value = aws_sns_topic.alertas.arn
}
