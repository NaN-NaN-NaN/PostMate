# PostMate Backend - Project Summary

## Overview

**PostMate** is a complete document processing backend system built with Python FastAPI and AWS services. It extracts text from images using OCR, performs AI analysis, provides Q&A chat, and manages reminders.

## Tech Stack

### Core
- **Language:** Python 3.10+
- **Framework:** FastAPI (async)
- **API Documentation:** OpenAPI/Swagger (auto-generated)

### AWS Services (Production)
- **Storage:** Amazon S3
- **OCR:** Amazon Textract
- **LLM:** Amazon Bedrock (Claude 3)
- **Database:** Amazon DynamoDB
- **Compute:** ECS Fargate
- **Scheduler:** EventBridge + Lambda
- **Container Registry:** ECR

### Local Development Alternatives
- **Storage:** Local file system
- **OCR:** Tesseract
- **LLM:** OpenAI GPT-4
- **Database:** DynamoDB Local
- **Scheduler:** APScheduler

## Project Structure

```
postmate-backend/
├── app/
│   ├── main.py                    # FastAPI application entry point
│   ├── config.py                  # Configuration management
│   ├── dependencies.py            # Dependency injection
│   ├── api/v1/                    # API endpoints
│   │   ├── upload.py              # Upload & OCR endpoints
│   │   ├── analyze.py             # Analysis endpoints
│   │   ├── chat.py                # Chat endpoints
│   │   ├── reminders.py           # Reminder endpoints
│   │   └── search.py              # Search & export endpoints
│   ├── services/                  # Business logic
│   │   ├── storage.py             # S3/local storage
│   │   ├── textract.py            # OCR (Textract/Tesseract)
│   │   ├── llm.py                 # LLM (Bedrock/OpenAI)
│   │   ├── pdfgen.py              # PDF generation
│   │   └── db.py                  # DynamoDB operations
│   ├── models/                    # Data models
│   │   ├── document.py
│   │   ├── analysis.py
│   │   ├── chat.py
│   │   └── reminder.py
│   ├── workers/                   # Background tasks
│   │   └── background_tasks.py
│   ├── prompts/                   # LLM prompts
│   │   ├── analysis_prompt.txt
│   │   ├── chat_prompt.txt
│   │   └── summary_prompt.txt
│   └── scripts/
│       └── create_tables_local.py
├── tests/                         # Unit tests
│   ├── conftest.py
│   ├── test_textract_parser.py
│   ├── test_llm_prompts.py
│   └── sample_data/
├── lambda/                        # AWS Lambda functions
│   └── reminder_scheduler/
├── deploy_aws.sh                  # AWS deployment script
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Key Features

### 1. Document Upload & OCR
- Multi-file upload support
- Async OCR processing (Textract or Tesseract)
- Reading order preservation for multi-column layouts
- Confidence scoring

### 2. AI Analysis
- Document categorization (invoice, receipt, letter, etc.)
- Key entity extraction (dates, amounts, vendors)
- Automatic summarization
- Tag suggestions
- Strict JSON output format

### 3. Chat Q&A
- Context-aware question answering
- Chat history persistence
- Long document handling via chunking

### 4. Reminders
- Document-linked reminders
- Calendar view
- Scheduled notifications (EventBridge + Lambda)

### 5. Search & Export
- Full-text search (DynamoDB scan)
- Category and date filtering
- Annotated PDF generation
- Download endpoints with presigned URLs

## API Endpoints

```
GET  /health                              # Health check
POST /api/v1/upload                       # Upload images
GET  /api/v1/documents/{id}/status        # Get status
POST /api/v1/documents/{id}/process_ocr   # Trigger OCR
GET  /api/v1/documents/{id}/ocr           # Get OCR result
POST /api/v1/analyze/{id}                 # Request analysis
GET  /api/v1/analyze/{id}/status          # Analysis status
GET  /api/v1/analyze/{id}/result          # Analysis result
POST /api/v1/chat/{id}                    # Ask question
GET  /api/v1/chat/{id}/history            # Chat history
POST /api/v1/reminders                    # Create reminder
GET  /api/v1/reminders                    # List reminders
GET  /api/v1/reminders/calendar           # Calendar view
PUT  /api/v1/reminders/{id}               # Update reminder
DELETE /api/v1/reminders/{id}             # Delete reminder
GET  /api/v1/search                       # Search documents
POST /api/v1/documents/{id}/export/pdf    # Generate PDF
GET  /api/v1/documents/{id}/download      # Download file
```

## Data Models

### Document
```python
{
  "document_id": "doc_xxx",
  "status": "uploaded|processing|completed|failed",
  "uploaded_at": "2024-01-15T10:00:00",
  "image_urls": ["s3://..."],
  "ocr_status": "pending|processing|completed|failed",
  "ocr_text": "Extracted text...",
  "ocr_confidence": 98.5,
  "analysis_status": "pending|processing|completed|failed"
}
```

### Analysis
```python
{
  "analysis_id": "analysis_xxx",
  "document_id": "doc_xxx",
  "category": "invoice|receipt|letter|contract|form|other",
  "confidence": 0.95,
  "summary": "Brief summary...",
  "key_entities": {
    "date": "2024-01-15",
    "total_amount": "$1,234.56",
    "vendor": "ABC Company"
  },
  "suggested_tags": ["invoice", "payment"]
}
```

### ChatMessage
```python
{
  "message_id": "msg_xxx",
  "document_id": "doc_xxx",
  "role": "user|assistant",
  "content": "Message text",
  "timestamp": "2024-01-15T10:00:00"
}
```

### Reminder
```python
{
  "reminder_id": "reminder_xxx",
  "document_id": "doc_xxx",
  "title": "Pay invoice",
  "reminder_date": "2024-02-15T10:00:00",
  "status": "pending|sent|cancelled"
}
```

## LLM Implementation Details

### Chunking & Summarization Algorithm
1. Count tokens in OCR text
2. If > MAX_CHUNK_TOKENS:
   - Split into chunks (respecting paragraph boundaries)
   - Summarize each chunk individually
   - Combine summaries
   - If combined still too long, recursively summarize
3. Use final text for analysis/chat

### Textract Reading Order Algorithm
1. Extract all LINE blocks from Textract response
2. Get bounding box geometry (top, left coordinates)
3. Sort by: `(round(top * 100), left)`
   - Groups lines at same vertical position
   - Sorts left-to-right within each row
4. Join lines with newlines

### Prompt Engineering
- **Analysis:** Strict JSON schema enforcement, no markdown
- **Chat:** Context-aware with document content
- **Summary:** Preserve key details (dates, amounts, names)

## Testing Strategy

### Unit Tests
- `test_textract_parser.py` - Reading order, multi-column, confidence
- `test_llm_prompts.py` - JSON extraction, chunking, token counting

### Integration Tests
- Upload → OCR → Analysis → Chat workflow
- Multi-file upload
- Error handling

### Test Fixtures
- Sample Textract JSON response
- Sample LLM analysis response
- Mock AWS services using moto

## Deployment Options

### Local Development
```bash
# 1. Start DynamoDB Local
docker run -d -p 8000:8000 amazon/dynamodb-local

