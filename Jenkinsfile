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

        stage('Build & Push Docker Image to ECR') {
            steps {
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
                    script {
                        def accountId = sh(script: "aws sts get-caller-identity --query Account --output text", returnStdout: true).trim()
                        def ecrUrl = "${accountId}.dkr.ecr.${env.AWS_REGION}.amazonaws.com/${env.ECR_REPO}"

                        sh """
                            export PATH=\$PATH:${AWS_CLI_PATH}
                            aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ecrUrl}
                            docker build -t ${env.ECR_REPO}:${IMAGE_TAG} .
                            docker tag ${env.ECR_REPO}:${IMAGE_TAG} ${ecrUrl}:${IMAGE_TAG}
                            docker push ${ecrUrl}:${IMAGE_TAG}
                        """
                    }
                }
            }
        }

        stage('Deploy to EKS') {
            steps {
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
                    echo 'Updating kubeconfig & applying manifests …'
                    sh """
                        export PATH=\$PATH:${AWS_CLI_PATH}
                        aws eks update-kubeconfig --region ${AWS_REGION} --name ${EKS_CLUSTER_NAME}

                        # (Optional) substitute image tag into manifest before apply
                        # sed -i "s|IMAGE_PLACEHOLDER|${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}|g" deployment.yaml

                        kubectl apply -f deployment.yaml
                    """
                }
            }
        }
    }
}
