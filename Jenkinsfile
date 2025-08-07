pipeline {
    agent any

    environment {
        VENV_DIR          = 'venv'

        /* ── AWS-specific settings ───────────────────────────────────── */
        AWS_ACCOUNT_ID    = '286549082538'        // <-- your AWS account
        AWS_REGION        = 'eu-north-1'          // <-- preferred region
        ECR_REPO          = 'my-repo'              // <-- ECR repo name
        EKS_CLUSTER_NAME  = 'ml-app-cluster'       // <-- EKS cluster name
        AWS_CLI_PATH      = '/usr/local/bin'       // path where aws cli is installed
        IMAGE_TAG         = 'latest'
        SA_NAME           = 'ml-app-sa'               // service account for IRSA
        K8S_NAMESPACE    = 'prod'          //  <--- NEW – must match manifest
        TOOL_DIR = "${WORKSPACE}/bin"
        PATH     = "${TOOL_DIR}:${env.PATH}"
    }

    stages {

        stage('Clone from GitHub') {
            steps {
                echo 'Cloning repository …'
                checkout scmGit(
                    branches: [[name: '*/master']],
                    extensions: [],
                    userRemoteConfigs: [[
                        credentialsId: 'github-token',
                        url: 'https://github.com/lkbansal111/recommender-system.git'
                    ]]
                )
            }
        }

stage('Install AWS CLI + eksctl + kubectl') {
    steps {
        sh '''
# run the whole block under bash:
bash -euo pipefail -c "
  TOOL_DIR=\\"$WORKSPACE/bin\\"
  mkdir -p \\"$TOOL_DIR\\"
  export PATH=\\"$TOOL_DIR:$PATH\\"

  if ! command -v aws >/dev/null; then
    echo '[tooling] installing AWS CLI v2 …'
    curl -sSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscli.zip
    unzip -qq /tmp/awscli.zip -d /tmp
    /tmp/aws/install -i /tmp/aws-cli -b \\"$TOOL_DIR\\"
  fi

  if ! command -v eksctl >/dev/null; then
    echo '[tooling] installing eksctl …'
    curl -sSL https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_Linux_amd64.tar.gz | \
      tar -xz -C \\"$TOOL_DIR\\"
  fi

  if ! command -v kubectl >/dev/null; then
    echo '[tooling] installing kubectl …'
    curl -sSL \"https://dl.k8s.io/release/$(curl -sSL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl\" \
         -o \\"$TOOL_DIR/kubectl\\"
    chmod +x \\"$TOOL_DIR/kubectl\\"
  fi
"
'''
    }
}



        stage('Create virtualenv') {
            steps {
                echo 'Creating Python virtual environment …'
                sh """
                    python -m venv ${VENV_DIR}
                    . ${VENV_DIR}/bin/activate
                    pip install --upgrade pip
                    pip install -e .
                    pip install dvc
                """
            }
        }

        stage('DVC pull (from S3)') {
            steps {
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
                    echo 'Fetching data artifacts with DVC …'
                    sh """
                        . ${VENV_DIR}/bin/activate
                        export AWS_DEFAULT_REGION=${AWS_REGION}
                        dvc pull
                    """
                }
            }
        }

    stage('Cleanup orphaned EKS cluster') {
      steps {
        withCredentials([[
          $class: 'AmazonWebServicesCredentialsBinding',
          credentialsId: 'aws-token'          // <- your Jenkins AWS creds ID
        ]]) {
          sh '''
            #!/usr/bin/env bash
            set +e                                       # don’t fail if cluster absent
            eksctl get cluster --name "$EKS_CLUSTER_NAME" --region "$AWS_REGION" >/dev/null 2>&1
            if [ $? -eq 0 ]; then
              echo "[cleanup] Old cluster exists – deleting…"
              eksctl delete cluster --name "$EKS_CLUSTER_NAME" --region "$AWS_REGION" --wait
              echo "[cleanup] Delete finished."
            else
              echo "[cleanup] No existing cluster – skipping."
            fi
            set -e
          '''
        }
      }
    }

   /* ------------------------------------------------------------------ */
    stage('Provision AWS infra') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
          sh """
            export PATH=\$PATH:${AWS_CLI_PATH}

            ############### ECR ##########################################
            echo "Ensuring ECR repo exists…"
            aws ecr describe-repositories                        \\
              --repository-names ${ECR_REPO} --region ${AWS_REGION} || \\
            aws ecr create-repository                            \\
              --repository-name ${ECR_REPO}                      \\
              --image-scanning-configuration scanOnPush=true     \\
              --region ${AWS_REGION}

            ############### EKS #########################################
            echo "Ensuring EKS cluster exists…"
            if ! aws eks describe-cluster --name ${EKS_CLUSTER_NAME} --region ${AWS_REGION} >/dev/null 2>&1; then
              echo "Creating EKS cluster (this can take ~15 min)…"
              eksctl create cluster --name ${EKS_CLUSTER_NAME} --region ${AWS_REGION} --nodes 2
            fi

            ############### OIDC & IRSA ###############################
            echo "Associating OIDC provider (idempotent)…"
            eksctl utils associate-iam-oidc-provider --cluster ${EKS_CLUSTER_NAME} --approve

            # Minimal policy example: replace with anything your app needs
            POLICY_NAME=${SA_NAME}-policy
            POLICY_ARN=\$(aws iam list-policies --query "Policies[?PolicyName=='\$POLICY_NAME'].Arn" --output text)
            if [ -z "\$POLICY_ARN" ]; then
              cat > /tmp/sa_policy.json <<'EOF'
            {
              "Version": "2012-10-17",
              "Statement": [
                { "Effect": "Allow", "Action": [ "s3:ListBucket" ], "Resource": "*" }
              ]
            }
EOF
              POLICY_ARN=\$(aws iam create-policy --policy-name \$POLICY_NAME --policy-document file:///tmp/sa_policy.json --query Policy.Arn --output text)
            fi

            eksctl create iamserviceaccount                           \\
              --name      ${SA_NAME}                                  \\
              --namespace ${K8S_NAMESPACE}                            \\
              --cluster   ${EKS_CLUSTER_NAME}                         \\
              --attach-policy-arn \$POLICY_ARN                        \\
              --approve                                               \\
              --override-existing-serviceaccounts
          """
        }
      }
    }

    /* ------------------------------------------------------------------ */
    stage('Build & push image') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
          script {
            def accountId = sh(script: "aws sts get-caller-identity --query Account --output text", returnStdout: true).trim()
            def ecrUrl    = "${accountId}.dkr.ecr.${env.AWS_REGION}.amazonaws.com/${env.ECR_REPO}"

            sh """
              export PATH=\$PATH:${AWS_CLI_PATH}
              aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ecrUrl}

              docker build -t ${env.ECR_REPO}:${IMAGE_TAG} .
              docker tag  ${env.ECR_REPO}:${IMAGE_TAG} ${ecrUrl}:${IMAGE_TAG}
              docker push ${ecrUrl}:${IMAGE_TAG}
            """
          }
        }
      }
    }

    /* ------------------------------------------------------------------ */
    stage('Deploy to EKS') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
          script {
            def accountId = sh(script: "aws sts get-caller-identity --query Account --output text", returnStdout: true).trim()
            def fullImage = "${accountId}.dkr.ecr.${env.AWS_REGION}.amazonaws.com/${env.ECR_REPO}:${IMAGE_TAG}"
            sh """
              export PATH=\$PATH:${AWS_CLI_PATH}
              aws eks update-kubeconfig --region ${AWS_REGION} --name ${EKS_CLUSTER_NAME}

              # inject the freshly built image & SA into the manifest on the fly
              sed -e "s|__IMAGE__|${fullImage}|g"         \\
                  -e "s|__SERVICE_ACCOUNT__|${SA_NAME}|g" \\
                  k8s/deployment.yaml | kubectl apply -f -
            """
          }
        }
      }
    }
  }
}