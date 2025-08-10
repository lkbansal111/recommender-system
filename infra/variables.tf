variable "region" {
  type        = string
  description = "AWS region"
}

variable "project_name" {
  type        = string
  description = "Name prefix for resources"
  default     = "ml-app"
}

variable "ecr_repo_name" {
  type        = string
  description = "ECR repository name"
}

# Jenkins identity (choose ONE: user OR role)
variable "jenkins_user_arn" {
  type    = string
  default = ""
}

variable "jenkins_role_arn" {
  type    = string
  default = ""
}

# Node group sizing (adjust if needed)
variable "node_instance_types" {
  type    = list(string)
  default = ["t3.medium"]
}

variable "desired_size" {
  type    = number
  default = 2
}

variable "min_size" {
  type    = number
  default = 1
}

variable "max_size" {
  type    = number
  default = 3
}
