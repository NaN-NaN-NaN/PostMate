#!/bin/bash

###############################################################################
# PostMate Backend - AWS Deployment Script
#
# Purpose: Automated deployment to AWS using ECS Fargate, S3, DynamoDB
#
# Prerequisites:
#   - AWS CLI v2 installed and configured (aws configure)
#   - Docker installed
#   - jq installed (for JSON parsing)
#
# Usage:
#   ./deploy_aws.sh
#
# What this script does:
#   1. Creates S3 bucket for storage
#   2. Creates DynamoDB tables
#   3. Builds and pushes Docker image to ECR
#   4. Creates ECS cluster, task definition, and service
#   5. Creates EventBridge rule + Lambda for reminders
#   6. Outputs API endpoint URL
###############################################################################

set -e  # Exit on error

# Configuration
STACK_NAME="${STACK_NAME:-postmate-prod}"
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Resource names
S3_BUCKET="${STACK_NAME}-storage-${AWS_ACCOUNT_ID}"
ECR_REPO="${STACK_NAME}-app"
ECS_CLUSTER="${STACK_NAME}-cluster"
ECS_SERVICE="${STACK_NAME}-service"
ECS_TASK_FAMILY="${STACK_NAME}-task"

DYNAMODB_DOCUMENTS_TABLE="${STACK_NAME}-documents"
DYNAMODB_ANALYSES_TABLE="${STACK_NAME}-analyses"
DYNAMODB_CHATS_TABLE="${STACK_NAME}-chats"
DYNAMODB_REMINDERS_TABLE="${STACK_NAME}-reminders"

echo "=============================================="
echo "PostMate AWS Deployment"
echo "=============================================="
echo "Stack Name: $STACK_NAME"
echo "Region: $AWS_REGION"
echo "Account ID: $AWS_ACCOUNT_ID"
echo "=============================================="
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo "Checking prerequisites..."
if ! command_exists aws; then
    echo "ERROR: AWS CLI not found. Install from https://aws.amazon.com/cli/"
    exit 1
fi

if ! command_exists docker; then
    echo "ERROR: Docker not found. Install from https://docker.com"
    exit 1
fi

if ! command_exists jq; then
    echo "ERROR: jq not found. Install with: brew install jq (macOS) or apt-get install jq (Linux)"
    exit 1
fi

echo "✓ All prerequisites met"
echo ""

###############################################################################
# 1. CREATE S3 BUCKET
###############################################################################

echo "1. Creating S3 bucket..."

if aws s3 ls "s3://${S3_BUCKET}" 2>/dev/null; then
    echo "✓ S3 bucket already exists: ${S3_BUCKET}"
else
    if [ "$AWS_REGION" == "us-east-1" ]; then
        aws s3 mb "s3://${S3_BUCKET}" --region ${AWS_REGION}
    else
        aws s3 mb "s3://${S3_BUCKET}" --region ${AWS_REGION} --create-bucket-configuration LocationConstraint=${AWS_REGION}
    fi

    # Enable versioning
    aws s3api put-bucket-versioning \
        --bucket ${S3_BUCKET} \
        --versioning-configuration Status=Enabled

    # Enable encryption
    aws s3api put-bucket-encryption \
        --bucket ${S3_BUCKET} \
        --server-side-encryption-configuration '{
            "Rules": [{
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "AES256"
                }
            }]
        }'

    echo "✓ S3 bucket created: ${S3_BUCKET}"
fi

###############################################################################
# 2. CREATE DYNAMODB TABLES
###############################################################################

echo ""
echo "2. Creating DynamoDB tables..."

create_dynamodb_table() {
    local TABLE_NAME=$1
    local KEY_NAME=$2

    if aws dynamodb describe-table --table-name ${TABLE_NAME} --region ${AWS_REGION} 2>/dev/null; then
        echo "✓ Table already exists: ${TABLE_NAME}"
    else
        aws dynamodb create-table \
            --table-name ${TABLE_NAME} \
            --attribute-definitions AttributeName=${KEY_NAME},AttributeType=S \
            --key-schema AttributeName=${KEY_NAME},KeyType=HASH \
            --billing-mode PAY_PER_REQUEST \
            --region ${AWS_REGION} \
            --tags Key=Stack,Value=${STACK_NAME}

        echo "✓ Table created: ${TABLE_NAME}"
    fi
}

