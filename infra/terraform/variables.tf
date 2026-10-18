variable "region" {
  description = "Región de AWS (la cuenta de la nueva experiencia está fija en us-east-2)."
  type        = string
  default     = "us-east-2"
}

variable "alert_email" {
  description = "Correo que recibe las alertas del presupuesto."
  type        = string
}

variable "monthly_budget_usd" {
  description = "Tope mensual del presupuesto, en USD."
  type        = number
  default     = 5
}

variable "athena_scan_limit_gb" {
  description = "Athena cancela cualquier consulta que intente escanear más que esto."
  type        = number
  default     = 5
}
