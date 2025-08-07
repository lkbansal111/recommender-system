resource "aws_ecr_repository" "app" {
  name                 = var.ecr_repo
  image_scanning_configuration { scan_on_push = true }
}