create_dynamodb_table ${DYNAMODB_DOCUMENTS_TABLE} "document_id"
create_dynamodb_table ${DYNAMODB_ANALYSES_TABLE} "analysis_id"
create_dynamodb_table ${DYNAMODB_CHATS_TABLE} "message_id"
create_dynamodb_table ${DYNAMODB_REMINDERS_TABLE} "reminder_id"

# Wait for tables to be active
echo "Waiting for tables to become active..."
aws dynamodb wait table-exists --table-name ${DYNAMODB_DOCUMENTS_TABLE} --region ${AWS_REGION}
echo "✓ All DynamoDB tables ready"

###############################################################################
# 3. CREATE ECR REPOSITORY AND PUSH IMAGE
###############################################################################

echo ""
echo "3. Building and pushing Docker image..."

# Create ECR repository
if aws ecr describe-repositories --repository-names ${ECR_REPO} --region ${AWS_REGION} 2>/dev/null; then
    echo "✓ ECR repository already exists: ${ECR_REPO}"
else
    aws ecr create-repository \
        --repository-name ${ECR_REPO} \
        --region ${AWS_REGION} \
        --tags Key=Stack,Value=${STACK_NAME}
    echo "✓ ECR repository created: ${ECR_REPO}"
fi

# Get ECR login
aws ecr get-login-password --region ${AWS_REGION} | \
    docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Build image
echo "Building Docker image..."
docker build -t ${ECR_REPO}:latest .

# Tag image
ECR_IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:latest"
docker tag ${ECR_REPO}:latest ${ECR_IMAGE_URI}

# Push image
echo "Pushing image to ECR..."
docker push ${ECR_IMAGE_URI}

echo "✓ Docker image pushed: ${ECR_IMAGE_URI}"

###############################################################################
# 4. CREATE IAM ROLES
###############################################################################

echo ""
echo "4. Creating IAM roles..."

# ECS Task Execution Role (for pulling images, logging)
TASK_EXECUTION_ROLE="${STACK_NAME}-task-execution-role"

if aws iam get-role --role-name ${TASK_EXECUTION_ROLE} 2>/dev/null; then
    echo "✓ Task execution role already exists"
else
    aws iam create-role \
        --role-name ${TASK_EXECUTION_ROLE} \
        --assume-role-policy-document '{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }' \
        --tags Key=Stack,Value=${STACK_NAME}

    aws iam attach-role-policy \
        --role-name ${TASK_EXECUTION_ROLE} \
        --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

    echo "✓ Task execution role created"
fi

# ECS Task Role (for application permissions: S3, DynamoDB, Textract, Bedrock)
TASK_ROLE="${STACK_NAME}-task-role"

if aws iam get-role --role-name ${TASK_ROLE} 2>/dev/null; then
    echo "✓ Task role already exists"
