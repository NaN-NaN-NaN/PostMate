# PostMate Backend - Documentation Index

## Quick Navigation

### Getting Started
1. **[QUICKSTART.md](QUICKSTART.md)** - Get running in 5 minutes
2. **[README.md](README.md)** - Full documentation
3. **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** - Technical overview

### Development
4. **[.env.example](.env.example)** - Environment configuration template
5. **[requirements.txt](requirements.txt)** - Python dependencies
6. **[docker-compose.yml](docker-compose.yml)** - Local dev stack

### API Documentation
7. **[CURL_EXAMPLES.md](CURL_EXAMPLES.md)** - Complete cURL examples
8. **[postman_collection.json](postman_collection.json)** - Postman collection
9. **`/docs`** endpoint - Interactive API docs (when running)

### Deployment
10. **[deploy_aws.sh](deploy_aws.sh)** - AWS deployment script
11. **[Dockerfile](Dockerfile)** - Container image definition

### Code Structure

#### Application Core
- **[app/main.py](app/main.py)** - FastAPI application entry point
- **[app/config.py](app/config.py)** - Configuration management
- **[app/dependencies.py](app/dependencies.py)** - Dependency injection

#### API Endpoints
- **[app/api/v1/upload.py](app/api/v1/upload.py)** - Upload & OCR endpoints
- **[app/api/v1/analyze.py](app/api/v1/analyze.py)** - Analysis endpoints
- **[app/api/v1/chat.py](app/api/v1/chat.py)** - Chat Q&A endpoints
- **[app/api/v1/reminders.py](app/api/v1/reminders.py)** - Reminder management
- **[app/api/v1/search.py](app/api/v1/search.py)** - Search & export

#### Services (Business Logic)
- **[app/services/storage.py](app/services/storage.py)** - S3/local storage
- **[app/services/textract.py](app/services/textract.py)** - OCR processing
- **[app/services/llm.py](app/services/llm.py)** - LLM integration
- **[app/services/pdfgen.py](app/services/pdfgen.py)** - PDF generation
- **[app/services/db.py](app/services/db.py)** - DynamoDB operations

#### Data Models
- **[app/models/document.py](app/models/document.py)** - Document model
- **[app/models/analysis.py](app/models/analysis.py)** - Analysis model
- **[app/models/chat.py](app/models/chat.py)** - Chat models
- **[app/models/reminder.py](app/models/reminder.py)** - Reminder model

#### Background Workers
- **[app/workers/background_tasks.py](app/workers/background_tasks.py)** - Task processors

#### Prompts
- **[app/prompts/analysis_prompt.txt](app/prompts/analysis_prompt.txt)** - Analysis prompt
- **[app/prompts/chat_prompt.txt](app/prompts/chat_prompt.txt)** - Chat prompt
- **[app/prompts/summary_prompt.txt](app/prompts/summary_prompt.txt)** - Summary prompt

### Testing
- **[tests/conftest.py](tests/conftest.py)** - Test configuration
- **[tests/test_textract_parser.py](tests/test_textract_parser.py)** - Textract tests
- **[tests/test_llm_prompts.py](tests/test_llm_prompts.py)** - LLM tests
- **[tests/test_upload.py](tests/test_upload.py)** - Upload endpoint tests
- **[tests/test_analyze.py](tests/test_analyze.py)** - Analysis tests

### AWS Lambda
- **[lambda/reminder_scheduler/handler.py](lambda/reminder_scheduler/handler.py)** - Reminder scheduler

### Utilities
- **[create_test_image.py](create_test_image.py)** - Generate test invoice image
- **[app/scripts/create_tables_local.py](app/scripts/create_tables_local.py)** - Create DynamoDB tables

### Configuration Files
- **[.gitignore](.gitignore)** - Git ignore rules
- **[LICENSE](LICENSE)** - MIT License

---

## Documentation by Use Case

### I want to...

#### ...get started quickly
→ Read [QUICKSTART.md](QUICKSTART.md)

#### ...understand the full system
→ Read [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)

#### ...see API examples
→ Read [CURL_EXAMPLES.md](CURL_EXAMPLES.md)

#### ...deploy to AWS
→ Run [deploy_aws.sh](deploy_aws.sh)

#### ...run tests
→ `pytest tests/ -v`

#### ...understand OCR parsing
→ Read [app/services/textract.py](app/services/textract.py) and [tests/test_textract_parser.py](tests/test_textract_parser.py)

#### ...customize LLM prompts
→ Edit files in [app/prompts/](app/prompts/)

