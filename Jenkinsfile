pipeline {
  agent any
  options { timestamps() }

  environment {
    AWS_ACCOUNT_ID   = '286549082538'
    AWS_REGION       = 'eu-east-1'
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



stage('Provision AWS (Terraform)') {
  steps {
    withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
      sh '''#!/usr/bin/env sh
set -eux

# (Optional) Purane atke terraform containers cleanup
docker ps -q --filter "ancestor=hashicorp/terraform:1.9.5" | xargs -r docker rm -f || true

# 1) Terraform container
CID=$(docker run -d \
  --entrypoint sh \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN \
  -e AWS_REGION -e AWS_DEFAULT_REGION="${AWS_REGION}" \
  -e EKS_CLUSTER_NAME="${EKS_CLUSTER_NAME}" \
  hashicorp/terraform:1.9.5 -lc "sleep infinity")

# 2) TF files copy
docker cp "${TF_DIR}/." "$CID":/workspace/

# 3) Container me awscli install (NO pip) + pre-import + apply
docker exec "$CID" sh -lc '
  set -eux

  # awscli via package manager (Alpine/Debian both)
  if command -v apk >/dev/null 2>&1; then
    apk add --no-cache aws-cli curl jq
  elif command -v apt-get >/dev/null 2>&1; then
    apt-get update && apt-get install -y awscli curl jq && rm -rf /var/lib/apt/lists/*
  else
    echo "No supported package manager to install awscli" >&2
    exit 1
  fi

  cd /workspace
  terraform init -input=false -upgrade
  terraform validate

  # --- preflight: agar CW log group pehle se hai to import to state ---
  LG="/aws/eks/${EKS_CLUSTER_NAME}/cluster"
  if aws logs describe-log-groups --region "${AWS_REGION}" \
       --log-group-name-prefix "$LG" \
       | jq -e ".logGroups[] | select(.logGroupName==\\"$LG\\")" > /dev/null; then
    echo "Log group $LG exists -> importing into Terraform state"
    terraform import -input=false "module.eks.aws_cloudwatch_log_group.this[0]" "$LG" || true
  fi

  terraform apply -auto-approve -input=false
'

# 4) cleanup
docker rm -f "$CID" || true
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
