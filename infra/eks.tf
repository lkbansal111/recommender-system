module "eks" {
  source          = "terraform-aws-modules/eks/aws"
  cluster_name    = var.cluster_name
  cluster_version = "1.30"
  subnet_ids      = data.aws_subnets.private.ids
  # … plus node groups, IRSA, etc …
}