#### ...add a new endpoint
→ Create file in [app/api/v1/](app/api/v1/) following existing patterns

#### ...change database schema
→ Edit models in [app/models/](app/models/)

#### ...modify storage backend
→ Edit [app/services/storage.py](app/services/storage.py)

---

## Key Concepts

### Document Processing Flow
```
Upload → OCR → Analysis → Chat/Export
```

1. **Upload** ([upload.py](app/api/v1/upload.py)): Save images to storage
2. **OCR** ([textract.py](app/services/textract.py)): Extract text with reading order
3. **Analysis** ([llm.py](app/services/llm.py)): Categorize and extract entities
4. **Chat** ([chat.py](app/api/v1/chat.py)): Q&A about document
5. **Export** ([search.py](app/api/v1/search.py)): Generate annotated PDF

### LLM Integration
- **Chunking:** Split long documents ([llm.py:chunk_and_summarize](app/services/llm.py))
- **Prompts:** Template-based with strict JSON output ([app/prompts/](app/prompts/))
- **Providers:** Bedrock (production) or OpenAI (dev)

### Storage Abstraction
- **Local:** File system for development
- **AWS:** S3 for production
- **Interface:** Unified API in [storage.py](app/services/storage.py)

### Background Processing
- **Local:** FastAPI BackgroundTasks
- **AWS:** SQS + Lambda workers
- **Implementation:** [background_tasks.py](app/workers/background_tasks.py)

---

## Common Tasks

### Add New Document Category
1. Edit `DocumentCategory` enum in [app/models/analysis.py](app/models/analysis.py)
2. Update prompt in [app/prompts/analysis_prompt.txt](app/prompts/analysis_prompt.txt)
3. Add test case in [tests/test_analyze.py](tests/test_analyze.py)

### Change LLM Model
1. Update `.env`: `BEDROCK_MODEL_ID` or `OPENAI_MODEL`
2. Adjust `MAX_CHUNK_TOKENS` if needed
3. Test with different document types

### Add Notification Channel
1. Edit [app/workers/background_tasks.py](app/workers/background_tasks.py)
2. Implement `send_reminder_notification()` for new channel
3. Update `ReminderRequest` in [app/api/v1/reminders.py](app/api/v1/reminders.py)

### Customize PDF Format
1. Edit [app/services/pdfgen.py](app/services/pdfgen.py)
2. Modify `_setup_custom_styles()` for styling
3. Update `_build_*_section()` methods for content

---

## Architecture Diagrams

### Local Development
```
┌─────────────┐
│   FastAPI   │ (port 8080)
└──────┬──────┘
       │
       ├─────► Local FS (./local_data/)
       ├─────► Tesseract OCR
       ├─────► OpenAI API
       └─────► DynamoDB Local (port 8000)
```

### AWS Production
```
Client → ALB → ECS Fargate (FastAPI)
                   │
                   ├─────► S3
                   ├─────► Textract
                   ├─────► Bedrock
                   └─────► DynamoDB

EventBridge ──► Lambda (reminders)
```

---

## File Organization

```
postmate-backend/
├── Documentation           # This file, README, guides
├── Configuration          # .env, requirements.txt, docker files
├── app/                   # Application code
│   ├── api/              # API endpoints (controllers)
│   ├── services/         # Business logic
│   ├── models/           # Data models
│   ├── workers/          # Background tasks
│   ├── prompts/          # LLM prompts
│   └── scripts/          # Utility scripts
├── tests/                # Unit and integration tests
├── lambda/               # AWS Lambda functions
└── Deployment           # deploy_aws.sh, Dockerfile
```

---

## Version History

- **v1.0.0** - Initial release
  - Multi-file upload
  - OCR with Textract/Tesseract
  - AI analysis with Bedrock/OpenAI
  - Chat Q&A
  - Reminders with calendar
  - Search and PDF export
  - AWS deployment automation

---

## Related Resources

### External Documentation
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [AWS Textract](https://docs.aws.amazon.com/textract/)
- [AWS Bedrock](https://docs.aws.amazon.com/bedrock/)
- [DynamoDB](https://docs.aws.amazon.com/dynamodb/)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)

### Tools
- [Postman](https://www.postman.com/) - API testing
- [jq](https://stedolan.github.io/jq/) - JSON parsing
- [AWS CLI](https://aws.amazon.com/cli/) - AWS management

---

**Last Updated:** 2024-01-15

**Maintainer:** PostMate Team

**License:** MIT - See [LICENSE](LICENSE)
