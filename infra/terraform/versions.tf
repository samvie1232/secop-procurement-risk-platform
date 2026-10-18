terraform {
  required_version = "~> 1.16"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.69"
    }
  }

  # Bucket creado por infra/bootstrap. use_lockfile bloquea el state sin DynamoDB.
  backend "s3" {
    bucket       = "secop-risk-tfstate-716528269015"
    key          = "secop-risk/terraform.tfstate"
    region       = "us-east-2"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      project    = "secop-risk"
      managed_by = "terraform"
    }
  }
}
