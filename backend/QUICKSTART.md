# PostMate Backend - Quick Start Guide

Get up and running in 5 minutes!

## Option 1: Local Development (No AWS Required)

### Prerequisites
- Python 3.10+
- Tesseract OCR
- OpenAI API key
- Docker (optional, for DynamoDB Local)

### 1. Install Tesseract

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

### 2. Setup Project

```bash
# Clone repository
git clone <your-repo-url>
cd postmate-backend

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env
```

**Minimal `.env` for local development:**
```env
# App
ENVIRONMENT=local
DEBUG=true

# Storage
USE_LOCAL_STORAGE=true
LOCAL_STORAGE_PATH=./local_data

# OCR
OCR_PROVIDER=tesseract
TESSERACT_PATH=/usr/local/bin/tesseract  # Adjust to your path

# LLM (get key from https://platform.openai.com/api-keys)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here

# Database
USE_DYNAMODB_LOCAL=true
DYNAMODB_LOCAL_ENDPOINT=http://localhost:8000
```

### 4. Start DynamoDB Local

**Using Docker:**
```bash
docker run -d -p 8000:8000 amazon/dynamodb-local
```

**Create tables:**
```bash
python -m app.scripts.create_tables_local
```

### 5. Run the Application

```bash
uvicorn app.main:app --reload --port 8080
```

**Or using the shortcut:**
```bash
python -m app.main
```

### 6. Test the API

Open your browser:
- **API Docs:** http://localhost:8080/docs
- **Health Check:** http://localhost:8080/health

**Quick test with curl:**
```bash
# Health check
curl http://localhost:8080/health | jq

# Upload a test image (create one first)
curl -X POST http://localhost:8080/api/v1/upload \
  -F "files=@/path/to/test-image.jpg"
```

---

## Option 2: Docker Compose (Easiest!)

### Prerequisites
- Docker
- Docker Compose
- OpenAI API key

### 1. Setup

```bash
# Clone repository
cd postmate-backend

# Copy environment file
cp .env.example .env

# Edit .env - only need to set:
# OPENAI_API_KEY=sk-your-key-here
nano .env
```

### 2. Run Everything

```bash
docker-compose up --build
```

This starts:
- FastAPI application (port 8080)
- DynamoDB Local (port 8000)
- DynamoDB Admin UI (port 8001)

### 3. Access Services

- **API:** http://localhost:8080/docs
- **DynamoDB Admin:** http://localhost:8001

### 4. Test

```bash
curl http://localhost:8080/health
```

---

## Option 3: AWS Deployment

### Prerequisites
- AWS Account
- AWS CLI configured
- Docker
- Bedrock model access (request in AWS Console)

### 1. Configure AWS

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Enter region (e.g., us-east-1)
```

### 2. Request Bedrock Access

1. Go to AWS Console → Amazon Bedrock
2. Click "Model Access"
3. Request access to "Claude 3 Sonnet"
4. Wait for approval (usually instant)

### 3. Deploy

```bash
chmod +x deploy_aws.sh
./deploy_aws.sh
```

The script will:
- Create S3 bucket
- Create DynamoDB tables
- Build and push Docker image to ECR
- Deploy to ECS Fargate
- Output your API endpoint

### 4. Test

```bash
# Replace with your public IP from deploy script output
export API_URL="http://YOUR_PUBLIC_IP:8080"

curl ${API_URL}/health
```

---

## Creating a Test Image

Don't have a test image? Create one with Python:

```python
from PIL import Image, ImageDraw, ImageFont

# Create blank image
img = Image.new('RGB', (800, 1000), color='white')
draw = ImageDraw.Draw(img)

# Add text
try:
    font = ImageFont.truetype("Arial.ttf", 32)
except:
    font = ImageFont.load_default()

draw.text((50, 50), "INVOICE", fill='black', font=font)
draw.text((50, 120), "Invoice #: INV-2024-001", fill='black')
draw.text((50, 160), "Date: January 15, 2024", fill='black')
draw.text((50, 200), "Amount: $1,234.56", fill='black')

# Save
img.save('test_invoice.jpg')
print("Test image created: test_invoice.jpg")
```

Run:
```bash
python create_test_image.py
```

---

## Complete Workflow Test

Once your server is running, test the complete workflow:

### 1. Upload Document
```bash
DOC_ID=$(curl -s -X POST http://localhost:8080/api/v1/upload \
  -F "files=@test_invoice.jpg" | jq -r '.document_id')

echo "Document ID: $DOC_ID"
```

### 2. Process OCR
```bash
curl -X POST http://localhost:8080/api/v1/documents/${DOC_ID}/process_ocr

# Wait 10 seconds
sleep 10
```

### 3. Get OCR Result
```bash
curl http://localhost:8080/api/v1/documents/${DOC_ID}/ocr | jq '.ocr_text'
```

### 4. Analyze Document
```bash
curl -X POST http://localhost:8080/api/v1/analyze/${DOC_ID}

# Wait 10 seconds
sleep 10

# Get result
curl http://localhost:8080/api/v1/analyze/${DOC_ID}/result | jq
```

### 5. Ask Questions
```bash
curl -X POST http://localhost:8080/api/v1/chat/${DOC_ID} \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the invoice number?"}' \
  | jq '.answer'
```

### 6. Create Reminder
```bash
curl -X POST http://localhost:8080/api/v1/reminders \
  -H "Content-Type: application/json" \
  -d "{
    \"document_id\": \"${DOC_ID}\",
    \"title\": \"Pay invoice\",
    \"reminder_date\": \"2024-12-31T10:00:00Z\"
  }" | jq
```

### 7. Export PDF
```bash
curl -X POST http://localhost:8080/api/v1/documents/${DOC_ID}/export/pdf \
  -H "Content-Type: application/json" \
  -d '{"include_images": true, "include_analysis": true}' \
  | jq '.pdf_url'
```

---

## Troubleshooting

### Tesseract not found
```bash
# Check if installed
which tesseract

# Update .env with correct path
TESSERACT_PATH=/usr/local/bin/tesseract
```

### DynamoDB connection error
```bash
# Check if DynamoDB Local is running
docker ps | grep dynamodb

# Restart it
docker run -d -p 8000:8000 amazon/dynamodb-local

# Recreate tables
python -m app.scripts.create_tables_local
```

### OpenAI API error
```bash
# Verify your API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Check .env has correct key
grep OPENAI_API_KEY .env
```

### Port already in use
```bash
# Use different port
uvicorn app.main:app --reload --port 8081

# Or find and kill process on port 8080
lsof -ti:8080 | xargs kill -9
```

---

## Next Steps

1. **Read Full Documentation:** See [README.md](README.md)
2. **Try Postman Collection:** Import `postman_collection.json`
3. **Run Tests:** `pytest tests/ -v`
4. **Explore API Docs:** http://localhost:8080/docs
5. **Check cURL Examples:** See [CURL_EXAMPLES.md](CURL_EXAMPLES.md)

---

## Quick Reference

**Local URLs:**
- API: http://localhost:8080
- Docs: http://localhost:8080/docs
- Health: http://localhost:8080/health
- DynamoDB Admin: http://localhost:8001

**Key Commands:**
```bash
# Start app
uvicorn app.main:app --reload

# Run tests
pytest

# Create tables
python -m app.scripts.create_tables_local

# Deploy to AWS
./deploy_aws.sh
```

**Environment Files:**
- `.env.example` - Template
- `.env` - Your config (git-ignored)

---

## Getting Help

- Check logs in terminal
- Visit `/docs` endpoint for API documentation
- See `README.md` for detailed information
- Check `tests/` for examples

---

**Happy coding! 🚀**