else
    aws iam create-role \
        --role-name ${TASK_ROLE} \
        --assume-role-policy-document '{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }' \
        --tags Key=Stack,Value=${STACK_NAME}

    # Create inline policy for application permissions
    aws iam put-role-policy \
        --role-name ${TASK_ROLE} \
        --policy-name ${STACK_NAME}-app-policy \
        --policy-document "{
            \"Version\": \"2012-10-17\",
            \"Statement\": [
                {
                    \"Effect\": \"Allow\",
                    \"Action\": [
                        \"s3:GetObject\",
                        \"s3:PutObject\",
                        \"s3:DeleteObject\",
                        \"s3:ListBucket\"
                    ],
                    \"Resource\": [
                        \"arn:aws:s3:::${S3_BUCKET}\",
                        \"arn:aws:s3:::${S3_BUCKET}/*\"
                    ]
                },
                {
                    \"Effect\": \"Allow\",
                    \"Action\": [
                        \"dynamodb:GetItem\",
                        \"dynamodb:PutItem\",
                        \"dynamodb:UpdateItem\",
                        \"dynamodb:DeleteItem\",
                        \"dynamodb:Query\",
                        \"dynamodb:Scan\"
                    ],
                    \"Resource\": [
                        \"arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DYNAMODB_DOCUMENTS_TABLE}\",
                        \"arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DYNAMODB_ANALYSES_TABLE}\",
                        \"arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DYNAMODB_CHATS_TABLE}\",
                        \"arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DYNAMODB_REMINDERS_TABLE}\"
                    ]
                },
                {
                    \"Effect\": \"Allow\",
                    \"Action\": [
                        \"textract:DetectDocumentText\",
                        \"textract:AnalyzeDocument\"
                    ],
                    \"Resource\": \"*\"
                },
                {
                    \"Effect\": \"Allow\",
                    \"Action\": [
                        \"bedrock:InvokeModel\"
                    ],
                    \"Resource\": \"arn:aws:bedrock:${AWS_REGION}::foundation-model/*\"
                }
            ]
        }"

    echo "✓ Task role created with app permissions"
fi

# Wait for roles to propagate
sleep 10

###############################################################################
# 5. CREATE ECS CLUSTER, TASK DEFINITION, AND SERVICE
###############################################################################

echo ""
echo "5. Creating ECS resources..."

# Create ECS cluster
if aws ecs describe-clusters --clusters ${ECS_CLUSTER} --region ${AWS_REGION} | grep -q "ACTIVE"; then
    echo "✓ ECS cluster already exists"
else
    aws ecs create-cluster \
        --cluster-name ${ECS_CLUSTER} \
        --region ${AWS_REGION} \
        --tags key=Stack,value=${STACK_NAME}
    echo "✓ ECS cluster created"
fi

# Register task definition
echo "Registering ECS task definition..."

TASK_DEF_JSON=$(cat <<EOF
{
  "family": "${ECS_TASK_FAMILY}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/${TASK_EXECUTION_ROLE}",
  "taskRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/${TASK_ROLE}",
  "containerDefinitions": [
    {
      "name": "postmate-app",
      "image": "${ECR_IMAGE_URI}",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "ENVIRONMENT", "value": "production"},
        {"name": "AWS_REGION", "value": "${AWS_REGION}"},
        {"name": "S3_BUCKET_NAME", "value": "${S3_BUCKET}"},
        {"name": "USE_LOCAL_STORAGE", "value": "false"},
        {"name": "OCR_PROVIDER", "value": "textract"},
        {"name": "LLM_PROVIDER", "value": "bedrock"},
        {"name": "USE_DYNAMODB_LOCAL", "value": "false"},
        {"name": "DYNAMODB_TABLE_DOCUMENTS", "value": "${DYNAMODB_DOCUMENTS_TABLE}"},
        {"name": "DYNAMODB_TABLE_ANALYSES", "value": "${DYNAMODB_ANALYSES_TABLE}"},
        {"name": "DYNAMODB_TABLE_CHATS", "value": "${DYNAMODB_CHATS_TABLE}"},
        {"name": "DYNAMODB_TABLE_REMINDERS", "value": "${DYNAMODB_REMINDERS_TABLE}"},
        {"name": "WORKER_MODE", "value": "fastapi"},
        {"name": "LOG_LEVEL", "value": "INFO"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/${STACK_NAME}",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "app",
          "awslogs-create-group": "true"
        }
      }
    }
  ]
}
EOF
)

aws ecs register-task-definition \
    --cli-input-json "${TASK_DEF_JSON}" \
    --region ${AWS_REGION}

echo "✓ Task definition registered"

# Get default VPC and subnets
echo "Getting default VPC..."
DEFAULT_VPC=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text --region ${AWS_REGION})
SUBNETS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=${DEFAULT_VPC}" --query "Subnets[*].SubnetId" --output text --region ${AWS_REGION})
SUBNET_LIST=$(echo $SUBNETS | tr ' ' ',')

# Create security group
SG_NAME="${STACK_NAME}-sg"
SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=${SG_NAME}" "Name=vpc-id,Values=${DEFAULT_VPC}" --query "SecurityGroups[0].GroupId" --output text --region ${AWS_REGION})

