provider "aws" {
  region = var.region
}

# Token to talk to the EKS API as your Jenkins IAM identity
data "aws_eks_cluster_auth" "this" {
  name = module.eks.cluster_name
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
  token                  = data.aws_eks_cluster_auth.this.token
  # NOTE: remove load_config_file line (not supported in this provider)
}
