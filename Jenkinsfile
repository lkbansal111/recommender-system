pipeline {
  agent any

  options { timestamps() }

  environment {
    // ---- Global settings ----
    VENV_DIR         = 'venv'

    // ---- AWS ----
    AWS_ACCOUNT_ID   = '286549082538'     // your AWS account
    AWS_REGION       = 'eu-north-1'
    ECR_REPO         = 'my-repo'
    EKS_CLUSTER_NAME = 'ml-app-cluster'
    IMAGE_TAG        = 'latest'
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

    stage('Provision AWS (Terraform)') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
          script {
            docker.image('hashicorp/terraform:1.9.5').inside {
              dir('infra') {
                sh '''
                  set -e
                  export AWS_DEFAULT_REGION="$AWS_REGION"
                  terraform --version
                  terraform init -input=false
                  terraform apply -auto-approve -input=false
                '''
              }
            }
          }
        }
      }
    }

    stage('Create virtualenv') {
      steps {
        script {
          docker.image('python:3.11-slim').inside {
            sh '''
              set -e
              python -m venv "$VENV_DIR"
              . "$VENV_DIR/bin/activate"
              pip install --upgrade pip
              pip install -e .
            '''
          }
        }
      }
    }

    stage('DVC pull (from S3)') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
          script {
            docker.image('python:3.11-slim').inside {
              sh '''
                set -e
                # DVC + S3
                pip install --no-cache-dir --upgrade pip
                pip install --no-cache-dir "dvc[s3]"
                export AWS_DEFAULT_REGION="$AWS_REGION"
                dvc pull
              '''
            }
          }
        }
      }
    }

    stage('Build & Push Docker Image to ECR (Kaniko)') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
          script {
            def ecrUrl = "${env.AWS_ACCOUNT_ID}.dkr.ecr.${env.AWS_REGION}.amazonaws.com/${env.ECR_REPO}"

            // Kaniko container; disable entrypoint so we can run /bin/sh
            docker.image('gcr.io/kaniko-project/executor:latest').inside('--entrypoint=""') {
              sh """
                set -e
                /kaniko/executor \
                  --context="${WORKSPACE}" \
                  --dockerfile="${WORKSPACE}/Dockerfile" \
                  --destination="${ecrUrl}:${IMAGE_TAG}" \
                  --snapshotMode=redo \
                  --use-new-run \
                  --cache=true
              """
            }
          }
        }
      }
    }

    stage('Deploy to EKS') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
          script {
            docker.image('amazon/aws-cli:2').inside {
              sh '''
                set -e
                # Install kubectl (latest stable)
                curl -L -o /usr/local/bin/kubectl \
                  "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
                chmod +x /usr/local/bin/kubectl
                kubectl version --client

                # Update kubeconfig & deploy
                aws eks update-kubeconfig --region "$AWS_REGION" --name "$EKS_CLUSTER_NAME"

                sed -i "s|IMAGE_PLACEHOLDER|$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG|g" deployment.yaml
                kubectl apply -f deployment.yaml
              '''
            }
          }
        }
      }
    }
  }
}