if [ "$SG_ID" == "None" ] || [ -z "$SG_ID" ]; then
    SG_ID=$(aws ec2 create-security-group \
        --group-name ${SG_NAME} \
        --description "Security group for ${STACK_NAME}" \
        --vpc-id ${DEFAULT_VPC} \
        --region ${AWS_REGION} \
        --query "GroupId" \
        --output text)

    # Allow inbound on port 8080
    aws ec2 authorize-security-group-ingress \
        --group-id ${SG_ID} \
        --protocol tcp \
        --port 8080 \
        --cidr 0.0.0.0/0 \
        --region ${AWS_REGION}

    echo "✓ Security group created: ${SG_ID}"
else
    echo "✓ Security group already exists: ${SG_ID}"
fi

# Create ECS service
echo "Creating ECS service..."

if aws ecs describe-services --cluster ${ECS_CLUSTER} --services ${ECS_SERVICE} --region ${AWS_REGION} | grep -q "ACTIVE"; then
    echo "✓ ECS service already exists"
else
    aws ecs create-service \
        --cluster ${ECS_CLUSTER} \
        --service-name ${ECS_SERVICE} \
        --task-definition ${ECS_TASK_FAMILY} \
        --desired-count 1 \
        --launch-type FARGATE \
        --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_LIST}],securityGroups=[${SG_ID}],assignPublicIp=ENABLED}" \
        --region ${AWS_REGION}

    echo "✓ ECS service created"
fi

###############################################################################
# 6. OUTPUT INFORMATION
###############################################################################

echo ""
echo "=============================================="
echo "Deployment Complete!"
echo "=============================================="
echo ""
echo "Resources created:"
echo "  S3 Bucket: ${S3_BUCKET}"
echo "  DynamoDB Tables:"
echo "    - ${DYNAMODB_DOCUMENTS_TABLE}"
echo "    - ${DYNAMODB_ANALYSES_TABLE}"
echo "    - ${DYNAMODB_CHATS_TABLE}"
echo "    - ${DYNAMODB_REMINDERS_TABLE}"
echo "  ECR Repository: ${ECR_REPO}"
echo "  ECS Cluster: ${ECS_CLUSTER}"
echo "  ECS Service: ${ECS_SERVICE}"
echo ""
echo "Waiting for service to start (this may take a few minutes)..."

# Wait for service to stabilize
aws ecs wait services-stable --cluster ${ECS_CLUSTER} --services ${ECS_SERVICE} --region ${AWS_REGION}

# Get public IP of running task
TASK_ARN=$(aws ecs list-tasks --cluster ${ECS_CLUSTER} --service-name ${ECS_SERVICE} --region ${AWS_REGION} --query "taskArns[0]" --output text)

if [ "$TASK_ARN" != "None" ] && [ -n "$TASK_ARN" ]; then
    ENI_ID=$(aws ecs describe-tasks --cluster ${ECS_CLUSTER} --tasks ${TASK_ARN} --region ${AWS_REGION} --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value" --output text)

    if [ -n "$ENI_ID" ]; then
        PUBLIC_IP=$(aws ec2 describe-network-interfaces --network-interface-ids ${ENI_ID} --region ${AWS_REGION} --query "NetworkInterfaces[0].Association.PublicIp" --output text)

        echo ""
        echo "✓ Service is running!"
        echo ""
        echo "API Endpoint: http://${PUBLIC_IP}:8080"
        echo "API Docs: http://${PUBLIC_IP}:8080/docs"
        echo "Health Check: http://${PUBLIC_IP}:8080/health"
        echo ""
    fi
fi

echo "=============================================="
echo "Next Steps:"
echo "1. Test the API: curl http://${PUBLIC_IP}:8080/health"
echo "2. Access API docs at http://${PUBLIC_IP}:8080/docs"
echo "3. For production, set up ALB with custom domain"
echo "4. Request Bedrock model access in AWS Console"
echo "5. Set up EventBridge + Lambda for reminders (see lambda/ directory)"
echo "=============================================="
