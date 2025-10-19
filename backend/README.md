# PostMate Backend

**Purpose:** Complete backend system for PostMate - a document processing service that extracts text from images (invoices, receipts, letters), performs AI analysis, provides chat Q&A, and manages reminders. Built with FastAPI and AWS services.

## Architecture Overview

- **Framework:** FastAPI (Python 3.10+) with async/await
- **Storage:** AWS S3 (images, PDFs, Textract JSON) + DynamoDB (metadata, analyses, chats, reminders)
- **AI Services:**
  - OCR: AWS Textract (production) / Tesseract (local dev)
  - LLM: AWS Bedrock Claude (production) / OpenAI GPT (local dev)
- **Background Processing:** FastAPI BackgroundTasks (local) / AWS Lambda + SQS (production)
- **Reminders:** AWS EventBridge + Lambda (production) / APScheduler (local)

## Table of Contents

1. [Local Development Setup](#local-development-setup)
2. [AWS Production Deployment](#aws-production-deployment)
3. [Environment Variables](#environment-variables)
4. [API Endpoints](#api-endpoints)
5. [Testing](#testing)
6. [Deployment Scripts](#deployment-scripts)

---

## Local Development Setup

### Prerequisites

- Python 3.10+
- Docker & Docker Compose (optional, for containerized dev)
- Tesseract OCR (for local OCR fallback)
- AWS CLI v2 (for AWS deployment)

### Install Tesseract (Local OCR)

**macOS:**
```bash
brew install tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**Windows:**
Download from: https://github.com/UB-Mannheim/tesseract/wiki

### Step 1: Clone and Install Dependencies

```bash
git clone <repository-url>
cd postmate-backend

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For testing
```

### Step 2: Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your configuration (see [Environment Variables](#environment-variables) section below).

**Minimal Local Setup (No AWS):**
```env
# App Config
ENVIRONMENT=local
DEBUG=true
API_V1_PREFIX=/api/v1

# Local Storage (file system instead of S3)
USE_LOCAL_STORAGE=true
LOCAL_STORAGE_PATH=./local_data

# Local OCR (Tesseract)
OCR_PROVIDER=tesseract
TESSERACT_PATH=/usr/local/bin/tesseract  # Adjust to your path

# Local LLM (OpenAI)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-openai-key-here

# Local Database (DynamoDB Local)
USE_DYNAMODB_LOCAL=true
DYNAMODB_LOCAL_ENDPOINT=http://localhost:8000
```

### Step 3: Run DynamoDB Local (Optional for full local dev)

```bash
# Using Docker
docker run -d -p 8000:8000 amazon/dynamodb-local

# Create tables locally
python -m app.scripts.create_tables_local
```

### Step 4: Start the Application

```bash
# Direct run
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# Or with Docker Compose
docker-compose up --build
```

The API will be available at: `http://localhost:8080`

Interactive API docs: `http://localhost:8080/docs`

---

## AWS Production Deployment

### Prerequisites

1. AWS Account with appropriate permissions
2. AWS CLI configured (`aws configure`)
3. Docker installed
4. ECR repository created (or use deploy script to create)

### Quick Deploy (Automated)

```bash
# Make deploy script executable
chmod +x deploy_aws.sh

# Run deployment (creates all AWS resources)
./deploy_aws.sh
```

The script will:
1. Create S3 bucket for storage
2. Create DynamoDB tables (documents, analyses, chats, reminders)
3. Build and push Docker image to ECR
4. Deploy ECS Fargate service
5. Create EventBridge rule + Lambda for reminder scheduling
6. Output the API endpoint URL

### Manual AWS Setup

See detailed instructions in `deploy_aws.sh` comments and [Deployment Scripts](#deployment-scripts) section.

---

## Environment Variables

### Core Application

| Variable | Description | Local Dev | AWS Production |
|----------|-------------|-----------|----------------|
| `ENVIRONMENT` | Environment name | `local` | `production` |
| `DEBUG` | Enable debug logging | `true` | `false` |
| `API_V1_PREFIX` | API version prefix | `/api/v1` | `/api/v1` |
| `AWS_REGION` | AWS region | `us-east-1` | `us-east-1` |

### Storage Configuration

| Variable | Description | Local Dev | AWS Production |
|----------|-------------|-----------|----------------|
| `USE_LOCAL_STORAGE` | Use file system instead of S3 | `true` | `false` |
| `LOCAL_STORAGE_PATH` | Local storage directory | `./local_data` | N/A |
| `S3_BUCKET_NAME` | S3 bucket for storage | N/A | `postmate-storage-prod` |
| `S3_PREFIX_IMAGES` | S3 prefix for images | N/A | `images/` |
| `S3_PREFIX_PDFS` | S3 prefix for PDFs | N/A | `pdfs/` |
| `S3_PREFIX_TEXTRACT` | S3 prefix for Textract JSON | N/A | `textract/` |

### OCR Configuration

| Variable | Description | Local Dev | AWS Production |
|----------|-------------|-----------|----------------|
| `OCR_PROVIDER` | OCR provider | `tesseract` | `textract` |
| `TESSERACT_PATH` | Path to Tesseract binary | `/usr/local/bin/tesseract` | N/A |
| `TEXTRACT_ASYNC` | Use async Textract jobs | N/A | `true` |

### LLM Configuration

| Variable | Description | Local Dev | AWS Production |
|----------|-------------|-----------|----------------|
| `LLM_PROVIDER` | LLM provider | `openai` | `bedrock` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-xxx` | N/A |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4-turbo-preview` | N/A |
| `BEDROCK_MODEL_ID` | Bedrock model ID | N/A | `anthropic.claude-3-sonnet-20240229-v1:0` |
| `BEDROCK_REGION` | Bedrock region | N/A | `us-east-1` |
| `MAX_CHUNK_TOKENS` | Max tokens per chunk for long docs | `4000` | `4000` |

### Database Configuration

| Variable | Description | Local Dev | AWS Production |
|----------|-------------|-----------|----------------|
| `USE_DYNAMODB_LOCAL` | Use DynamoDB Local | `true` | `false` |
| `DYNAMODB_LOCAL_ENDPOINT` | DynamoDB Local endpoint | `http://localhost:8000` | N/A |
| `DYNAMODB_TABLE_DOCUMENTS` | Documents table name | `postmate-documents-local` | `postmate-documents-prod` |
| `DYNAMODB_TABLE_ANALYSES` | Analyses table name | `postmate-analyses-local` | `postmate-analyses-prod` |
| `DYNAMODB_TABLE_CHATS` | Chats table name | `postmate-chats-local` | `postmate-chats-prod` |
| `DYNAMODB_TABLE_REMINDERS` | Reminders table name | `postmate-reminders-local` | `postmate-reminders-prod` |

### Background Workers

| Variable | Description | Local Dev | AWS Production |
|----------|-------------|-----------|----------------|
| `WORKER_MODE` | Worker execution mode | `fastapi` | `lambda` |
| `SQS_QUEUE_URL` | SQS queue for async jobs | N/A | `https://sqs.us-east-1...` |

---

## API Endpoints

All endpoints are prefixed with `/api/v1`. See interactive docs at `/docs` for full request/response schemas.

### Document Upload & Processing

- `POST /api/v1/upload` - Upload images (multi-file support)
- `GET /api/v1/documents/{doc_id}/status` - Check processing status
- `POST /api/v1/documents/{doc_id}/process_ocr` - Trigger OCR processing
- `GET /api/v1/documents/{doc_id}/ocr` - Get OCR results

### Analysis

- `POST /api/v1/analyze/{doc_id}` - Request AI analysis (category, entities, summary)
- `GET /api/v1/analyze/{doc_id}/status` - Poll analysis status
- `GET /api/v1/analyze/{doc_id}/result` - Get analysis result

### Chat

- `POST /api/v1/chat/{doc_id}` - Ask questions about document
- `GET /api/v1/chat/{doc_id}/history` - Get chat history

### Reminders

- `POST /api/v1/reminders` - Create reminder
- `GET /api/v1/reminders` - List reminders (filter by date range)
- `GET /api/v1/reminders/calendar` - Calendar view
- `PUT /api/v1/reminders/{reminder_id}` - Update reminder
- `DELETE /api/v1/reminders/{reminder_id}` - Delete reminder

### Search & Export

- `GET /api/v1/search` - Search documents (full-text, category, date filters)
- `POST /api/v1/documents/{doc_id}/export/pdf` - Generate annotated PDF
- `GET /api/v1/documents/{doc_id}/download` - Download original/PDF

---

## Testing

### Run Unit Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Specific test file
pytest tests/test_textract_parser.py -v

# Run only fast tests (skip integration)
pytest -m "not integration"
```

### Test Files

- `test_textract_parser.py` - Textract JSON parsing and reading order
- `test_llm_prompts.py` - LLM prompt formatting and JSON validation
- `test_upload.py` - File upload endpoints
- `test_analyze.py` - Analysis workflow

### Manual Testing with Sample Data

```bash
# Upload test image
curl -X POST "http://localhost:8080/api/v1/upload" \
  -F "files=@tests/sample_data/test_image.jpg"

# Response: {"document_id": "doc_xxx", "status": "uploaded"}

# Trigger OCR
curl -X POST "http://localhost:8080/api/v1/documents/doc_xxx/process_ocr"

# Poll status
curl "http://localhost:8080/api/v1/documents/doc_xxx/status"

# Request analysis
curl -X POST "http://localhost:8080/api/v1/analyze/doc_xxx"

# Get analysis result
curl "http://localhost:8080/api/v1/analyze/doc_xxx/result"
```

See `postman_collection.json` for complete workflow examples.

---

## Deployment Scripts

### `deploy_aws.sh`

Automated deployment script that:
1. Creates S3 bucket with versioning
2. Creates DynamoDB tables with on-demand billing
3. Builds Docker image and pushes to ECR
4. Deploys ECS Fargate service with auto-scaling
5. Creates Lambda functions for reminders
6. Sets up EventBridge rules for scheduling

**Usage:**
```bash
./deploy_aws.sh
```

**Environment Variables for Deploy:**
```bash
export AWS_ACCOUNT_ID=123456789012
export AWS_REGION=us-east-1
export STACK_NAME=postmate-prod
```

### Rollback

```bash
# Delete CloudFormation stack
aws cloudformation delete-stack --stack-name postmate-prod

# Or manual cleanup
./deploy_aws.sh --destroy
```

---

## Local Development Workflow

### Full Local Demo (No AWS)

1. **Start DynamoDB Local:**
   ```bash
   docker run -d -p 8000:8000 amazon/dynamodb-local
   ```

2. **Create tables:**
   ```bash
   python -m app.scripts.create_tables_local
   ```

3. **Start FastAPI:**
   ```bash
   uvicorn app.main:app --reload --port 8080
   ```

4. **Test workflow:**
   ```bash
   # Upload
   curl -X POST http://localhost:8080/api/v1/upload \
     -F "files=@tests/sample_data/test_image.jpg"

   # Process OCR (uses Tesseract)
   curl -X POST http://localhost:8080/api/v1/documents/{doc_id}/process_ocr

   # Analyze (uses OpenAI)
   curl -X POST http://localhost:8080/api/v1/analyze/{doc_id}

   # Chat
   curl -X POST http://localhost:8080/api/v1/chat/{doc_id} \
     -H "Content-Type: application/json" \
     -d '{"question": "What is the total amount?"}'
   ```

---

## Production Architecture

```
Client
  │
  ├─> ALB (Application Load Balancer)
  │     │
  │     └─> ECS Fargate (FastAPI containers)
  │           │
  │           ├─> S3 (images, PDFs, Textract JSON)
  │           ├─> DynamoDB (metadata, analyses, chats, reminders)
  │           ├─> Textract (OCR)
  │           ├─> Bedrock (LLM)
  │           └─> SQS -> Lambda (async OCR worker)
  │
  └─> EventBridge (reminder scheduler)
        │
        └─> Lambda (check and send reminders)
```

---

## Troubleshooting

### Common Issues

**1. Tesseract not found:**
```bash
# Verify installation
which tesseract

# Update .env with correct path
TESSERACT_PATH=/usr/local/bin/tesseract
```

**2. DynamoDB Local connection error:**
```bash
# Ensure DynamoDB Local is running
docker ps | grep dynamodb-local

# Check endpoint in .env
DYNAMODB_LOCAL_ENDPOINT=http://localhost:8000
```

**3. AWS credentials not found:**
```bash
# Configure AWS CLI
aws configure

# Or use environment variables
export AWS_ACCESS_KEY_ID=xxx
export AWS_SECRET_ACCESS_KEY=xxx
```

**4. Bedrock model access denied:**
- Request model access in AWS Console -> Bedrock -> Model Access
- Wait for approval (usually instant for Claude models)

---

## Security Notes

- **Never commit `.env` file** - use `.env.example` as template
- **AWS credentials:** Use IAM roles (ECS task role) in production, never hardcode
- **API authentication:** Add JWT/API key middleware for production (not included in demo)
- **CORS:** Configure allowed origins in `main.py`

---

## License

MIT

---

## Support

For issues or questions:
- GitHub Issues: `<repository-url>/issues`
- Documentation: See `/docs` endpoint when running

---

**Next Steps:**
1. Review environment variables for your setup
2. Run local development server
3. Test with Postman collection
4. Deploy to AWS using `deploy_aws.sh`
