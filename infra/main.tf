terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.100" }
  }
}

provider "aws" {
  region = var.region
}

data "aws_availability_zones" "available" {}
data "aws_caller_identity" "current" {}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.21.0"

  name = "learn-eks-vpc"
  cidr = "10.0.0.0/16"

  azs            = slice(data.aws_availability_zones.available.names, 0, 2)
  public_subnets = ["10.0.1.0/24", "10.0.2.0/24"]

  enable_nat_gateway      = false
  single_nat_gateway      = false
  map_public_ip_on_launch = true
  enable_dns_hostnames    = true
  enable_dns_support      = true
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"              # 👈 v20+ required for access_entries

  cluster_name    = "learn-eks"
  cluster_version = "1.30"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.public_subnets

  cluster_endpoint_private_access = false
  cluster_endpoint_public_access  = true
  cluster_enabled_log_types       = []   # no CloudWatch logs for now
  authentication_mode             = "API"  # new EKS auth (no aws-auth configmap)

  eks_managed_node_groups = {
    default = {
      desired_size   = 1
      min_size       = 1
      max_size       = 1
      instance_types = ["t3.medium"]   # or keep t3.small if you must
      disk_size      = 40              # increase root volume for images/logs
      capacity_type  = "ON_DEMAND"
      subnet_ids     = module.vpc.public_subnets
    }
  }

  # Give the running IAM identity cluster-admin via Access Entry
  access_entries = {
    me = {
      principal_arn = data.aws_caller_identity.current.arn
      policy_associations = {
        admin = {
          policy_arn  = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
          access_scope = { type = "cluster" }
        }
      }
    }
  }
}

variable "region" {
  type    = string
  default = "us-east-1"
}

output "cluster_name"   { value = module.eks.cluster_name }
output "cluster_region" { value = var.region }
