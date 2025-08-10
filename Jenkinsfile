pipeline {
  agent any
  options { timestamps() }

  environment {
    // ---- AWS / ECR ----
    AWS_ACCOUNT_ID = '286549082538'
    AWS_REGION     = 'us-east-1'
    ECR_REPO       = 'my-repo'
    IMAGE_TAG      = 'latest'

    // ---- EKS naming driven by Terraform workspace ----
    DEPLOY_ENV        = 'dev'          // set per branch/env
    BASE_CLUSTER_NAME = 'learn-eks'    // base; TF makes it ${BASE_CLUSTER_NAME}-${DEPLOY_ENV}

    // ---- Docker host (Docker Desktop or remote daemon) ----
    DOCKER_HOST     = 'tcp://host.docker.internal:2375'
    DOCKER_BUILDKIT = '1'

    // ---- IaC backend ----
    TF_DIR          = 'infra'
    TF_STATE_BUCKET = 'tf-state-286549082538'  // will be created if missing
    TF_LOCK_TABLE   = 'tf-locks'               // will be created if missing

    // ---- App deploy ----
    K8S_MANIFEST    = 'deployment.yaml'
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

# Clean any old TF helper containers
docker ps -q --filter "ancestor=hashicorp/terraform:1.9.5" | xargs -r docker rm -f || true

# Start a throwaway container for TF work, PASS all needed env vars
CID=$(docker run -d \
  --entrypoint sh \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN \
  -e AWS_REGION -e AWS_DEFAULT_REGION="${AWS_REGION}" \
  -e TF_VAR_region="${AWS_REGION}" \
  -e TF_VAR_cluster_name="${BASE_CLUSTER_NAME}" \
  -e TF_STATE_BUCKET="${TF_STATE_BUCKET}" \
  -e TF_LOCK_TABLE="${TF_LOCK_TABLE}" \
  -e DEPLOY_ENV="${DEPLOY_ENV}" \
  -e BASE_CLUSTER_NAME="${BASE_CLUSTER_NAME}" \
  hashicorp/terraform:1.9.5 -lc "sleep infinity")

docker cp "${TF_DIR}/." "$CID":/workspace/

docker exec "$CID" sh -lc '
  set -eux

  # Alpine base: use pip awscli (v1) — v2 needs glibc
  if command -v apk >/dev/null 2>&1; then
    apk add --no-cache curl jq python3 py3-pip unzip
    python3 -m pip install --no-cache-dir -U pip awscli
  elif command -v apt-get >/dev/null 2>&1; then
    apt-get update && apt-get install -y curl jq python3 python3-pip unzip && rm -rf /var/lib/apt/lists/*
    python3 -m pip install --no-cache-dir -U pip awscli
  fi

  cd /workspace

  BACKEND_BUCKET="${TF_STATE_BUCKET}"
  LOCK_TABLE="${TF_LOCK_TABLE}"
  STATE_KEY="eks/${DEPLOY_ENV}/terraform.tfstate"

  # Ensure backend bucket & DynamoDB lock table exist (idempotent)
  if ! aws s3api head-bucket --bucket "$BACKEND_BUCKET" 2>/dev/null; then
    if [ "${AWS_REGION}" = "us-east-1" ]; then
      aws s3api create-bucket --bucket "$BACKEND_BUCKET"
    else
      aws s3api create-bucket --bucket "$BACKEND_BUCKET" --create-bucket-configuration LocationConstraint="${AWS_REGION}"
    fi
    aws s3api put-bucket-versioning --bucket "$BACKEND_BUCKET" --versioning-configuration Status=Enabled
    aws s3api put-bucket-encryption --bucket "$BACKEND_BUCKET" --server-side-encryption-configuration "{\"Rules\":[{\"ApplyServerSideEncryptionByDefault\":{\"SSEAlgorithm\":\"AES256\"}}]}"
  fi

  if ! aws dynamodb describe-table --table-name "$LOCK_TABLE" >/dev/null 2>&1; then
    aws dynamodb create-table \
      --table-name "$LOCK_TABLE" \
      --attribute-definitions AttributeName=LockID,AttributeType=S \
      --key-schema AttributeName=LockID,KeyType=HASH \
      --billing-mode PAY_PER_REQUEST
    aws dynamodb wait table-exists --table-name "$LOCK_TABLE"
  fi

  # Init with explicit backend config so each DEPLOY_ENV has its own state object
  terraform init -input=false -upgrade \
    -backend-config="bucket=${BACKEND_BUCKET}" \
    -backend-config="key=${STATE_KEY}" \
    -backend-config="region=${AWS_REGION}" \
    -backend-config="dynamodb_table=${LOCK_TABLE}" \
    -backend-config="encrypt=true"

  # Select/create Terraform workspace (drives cluster name suffix)
  terraform workspace select "${DEPLOY_ENV}" || terraform workspace new "${DEPLOY_ENV}"

  # Tighten public API access to this runner"s egress IP (override default 0.0.0.0/0)
  MYIP="$(curl -s https://checkip.amazonaws.com | tr -d \" \\n\\r\")"
  export TF_VAR_cluster_endpoint_public_access_cidrs='"'"'["'"'"'"${MYIP}"'"'"/32"]'"'"'

  terraform validate
  terraform apply -auto-approve -input=false
'

docker rm -f "$CID" || true
'''
        }
      }
    }

    stage('DVC pull (from S3)') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
          sh '''#!/usr/bin/env sh
set -eux

CID=$(docker run -d \
  --entrypoint sh \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN \
  -e AWS_REGION -e AWS_DEFAULT_REGION="${AWS_REGION}" \
  python:3.11-slim \
  -lc "sleep infinity")

docker cp . "$CID":/workspace

docker exec "$CID" sh -lc '
  set -e
  apt-get update && apt-get install -y --no-install-recommends git curl && rm -rf /var/lib/apt/lists/*
  python -m pip install --no-cache-dir -U pip
  python -m pip install --no-cache-dir "dvc[s3]"
  cd /workspace
  dvc pull
'

docker cp "$CID":/workspace/. "$PWD"
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
    python3 -m pip install --no-cache-dir -U pip awscli

    ECR_HOST='${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com'
    ECR_URL=\"${ECR_HOST}/${ECR_REPO}\"

    aws ecr describe-repositories --repository-names '${ECR_REPO}' --region '${AWS_REGION}' >/dev/null 2>&1 || \
      aws ecr create-repository --repository-name '${ECR_REPO}' --region '${AWS_REGION}' >/dev/null

    eval \$(aws ecr get-login --region '${AWS_REGION}' --no-include-email)

    docker build -t '${ECR_REPO}:${IMAGE_TAG}' .
    docker tag  '${ECR_REPO}:${IMAGE_TAG}' \"${ECR_URL}:${IMAGE_TAG}\"
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
set -eux
IMG="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}"
sed "s|IMAGE_PLACEHOLDER|$IMG|g" "${K8S_MANIFEST}" > /tmp/deploy.yaml
ls -l /tmp/deploy.yaml
'''

          sh '''#!/usr/bin/env sh
set -eux
docker run --rm \
  --entrypoint bash \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN -e AWS_REGION \
  -e EKS_CLUSTER_NAME="${BASE_CLUSTER_NAME}-${DEPLOY_ENV}" \
  amazonlinux:2023 \
  -lc "
    set -e
    dnf -y install tar gzip curl unzip shadow-utils

    curl -L -o /usr/local/bin/kubectl \"https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl\"
    chmod +x /usr/local/bin/kubectl

    curl -sSL 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o '/tmp/awscliv2.zip'
    unzip -q /tmp/awscliv2.zip -d /tmp
    /tmp/aws/install -i /opt/aws-cli -b /usr/local/bin

    aws eks update-kubeconfig --region '${AWS_REGION}' --name \"${EKS_CLUSTER_NAME}\" --alias \"${EKS_CLUSTER_NAME}\"
    kubectl cluster-info

    kubectl wait --for=condition=Ready node --all --timeout=600s || true
    kubectl apply -f -
    kubectl get pods -A
  " < /tmp/deploy.yaml
'''
        }
      }
    }

  }
}
