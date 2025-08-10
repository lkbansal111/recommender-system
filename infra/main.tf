terraform {
  required_version = ">= 1.5"

  backend "s3" {
    bucket         = "tf-state-286549082538"
    key            = "eks/dev/terraform.tfstate" # override per env via -backend-config if needed
    region         = "us-east-1"
    dynamodb_table = "tf-locks"
    encrypt        = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.100"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      ManagedBy   = "terraform"
      Environment = terraform.workspace
      Project     = "recommender-system"
    }
  }
}

data "aws_availability_zones" "available" {}
data "aws_caller_identity" "current" {}

locals {
  # Unique cluster name per workspace (e.g., learn-eks-dev)
  cluster_name = "${var.cluster_name}-${terraform.workspace}"
}

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

  # Tag public subnets for Kubernetes LoadBalancers and discovery
  public_subnet_tags = {
    "kubernetes.io/role/elb"                       = "1"
    "kubernetes.io/cluster/${local.cluster_name}"  = "shared"
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = local.cluster_name
  cluster_version = "1.30"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.public_subnets

  cluster_endpoint_private_access = false
  cluster_endpoint_public_access  = true
  cluster_endpoint_public_access_cidrs = var.cluster_endpoint_public_access_cidrs

  # Disable control-plane logs and CW log group
  cluster_enabled_log_types   = []
  create_cloudwatch_log_group = false

  authentication_mode = "API"  # EKS access entries (no aws-auth)

  # No envelope encryption (avoids KMS)
  cluster_encryption_config = []
  create_kms_key            = false

  eks_managed_node_groups = {
    default = {
      desired_size   = 1
      min_size       = 1
      max_size       = 1
      instance_types = ["t3.medium"]
      disk_size      = 40
      capacity_type  = "ON_DEMAND"
      subnet_ids     = module.vpc.public_subnets
    }
  }

  # Cluster-admin for current caller
  access_entries = {
    me = {
      principal_arn = data.aws_caller_identity.current.arn
      policy_associations = {
        admin = {
          policy_arn   = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
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

variable "cluster_name" {
  description = "Base EKS cluster name; workspace is appended"
  type        = string
  default     = "learn-eks"
}

variable "cluster_endpoint_public_access_cidrs" {
  description = "CIDR blocks allowed to reach the EKS public API endpoint"
  type        = list(string)
  default     = ["0.0.0.0/0"] # tighten to your Jenkins/office egress CIDRs
}

output "cluster_name"   { value = module.eks.cluster_name }
output "cluster_region" { value = var.region }
