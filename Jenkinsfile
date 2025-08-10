pipeline {
  agent any
  options { timestamps() }

  environment {
    AWS_ACCOUNT_ID   = '286549082538'
    AWS_REGION       = 'eu-north-1'
    ECR_REPO         = 'my-repo'
    EKS_CLUSTER_NAME = 'ml-app-cluster'
    IMAGE_TAG        = 'latest'

    // WSL + Docker Desktop over TCP
    DOCKER_HOST      = 'tcp://host.docker.internal:2375'
    DOCKER_BUILDKIT  = '1'
  }

  stages {

    stage('Checkout') {
      steps {
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

    stage('Docker smoke test') {
      steps {
        sh '''#!/usr/bin/env sh
set -e
echo "DOCKER_HOST=$DOCKER_HOST"
docker version
docker ps
'''
      }
    }

    stage('Provision AWS (Terraform)') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
          sh '''#!/usr/bin/env sh
set -e
docker run --rm \
  --entrypoint sh \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN \
  -e AWS_REGION -e AWS_DEFAULT_REGION=${AWS_REGION} \
  -v "$PWD/infra":/infra -w /infra \
  hashicorp/terraform:1.9.5 \
  -lc "terraform init -input=false && terraform apply -auto-approve -input=false"
'''
        }
      }
    }

    stage('DVC pull (from S3)') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
          sh '''#!/usr/bin/env sh
set -e
docker run --rm \
  --entrypoint sh \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN \
  -e AWS_REGION -e AWS_DEFAULT_REGION=${AWS_REGION} \
  -v "$PWD":/workspace -w /workspace \
  python:3.11-slim \
  -lc "
    set -e
    apt-get update && apt-get install -y --no-install-recommends git curl && rm -rf /var/lib/apt/lists/*
    python -m pip install --no-cache-dir -U pip
    python -m pip install --no-cache-dir 'dvc[s3]'
    dvc pull
  "
'''
        }
      }
    }

    stage('Build & Push Docker Image to ECR') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
          sh '''#!/usr/bin/env sh
set -e
docker run --rm \
  --entrypoint sh \
  -e DOCKER_HOST="${DOCKER_HOST}" \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN -e AWS_REGION \
  -v "$PWD":/workspace -w /workspace \
  docker:24-cli \
  -lc "
    set -e
    apk add --no-cache python3 py3-pip
    pip install --no-cache-dir awscli

    ECR_HOST='${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com'
    ECR_URL=\"${ECR_HOST}/${ECR_REPO}\"

    # ensure repo exists
    aws ecr describe-repositories --repository-names '${ECR_REPO}' --region '${AWS_REGION}' >/dev/null 2>&1 || \
      aws ecr create-repository --repository-name '${ECR_REPO}' --region '${AWS_REGION}' >/dev/null

    # login & build/push
    aws ecr get-login-password --region '${AWS_REGION}' | docker login --username AWS --password-stdin \"${ECR_HOST}\"
    docker build -t '${ECR_REPO}:${IMAGE_TAG}' .
    docker tag '${ECR_REPO}:${IMAGE_TAG}' \"${ECR_URL}:${IMAGE_TAG}\"
    docker push \"${ECR_URL}:${IMAGE_TAG}\"
  "
'''
        }
      }
    }

    stage('Deploy to EKS') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
          sh '''#!/usr/bin/env sh
set -e
docker run --rm \
  --entrypoint bash \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN -e AWS_REGION \
  -v "$PWD":/workspace -w /workspace \
  amazonlinux:2023 \
  -lc "
    set -e
    dnf -y install tar gzip curl unzip shadow-utils

    # kubectl
    curl -L -o /usr/local/bin/kubectl 'https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl'
    chmod +x /usr/local/bin/kubectl
    kubectl version --client

    # AWS CLI v2
    curl -sSL 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o '/tmp/awscliv2.zip'
    unzip -o /tmp/awscliv2.zip -d /tmp
    /tmp/aws/install -i /opt/aws-cli -b /usr/local/bin
    aws --version

    # update kubeconfig & deploy
    aws eks update-kubeconfig --region '${AWS_REGION}' --name '${EKS_CLUSTER_NAME}'
    sed -i \"s|IMAGE_PLACEHOLDER|${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}|g\" deployment.yaml
    kubectl apply -f deployment.yaml
  "
'''
        }
      }
    }
  }
}
