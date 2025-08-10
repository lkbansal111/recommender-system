pipeline {
  agent any

  options { timestamps() }

  environment {
    VENV_DIR          = 'venv'
    AWS_ACCOUNT_ID    = '286549082538'
    AWS_REGION        = 'eu-north-1'
    ECR_REPO          = 'my-repo'
    EKS_CLUSTER_NAME  = 'ml-app-cluster'
    AWS_CLI_PATH      = '/usr/local/bin'
    IMAGE_TAG         = 'latest'
    DEBIAN_FRONTEND   = 'noninteractive'
  }

  stages {

    stage('Install base tools') {
      steps {
        sh '''#!/usr/bin/env bash
set -euo pipefail
apt-get update
apt-get install -y --no-install-recommends \
  curl unzip ca-certificates gnupg apt-transport-https \
  python3 python3-venv python3-pip

# Ensure 'python' points to python3
command -v python >/dev/null 2>&1 || ln -s /usr/bin/python3 /usr/bin/python
python --version
pip --version

# Install kubectl (latest stable)
curl -L -o /usr/local/bin/kubectl \
  "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x /usr/local/bin/kubectl
kubectl version --client

# Install AWS CLI v2
curl -sSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip"
unzip -o /tmp/awscliv2.zip -d /tmp
/tmp/aws/install --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli --update
aws --version

# Install Terraform
TF_VERSION=$(curl -s https://checkpoint-api.hashicorp.com/v1/check/terraform | grep -oP '"current_version":"\\K[^"]+')
curl -fsSL "https://releases.hashicorp.com/terraform/${TF_VERSION}/terraform_${TF_VERSION}_linux_amd64.zip" -o /tmp/terraform.zip
unzip -o /tmp/terraform.zip -d /usr/local/bin
chmod +x /usr/local/bin/terraform
terraform -version
'''
      }
    }

    stage('Clone from GitHub') {
      steps {
        echo 'Cloning repository …'
        checkout scmGit(
          branches: [[name: '*/dev']],
          extensions: [],
          userRemoteConfigs: [[
            credentialsId: 'github-token',
            url: 'https://github.com/lkbansal111/recommender-system.git'
          ]]
        )
      }
    }

    stage('Provision AWS (Terraform)') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
          dir('infra') {
            sh '''#!/usr/bin/env bash
set -euo pipefail
export AWS_DEFAULT_REGION="$AWS_REGION"
terraform init -input=false
terraform apply -auto-approve -input=false
'''
          }
        }
      }
    }

    stage('Create virtualenv') {
      steps {
        echo 'Creating Python virtual environment …'
        sh '''#!/usr/bin/env bash
set -euo pipefail
python -m venv "$VENV_DIR"
. "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -e .
pip install dvc
'''
      }
    }

    stage('DVC pull (from S3)') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
          echo 'Fetching data artifacts with DVC …'
          sh '''#!/usr/bin/env bash
set -euo pipefail
. "$VENV_DIR/bin/activate"
export AWS_DEFAULT_REGION="$AWS_REGION"
dvc pull
'''
        }
      }
    }

    stage('Build & Push Docker Image to ECR') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
          script {
            def accountId = sh(script: "bash -lc \"aws sts get-caller-identity --query Account --output text\"", returnStdout: true).trim()
            def ecrUrl = "${accountId}.dkr.ecr.${env.AWS_REGION}.amazonaws.com/${env.ECR_REPO}"

            sh """#!/usr/bin/env bash
set -euo pipefail
export PATH=\$PATH:${env.AWS_CLI_PATH}

# Create repo if it doesn't exist
aws ecr describe-repositories --repository-names ${env.ECR_REPO} --region ${env.AWS_REGION} >/dev/null 2>&1 || \
  aws ecr create-repository --repository-name ${env.ECR_REPO} --region ${env.AWS_REGION} >/dev/null

aws ecr get-login-password --region ${env.AWS_REGION} | docker login --username AWS --password-stdin ${ecrUrl}
docker build -t ${env.ECR_REPO}:${env.IMAGE_TAG} .
docker tag ${env.ECR_REPO}:${env.IMAGE_TAG} ${ecrUrl}:${env.IMAGE_TAG}
docker push ${ecrUrl}:${env.IMAGE_TAG}
"""
          }
        }
      }
    }

    stage('Deploy to EKS') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
          echo 'Updating kubeconfig & applying manifests …'
          sh '''#!/usr/bin/env bash
set -euo pipefail
export PATH=$PATH:$AWS_CLI_PATH
aws eks update-kubeconfig --region "$AWS_REGION" --name "$EKS_CLUSTER_NAME"

# Template the image into the manifest before apply
sed -i "s|IMAGE_PLACEHOLDER|$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG|g" deployment.yaml

kubectl apply -f deployment.yaml
'''
        }
      }
    }
  }
}
