pipeline {
    agent any

    /* ------------------------------------------------------------------ */
    environment {
        /* General */
        VENV_DIR         = 'venv'
        IMAGE_TAG        = 'latest'

        /* AWS */
        AWS_ACCOUNT_ID   = '286549082538'      // <-- your account
        AWS_REGION       = 'eu-north-1'
        ECR_REPO         = 'my-repo'
        EKS_CLUSTER_NAME = 'ml-app-cluster'

        /* Paths – tools will be downloaded into TOOL_DIR */
        TOOL_DIR = "${WORKSPACE}/bin"
        PATH     = "${TOOL_DIR}:${env.PATH}"
    }

    /* ================================================================== */
    stages {

        /* -------------------------------------------------------------- */
        stage('Checkout') {
            steps {
                checkout scmGit(
                    branches: [[name: '*/master']],
                    userRemoteConfigs: [[
                        url: 'https://github.com/lkbansal111/recommender-system.git',
                        credentialsId: 'github-token'
                    ]]
                )
            }
        }

        /* -------------------------------------------------------------- */
        stage('Install aws / eksctl / kubectl (if missing)') {
            steps {
                sh '''
set -euo pipefail
mkdir -p "$TOOL_DIR"
export PATH="$TOOL_DIR:$PATH"

command -v aws     >/dev/null || {
  curl -sSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/aws.zip
  unzip -qq /tmp/aws.zip -d /tmp && /tmp/aws/install -i /tmp/aws-cli -b "$TOOL_DIR"
}
command -v eksctl  >/dev/null || {
  curl -sSL https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_Linux_amd64.tar.gz | \
  tar -xz -C "$TOOL_DIR"
}
command -v kubectl >/dev/null || {
  curl -sSL "https://dl.k8s.io/release/$(curl -sSL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
       -o "$TOOL_DIR/kubectl" && chmod +x "$TOOL_DIR/kubectl"
}
'''
            }
        }

        /* -------------------------------------------------------------- */
        stage('Python venv & deps') {
            steps {
                sh '''
python -m venv "$VENV_DIR"
. "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -e .
pip install dvc
'''
            }
        }

        /* -------------------------------------------------------------- */
        stage('DVC pull') {
            steps {
                withCredentials([[
                    $class: 'AmazonWebServicesCredentialsBinding',
                    credentialsId: 'aws-token']]) {
                    sh '''
. "$VENV_DIR/bin/activate"
export AWS_DEFAULT_REGION="$AWS_REGION"
dvc pull
'''
                }
            }
        }

        /* -------------------------------------------------------------- */
        stage('Provision ⬆  AWS (lightweight)') {
            steps {
                withCredentials([[
                    $class: 'AmazonWebServicesCredentialsBinding',
                    credentialsId: 'aws-token']]) {
                    sh '''
set -euo pipefail
export PATH="$TOOL_DIR:$PATH"

# ---------- ECR ---------------------------------------------------
aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$AWS_REGION" || \
aws ecr create-repository       --repository-name "$ECR_REPO" --region "$AWS_REGION" \
                               --image-scanning-configuration scanOnPush=true

# ---------- EKS (Fargate-only, finishes in ~6-7 min) --------------
if ! aws eks describe-cluster --name "$EKS_CLUSTER_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
  eksctl create cluster \
        --name    "$EKS_CLUSTER_NAME" \
        --region  "$AWS_REGION"      \
        --version 1.32                \
        --fargate                     \
        --tags   project=ml-demo
fi
'''
                }
            }
        }

        /* -------------------------------------------------------------- */
        stage('Build & push image') {
            steps {
                withCredentials([[
                    $class: 'AmazonWebServicesCredentialsBinding',
                    credentialsId: 'aws-token']]) {
                    script {
                        def accountId = sh(script: 'aws sts get-caller-identity --query Account --output text', returnStdout: true).trim()
                        def ecrUrl   = "${accountId}.dkr.ecr.${env.AWS_REGION}.amazonaws.com/${env.ECR_REPO}"

                        sh """
export PATH="$TOOL_DIR:$PATH"
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ecrUrl}

docker build -t ${ECR_REPO}:${IMAGE_TAG} .
docker tag  ${ECR_REPO}:${IMAGE_TAG} ${ecrUrl}:${IMAGE_TAG}
docker push ${ecrUrl}:${IMAGE_TAG}
"""
                    }
                }
            }
        }

        /* -------------------------------------------------------------- */
        stage('Deploy to EKS (Fargate)') {
            steps {
                withCredentials([[
                    $class: 'AmazonWebServicesCredentialsBinding',
                    credentialsId: 'aws-token']]) {
                    script {
                        def accountId = sh(script: 'aws sts get-caller-identity --query Account --output text', returnStdout: true).trim()
                        def fullImage = "${accountId}.dkr.ecr.${env.AWS_REGION}.amazonaws.com/${env.ECR_REPO}:${IMAGE_TAG}"

                        sh """
export PATH="$TOOL_DIR:$PATH"
aws eks update-kubeconfig --region ${AWS_REGION} --name ${EKS_CLUSTER_NAME}

sed "s|__IMAGE__|${fullImage}|g" k8s/deployment.yaml | kubectl apply -f -
"""
                    }
                }
            }
        }
    }
}
