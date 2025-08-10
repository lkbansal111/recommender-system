pipeline {
  agent any
  options { timestamps() }

  environment {
    AWS_ACCOUNT_ID   = '286549082538'
    AWS_REGION       = 'eu-north-1'
    ECR_REPO         = 'my-repo'
    EKS_CLUSTER_NAME = 'ml-app-cluster'
    IMAGE_TAG        = 'latest'

    // talk to Docker Desktop from WSL/Jenkins
    DOCKER_HOST      = 'tcp://host.docker.internal:2375'
    DOCKER_BUILDKIT  = '1'

    // repo paths
    TF_DIR           = 'infra'
    K8S_MANIFEST     = 'deployment.yaml'
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

    stage('Repo layout check') {
      steps {
        sh '''#!/usr/bin/env sh
set -e
echo "Workspace: $PWD"
ls -la
echo "Checking TF_DIR: $TF_DIR"
test -d "$TF_DIR" || { echo "ERROR: TF_DIR '$TF_DIR' not found"; exit 1; }
find "$TF_DIR" -maxdepth 1 -type f -name '*.tf' | grep -q . || { echo "ERROR: no .tf in $TF_DIR"; exit 1; }
'''
      }
    }

stage('Provision AWS (Terraform)') {
  steps {
    withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
      sh '''#!/usr/bin/env sh
set -eux

# 1) start a long-lived terraform container
CID=$(docker run -d \
  --entrypoint sh \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN \
  -e AWS_REGION -e AWS_DEFAULT_REGION="${AWS_REGION}" \
  hashicorp/terraform:1.9.5 \
  -lc "sleep infinity")

# 2) copy terraform files in
docker cp "${TF_DIR}/." "$CID":/workspace/

# 3) run terraform
docker exec "$CID" sh -lc '
  set -e
  cd /workspace
  terraform init -input=false
  terraform apply -auto-approve -input=false
'

# 4) cleanup
docker rm -f "$CID"
'''
    }
  }
}


stage('DVC pull (from S3)') {
  steps {
    withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
      sh '''#!/usr/bin/env sh
set -eux

# 1) start a python container
CID=$(docker run -d \
  --entrypoint sh \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN \
  -e AWS_REGION -e AWS_DEFAULT_REGION="${AWS_REGION}" \
  python:3.11-slim \
  -lc "sleep infinity")

# 2) copy full repo (DVC needs .dvc etc.)
docker cp . "$CID":/workspace

# 3) install + pull
docker exec "$CID" sh -lc '
  set -e
  apt-get update && apt-get install -y --no-install-recommends git curl && rm -rf /var/lib/apt/lists/*
  python -m pip install --no-cache-dir -U pip
  python -m pip install --no-cache-dir "dvc[s3]"
  cd /workspace
  dvc pull
'

# 4) copy pulled artifacts back
docker cp "$CID":/workspace/. "$PWD"

# 5) cleanup
docker rm -f "$CID"
'''
    }
  }
}


    stage('Build & Push Docker Image to ECR') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
          sh '''#!/usr/bin/env sh
set -eux
docker run --rm \
  --entrypoint sh \
  -e DOCKER_HOST="${DOCKER_HOST}" \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN -e AWS_REGION \
  -w /workspace \
  -v "$PWD":/workspace:ro \
  docker:24-cli \
  -lc "
    set -e
    apk add --no-cache python3 py3-pip
    pip install --no-cache-dir awscli

    ECR_HOST='${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com'
    ECR_URL=\\"${ECR_HOST}/${ECR_REPO}\\"

    aws ecr describe-repositories --repository-names '${ECR_REPO}' --region '${AWS_REGION}' >/dev/null 2>&1 || \
      aws ecr create-repository --repository-name '${ECR_REPO}' --region '${AWS_REGION}' >/dev/null

    aws ecr get-login-password --region '${AWS_REGION}' | docker login --username AWS --password-stdin \\"${ECR_HOST}\\"

    docker build -t '${ECR_REPO}:${IMAGE_TAG}' .
    docker tag '${ECR_REPO}:${IMAGE_TAG}' \\"${ECR_URL}:${IMAGE_TAG}\\"
    docker push \\"${ECR_URL}:${IMAGE_TAG}\\"
  "
'''
        }
      }
    }

    stage('Deploy to EKS') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {

          // render manifest locally (host) first
          sh '''#!/usr/bin/env sh
set -eux
IMG="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}"
sed "s|IMAGE_PLACEHOLDER|$IMG|g" "${K8S_MANIFEST}" > /tmp/deploy.yaml
ls -l /tmp/deploy.yaml
'''

          // run kubectl in a container and read manifest from stdin
          sh '''#!/usr/bin/env sh
set -eux
docker run --rm \
  --entrypoint bash \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN -e AWS_REGION \
  amazonlinux:2023 \
  -lc "
    set -e
    dnf -y install tar gzip curl unzip shadow-utils

    curl -L -o /usr/local/bin/kubectl 'https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl'
    chmod +x /usr/local/bin/kubectl

    curl -sSL 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o '/tmp/awscliv2.zip'
    unzip -o /tmp/awscliv2.zip -d /tmp
    /tmp/aws/install -i /opt/aws-cli -b /usr/local/bin

    aws eks update-kubeconfig --region '${AWS_REGION}' --name '${EKS_CLUSTER_NAME}'
    kubectl apply -f -
  " < /tmp/deploy.yaml
'''
        }
      }
    }
  }
}
