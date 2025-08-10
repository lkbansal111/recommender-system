locals {
  name = var.project_name
}

# ---------- AZs ----------
data "aws_availability_zones" "available" {}

# ---------- VPC ----------
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.8"

  name = "${local.name}-vpc"
  cidr = "10.0.0.0/16"

  azs             = slice(data.aws_availability_zones.available.names, 0, 3)
  private_subnets = ["10.0.1.0/24","10.0.2.0/24","10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24","10.0.102.0/24","10.0.103.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true

  tags = { Project = local.name }
}

# ---------- ECR ----------
resource "aws_ecr_repository" "main" {
  name = var.ecr_repo_name

  image_scanning_configuration { scan_on_push = true }
  image_tag_mutability = "MUTABLE"

  encryption_configuration { encryption_type = "AES256" }

  tags = { Project = local.name }
}

resource "aws_ecr_lifecycle_policy" "main" {
  repository = aws_ecr_repository.main.name
  policy     = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 20 images"
      selection    = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}

# ---------- EKS (pin v19) ----------
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.21"  # 👈 v19 line

  cluster_name    = "${local.name}-cluster"
  cluster_version = "1.30"  # if it errors, use "1.29"

  vpc_id                         = module.vpc.vpc_id
  subnet_ids                     = module.vpc.private_subnets
  cluster_endpoint_public_access = true

  eks_managed_node_groups = {
    default = {
      instance_types = var.node_instance_types
      min_size       = var.min_size
      max_size       = var.max_size
      desired_size   = var.desired_size
    }
  }

  # v19 me aws-auth yahin manage hota hai
  manage_aws_auth = true

  # IAM User ko cluster admin do (optional)
  map_users = var.jenkins_user_arn != "" ? [{
    userarn  = var.jenkins_user_arn
    username = "jenkins"
    groups   = ["system:masters"]
  }] : []

  # IAM Role ko cluster admin do (optional)
  map_roles = var.jenkins_role_arn != "" ? [{
    rolearn  = var.jenkins_role_arn
    username = "jenkins-role"
    groups   = ["system:masters"]
  }] : []

  tags = { Project = local.name }
}
