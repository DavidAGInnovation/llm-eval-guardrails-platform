output "cloudwatch_api_log_group" {
  value = aws_cloudwatch_log_group.api.name
}

output "cloudwatch_worker_log_group" {
  value = aws_cloudwatch_log_group.worker.name
}