# 2. Create tables
python -m app.scripts.create_tables_local

# 3. Run app
uvicorn app.main:app --reload
```

### Docker Compose
```bash
docker-compose up --build
```

### AWS Production
```bash
./deploy_aws.sh
```

## AWS Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│     ALB     │ (Application Load Balancer)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ ECS Fargate │ (FastAPI containers)
└──────┬──────┘
       │
       ├─────────────► S3 (images, PDFs, Textract JSON)
       │
       ├─────────────► DynamoDB (documents, analyses, chats, reminders)
       │
       ├─────────────► Textract (OCR)
       │
       ├─────────────► Bedrock (LLM - Claude 3)
       │
       └─────────────► SQS → Lambda (async OCR worker - optional)

┌─────────────────┐
│  EventBridge    │ (every 5 minutes)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Lambda Function │ (check pending reminders)
└─────────────────┘
```

## Security Considerations

### Authentication
- **Demo:** No auth (for simplicity)
- **Production:** Add JWT middleware or API key authentication

### IAM Roles
- **ECS Task Execution Role:** Pull images, write logs
- **ECS Task Role:** S3, DynamoDB, Textract, Bedrock permissions
- **Lambda Execution Role:** DynamoDB, SES/SNS permissions

### Secrets Management
- Use AWS Secrets Manager or Parameter Store
- Never commit `.env` file
- Use environment variables in ECS task definition

