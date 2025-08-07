pipeline {
    agent any

    environment {
        // ------- paths & versions -------
        AWS_CLI_VERSION   = '2.16.17'          // pin a recent AWS CLI v2
        EKSCTL_VERSION    = '0.183.0'          // pin eksctl
        AWS_CLI_PATH      = '/usr/local/bin'   // where we drop the binaries

        // --------- project / AWS ----------
        VENV_DIR          = 'venv'
        AWS_REGION        = 'eu-north-1'
        AWS_ACCOUNT_ID    = '286549082538'
        ECR_REPO          = 'my-repo'
        EKS_CLUSTER_NAME  = 'ml-app-cluster'
        IMAGE_TAG         = "${env.BUILD_NUMBER}"   // unique tag per build
    }

    stages {

        /* -------------------------
           0. Ensure CLI prerequisites
           ------------------------- */
        stage('Install AWS CLI & eksctl') {
            steps {
                sh '''
                  set -e
                  # install AWS CLI if missing
                  if ! command -v aws >/dev/null 2>&1; then
                      echo "Installing AWS CLI ${AWS_CLI_VERSION} ..."
                      curl -Ls "https://awscli.amazonaws.com/awscli-exe-linux-x86_64-${AWS_CLI_VERSION}.zip" -o /tmp/awscliv2.zip
                      unzip -q /tmp/awscliv2.zip -d /tmp
                      sudo /tmp/aws/install -u -i /usr/local/aws-cli -b ${AWS_CLI_PATH}
                      rm -rf /tmp/aws* /tmp/awscliv2.zip
                  fi

                  # install eksctl if missing
                  if ! command -v eksctl >/dev/null 2>&1; then
                      echo "Installing eksctl ${EKSCTL_VERSION} ..."
                      curl -Ls "https://github.com/eksctl-io/eksctl/releases/download/v${EKSCTL_VERSION}/eksctl_Linux_amd64.tar.gz" \
                        | sudo tar -xz -C ${AWS_CLI_PATH}
                      sudo chmod +x ${AWS_CLI_PATH}/eksctl
                  fi

                  # final sanity check
                  aws --version
                  eksctl version
                '''
            }
        }

        /* -------------------- existing stages -------------------- */

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

        stage('Provision AWS infra') {
            steps {
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
                    sh """
                        echo Ensuring ECR repo exists…
                        if ! aws ecr describe-repositories --repository-names ${ECR_REPO} --region ${AWS_REGION} >/dev/null 2>&1; then
                          aws ecr create-repository --repository-name ${ECR_REPO} --image-scanning-configuration scanOnPush=true --region ${AWS_REGION}
                        fi
                    """
                }
            }
        }

        stage('Build & push image') {
            steps {
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
                    script {
                        def ecrUrl = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
                        sh """
                            aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ecrUrl}
                            docker build -t ${ECR_REPO}:${IMAGE_TAG} .
                            docker tag  ${ECR_REPO}:${IMAGE_TAG} ${ecrUrl}:${IMAGE_TAG}
                            docker push ${ecrUrl}:${IMAGE_TAG}
                        """
                    }
                }
            }
        }

        stage('Deploy to EKS') {
            steps {
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
                    sh """
                        aws eks update-kubeconfig --region ${AWS_REGION} --name ${EKS_CLUSTER_NAME}
                        sed "s|IMAGE_PLACEHOLDER|${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}|" k8s/deployment.yaml | \
                          kubectl apply -f -
                    """
                }
            }
        }
    }
}
