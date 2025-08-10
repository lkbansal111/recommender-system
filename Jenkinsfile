pipeline {
    agent any

    environment {
        VENV_DIR          = 'venv'

        /* ── AWS-specific settings ───────────────────────────────────── */
        AWS_ACCOUNT_ID    = '286549082538'         // <-- your AWS account
        AWS_REGION        = 'eu-north-1'           // <-- preferred region
        ECR_REPO          = 'my-repo'              // <-- ECR repo name (matches terraform.tfvars)
        EKS_CLUSTER_NAME  = 'ml-app-cluster'       // <-- EKS cluster name (from module: ml-app-cluster)
        AWS_CLI_PATH      = '/usr/local/bin'       // path where aws cli is installed
        IMAGE_TAG         = 'latest'
    }

    stages {

        /* ── Install Python inside jenkins-dind ─────────────────────── */
        stage('Install Python (jenkins-dind)') {
            steps {
                sh """
                    docker exec -u root -it jenkins-dind bash
                    apt update -y
                    apt install -y python3
                    python3 --version
                    ln -s /usr/bin/python3 /usr/bin/python
                    python --version
                    apt install -y python3-pip
                    apt install -y python3-venv
                    exit
                """
            }
        }

        /* ── Install kubectl and AWS CLI (NOT gcloud) ───────────────── */
        stage('Install kubectl & AWS CLI (jenkins-dind)') {
            steps {
                sh """
                    docker exec -u root -it jenkins-dind bash
                    apt-get update
                    apt-get install -y curl unzip apt-transport-https ca-certificates gnupg

                    # Install kubectl (latest stable)
                    curl -LO "https://storage.googleapis.com/kubernetes-release/release/\\$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl"
                    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
                    kubectl version --client

                    # Install AWS CLI v2
                    curl -sSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip"
                    unzip -o /tmp/awscliv2.zip -d /tmp
                    /tmp/aws/install --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli --update
                    aws --version
                    exit
                """
            }
        }

        /* ── Grant Docker permission to Jenkins user ─────────────────── */
        stage('Grant Docker permission to jenkins user') {
            steps {
                sh """
                    docker exec -u root -it jenkins-dind bash
                    groupadd docker
                    usermod -aG docker jenkins
                    usermod -aG root jenkins
                    exit
                    docker restart jenkins-dind
                """
            }
        }

        stage('Clone from GitHub') {
            steps {
                echo 'Cloning repository …'
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

        /* NEW: Provision infra with Terraform */
        stage('Provision AWS (Terraform)') {
            steps {
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-token']]) {
                    dir('infra') {
                        sh """
                            export AWS_DEFAULT_REGION=${AWS_REGION}
                            terraform init -input=false
                            terraform apply -auto-approve -input=false
                        """
                    }
                }
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

                        # Template the image into the manifest before apply
                        sed -i "s|IMAGE_PLACEHOLDER|${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}|g" deployment.yaml

                        kubectl apply -f deployment.yaml
                    """
                }
            }
        }
    }
}