### Data Protection
- S3 server-side encryption (AES-256)
- DynamoDB encryption at rest
- VPC for ECS tasks (production)
- Security groups restrict access

## Performance Optimizations

### Async Operations
- All I/O operations use async/await
- Concurrent file processing
- Non-blocking LLM calls

### Caching
- Consider Redis for:
  - Frequently accessed documents
  - LLM responses (same document, same question)
  - Analysis results

### Scaling
- ECS auto-scaling based on CPU/memory
- DynamoDB on-demand billing (auto-scales)
- S3 automatically scales
- Consider SQS + Lambda for OCR workers at high volume

## Cost Estimation (AWS)

### Monthly Costs (estimate for 1000 documents/month)
- **S3:** ~$5 (50 GB storage + requests)
- **DynamoDB:** ~$10 (on-demand, low traffic)
- **Textract:** ~$15 (1000 pages @ $1.50/1000)
- **Bedrock:** ~$30 (Claude 3 Sonnet usage)
- **ECS Fargate:** ~$50 (1 task, 0.5 vCPU, 1 GB)
- **Lambda:** ~$1 (reminder scheduler)
- **Data Transfer:** ~$5

**Total: ~$116/month** (varies by usage)

### Cost Optimization
- Use Tesseract instead of Textract (free, lower accuracy)
- Use smaller Bedrock model (Claude Haiku)
- Stop ECS tasks when idle
- Use S3 lifecycle policies for old documents

## Future Enhancements

### Features
1. **Batch Processing:** Upload entire folders
2. **OCR Correction:** Manual editing of OCR text
3. **Document Comparison:** Compare two invoices
4. **Custom Categories:** User-defined categories
5. **Webhooks:** Notify external systems
6. **Multi-tenancy:** Support multiple users/organizations

### Technical Improvements
1. **Full-Text Search:** Add OpenSearch/Elasticsearch
2. **Caching Layer:** Redis for performance
3. **Rate Limiting:** Protect API from abuse
4. **Monitoring:** CloudWatch dashboards, alerts
5. **Async Workers:** SQS + Lambda for all background tasks
6. **CDN:** CloudFront for PDF downloads

### ML Enhancements
1. **Custom OCR:** Fine-tune Textract or train custom model
2. **NER:** Named Entity Recognition for specific domains
3. **Classification:** ML model for category prediction
4. **Data Extraction:** Template-based extraction (invoices)

## Maintenance

### Logs
- Application logs: CloudWatch Logs (ECS)
- Access logs: ALB access logs
- Lambda logs: CloudWatch Logs

### Monitoring
- ECS metrics: CPU, memory, task count
- API metrics: Request count, latency, errors
- DynamoDB metrics: Read/write capacity
- Bedrock metrics: Token usage, cost

### Backup
- S3: Versioning enabled
- DynamoDB: Point-in-time recovery (enable for production)
- Regular exports to S3

## License

MIT License - See LICENSE file

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## Support

- Documentation: `/docs` endpoint
- Examples: `CURL_EXAMPLES.md`
- Quick Start: `QUICKSTART.md`
- Issues: GitHub Issues

---

**Built with ❤️ for document processing automation**
