output "lake_bucket" {
  value = aws_s3_bucket.lake.bucket
}

output "athena_results_bucket" {
  value = aws_s3_bucket.athena_results.bucket
}

output "athena_workgroup" {
  value = aws_athena_workgroup.secop.name
}

output "glue_databases" {
  value = sort([for db in aws_glue_catalog_database.this : db.name])
}

output "pipeline_policy_arn" {
  value = aws_iam_policy.pipeline.arn
}
