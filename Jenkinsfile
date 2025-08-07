pipeline {
  agent any

  /************************************************************
   * Global settings – adjust only the few values below.
   ***********************************************************/
  environment {
    AWS_ACCOUNT_ID   = '286549082538'
    AWS_REGION       = 'eu-north-1'
    ECR_REPO         = 'my-repo'
    EKS_CLUSTER_NAME = 'ml-app-cluster'
    K8S_NAMESPACE    = 'prod'        // will be deployed to fp-prod Fargate profile
    IMAGE_TAG        = 'latest'

    VENV_DIR = 'venv'
    TOOL_DIR = "${WORKSPACE}/bin"
    PATH     = "${TOOL_DIR}:${env.PATH}"   /* makes aws/eksctl/kubectl visible */
  }

  stages {

    /*--------------------------------------------------------*/
    stage('Checkout') {
      steps { checkout scm }        // default: pull master with github-token creds
    }

    /*--------------------------------------------------------*/
    stage('Install CLI tooling (aws/eksctl/kubectl)') {
      steps {
        sh '''#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$TOOL_DIR"; export PATH="$TOOL_DIR:$PATH"

if ! command -v aws >/dev/null; then
  curl -sSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscli.zip
  unzip -qq /tmp/awscli.zip -d /tmp
  /tmp/aws/install -i /tmp/aws-cli -b "$TOOL_DIR"
fi

if ! command -v eksctl >/dev/null; then
  curl -sSL https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_Linux_amd64.tar.gz \
  | tar -xz -C "$TOOL_DIR"
fi

if ! command -v kubectl >/dev/null; then
  curl -sSL "https://dl.k8s.io/release/$(curl -sSL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
  -o "$TOOL_DIR/kubectl"
  chmod +x "$TOOL_DIR/kubectl"
fi
'''
      }
    }

    /*--------------------------------------------------------*/
    stage('Python venv & deps') {
      steps {
        sh '''#!/usr/bin/env bash
set -euo pipefail
python -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -e .
pip install dvc
'''
      }
    }

    /*--------------------------------------------------------*/
    stage('DVC pull') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
          sh '''#!/usr/bin/env bash
set -euo pipefail
source "$VENV_DIR/bin/activate"
export AWS_DEFAULT_REGION="$AWS_REGION"
dvc pull
'''
        }
      }
    }

    /*--------------------------------------------------------*/
    stage('Provision AWS (lightweight)') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
          sh '''#!/usr/bin/env bash
set -euo pipefail
export PATH="$TOOL_DIR:$PATH"

################ 1) ECR #################################################
aws ecr describe-repositories                 \
      --repository-names "$ECR_REPO"          \
      --region "$AWS_REGION" >/dev/null 2>&1  \
  || aws ecr create-repository                \
      --repository-name "$ECR_REPO"           \
      --image-scanning-configuration scanOnPush=true

################ 2) EKS control-plane only ################################
if ! aws eks describe-cluster --name "$EKS_CLUSTER_NAME" --region "$AWS_REGION" >/dev/null 2>&1 ; then
  echo "[eksctl] creating control-plane (no nodegroups)…"
  eksctl create cluster --name "$EKS_CLUSTER_NAME" --region "$AWS_REGION" --without-nodegroup
fi

################ 3) Fargate profile #######################################
if ! aws eks describe-fargate-profile                     \
        --cluster-name "$EKS_CLUSTER_NAME"                \
        --fargate-profile-name "fp-$K8S_NAMESPACE"        \
        --region "$AWS_REGION" >/dev/null 2>&1 ; then
  eksctl create fargateprofile                            \
        --cluster   "$EKS_CLUSTER_NAME"                   \
        --name      "fp-$K8S_NAMESPACE"                   \
        --namespace "$K8S_NAMESPACE"
fi
'''
        }
      }
    }

//     /*--------------------------------------------------------*/
//     stage('Build & push image') {
//       steps {
//         withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
//           script {
//             def accountId = sh(script: 'aws sts get-caller-identity --query Account --output text', returnStdout: true).trim()
//             def ecrUrl    = "${accountId}.dkr.ecr.${env.AWS_REGION}.amazonaws.com/${env.ECR_REPO}"

//             withEnv(["ECR_URL=${ecrUrl}"]) {
//               sh '''#!/usr/bin/env bash
// set -euo pipefail
// aws ecr get-login-password --region "$AWS_REGION" \
//   | docker login --username AWS --password-stdin "$ECR_URL"

// docker build -t "$ECR_REPO:$IMAGE_TAG" .
// docker tag  "$ECR_REPO:$IMAGE_TAG" "$ECR_URL:$IMAGE_TAG"
// docker push "$ECR_URL:$IMAGE_TAG"
// '''
//             }
//           }
//         }
//       }
//     }

    stage('Ensure namespace exists') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding',
                          credentialsId: 'aws-token']]) {
          sh '''#!/usr/bin/env bash
set -euo pipefail
export PATH="$TOOL_DIR:$PATH"

aws eks update-kubeconfig --region "$AWS_REGION" --name "$EKS_CLUSTER_NAME"

kubectl get namespace "$K8S_NAMESPACE" >/dev/null 2>&1 \
  || kubectl create namespace "$K8S_NAMESPACE"
'''
        }
      }
    }

    /*--------------------------------------------------------*/
   stage('Deploy to EKS (Fargate)') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding',
                          credentialsId: 'aws-token']]) {
          script {
            def accountId = sh(
              script: 'aws sts get-caller-identity --query Account --output text',
              returnStdout: true
            ).trim()
            def fullImage = "${accountId}.dkr.ecr.${env.AWS_REGION}.amazonaws.com/${env.ECR_REPO}:${IMAGE_TAG}"

            withEnv(["FULL_IMAGE=${fullImage}"]) {
              sh '''#!/usr/bin/env bash
set -euo pipefail
export PATH="$TOOL_DIR:$PATH"

aws eks update-kubeconfig --region "$AWS_REGION" --name "$EKS_CLUSTER_NAME"

# Render manifest and apply it into the (now-existing) namespace
sed "s|__IMAGE__|$FULL_IMAGE|g" k8s/deployment.yaml \
| kubectl apply -f -
'''
            }
          }
        }
      }
    }
  }
}
