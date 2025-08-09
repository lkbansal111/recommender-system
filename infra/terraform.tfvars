region          = "eu-north-1"
project_name    = "ml-app"
ecr_repo_name   = "my-repo"

# Choose ONE based on how Jenkins authenticates (user vs role):
jenkins_user_arn = "arn:aws:iam::286549082538:user/jenkins-ci"  # if you use an IAM User
# jenkins_role_arn = "arn:aws:iam::286549082538:role/jenkins-ci-role"  # if assuming a role
