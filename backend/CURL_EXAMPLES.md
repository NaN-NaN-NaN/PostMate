# PostMate API - cURL Examples

Complete workflow demonstration using cURL commands.

## Prerequisites

```bash
# Set base URL
export API_URL="http://localhost:8080"

# Or for AWS deployment
export API_URL="http://YOUR_PUBLIC_IP:8080"
```

## Complete Workflow

### 1. Health Check

```bash
curl -X GET "${API_URL}/health" | jq
```

**Expected Response:**
```json
{
  "status": "healthy",
  "environment": "local",
  "version": "1.0.0",
  "services": {
    "storage": "local",
    "ocr": "tesseract",
    "llm": "openai",
    "database": "dynamodb-local"
  }
}
```

---

### 2. Upload Image(s)

**Single image:**
```bash
curl -X POST "${API_URL}/api/v1/upload" \
  -F "files=@/path/to/invoice.jpg" \
  | jq
```

**Multiple images:**
```bash
curl -X POST "${API_URL}/api/v1/upload" \
  -F "files=@/path/to/invoice_page1.jpg" \
  -F "files=@/path/to/invoice_page2.jpg" \
  | jq
```

**Expected Response:**
```json
{
  "document_id": "doc_ABC123",
  "status": "uploaded",
  "uploaded_files": 1,
  "message": "Successfully uploaded 1 file(s). Use document_id to check status and process OCR."
}
```

**Save document ID:**
```bash
export DOC_ID="doc_ABC123"
```

---

### 3. Check Document Status

```bash
curl -X GET "${API_URL}/api/v1/documents/${DOC_ID}/status" | jq
```

**Expected Response:**
```json
{
  "document_id": "doc_ABC123",
  "status": "uploaded",
  "uploaded_at": "2024-01-15T10:00:00",
  "processed_at": null,
  "ocr_status": "pending",
  "analysis_status": "pending",
  "image_count": 1,
  "ocr_text": null,
  "error_message": null
}
```

---

### 4. Trigger OCR Processing

```bash
curl -X POST "${API_URL}/api/v1/documents/${DOC_ID}/process_ocr" | jq
```

**Expected Response:**
```json
{
  "document_id": "doc_ABC123",
  "status": "processing",
  "message": "OCR processing started. Poll status endpoint for completion."
}
```

---

### 5. Poll OCR Status (wait for completion)

```bash
# Poll every 5 seconds until completed
while true; do
  STATUS=$(curl -s "${API_URL}/api/v1/documents/${DOC_ID}/status" | jq -r '.ocr_status')
  echo "OCR Status: $STATUS"

  if [ "$STATUS" == "completed" ]; then
    echo "OCR completed!"
    break
  elif [ "$STATUS" == "failed" ]; then
    echo "OCR failed!"
    break
  fi

  sleep 5
done
```

---

### 6. Get OCR Result

```bash
curl -X GET "${API_URL}/api/v1/documents/${DOC_ID}/ocr" | jq
```

**Expected Response:**
```json
{
  "document_id": "doc_ABC123",
  "ocr_status": "completed",
  "ocr_text": "INVOICE\nInvoice #: 12345\nDate: 2024-01-15\nTotal: $1,234.56",
  "confidence": 98.5,
  "page_count": 1,
  "processed_at": "2024-01-15T10:00:30",
  "textract_json_url": "s3://..."
}
```

---

### 7. Request AI Analysis

```bash
curl -X POST "${API_URL}/api/v1/analyze/${DOC_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "force_reanalyze": false
  }' \
  | jq
```

**Expected Response:**
```json
{
  "analysis_id": "analysis_XYZ789",
  "document_id": "doc_ABC123",
  "status": "processing",
  "message": "Analysis started. Poll status endpoint for completion."
}
```

**Save analysis ID:**
```bash
export ANALYSIS_ID="analysis_XYZ789"
```

---

### 8. Poll Analysis Status

```bash
curl -X GET "${API_URL}/api/v1/analyze/${DOC_ID}/status" | jq
```

---

### 9. Get Analysis Result

```bash
curl -X GET "${API_URL}/api/v1/analyze/${DOC_ID}/result" | jq
```

**Expected Response:**
```json
{
  "analysis_id": "analysis_XYZ789",
  "document_id": "doc_ABC123",
  "category": "invoice",
  "confidence": 0.95,
  "summary": "Invoice from ABC Company for consulting services, total amount $1,234.56",
  "key_entities": {
    "date": "2024-01-15",
    "total_amount": "$1,234.56",
    "vendor": "ABC Company",
    "invoice_number": "12345",
    "due_date": "2024-02-15"
  },
  "suggested_tags": ["invoice", "payment", "consulting"],
  "completed_at": "2024-01-15T10:01:00"
}
```

---

### 10. Chat - Ask Questions

**First question:**
```bash
curl -X POST "${API_URL}/api/v1/chat/${DOC_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the total amount on this invoice?"
  }' \
  | jq
```

**Expected Response:**
```json
{
  "message_id": "msg_123",
  "question": "What is the total amount on this invoice?",
  "answer": "The total amount on this invoice is $1,234.56.",
  "timestamp": "2024-01-15T10:02:00"
}
```

**Follow-up question:**
```bash
curl -X POST "${API_URL}/api/v1/chat/${DOC_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "When is the due date?"
  }' \
  | jq
```

---

### 11. Get Chat History

```bash
curl -X GET "${API_URL}/api/v1/chat/${DOC_ID}/history" | jq
```

**Expected Response:**
```json
{
  "document_id": "doc_ABC123",
  "messages": [
    {
      "message_id": "msg_123",
      "role": "user",
      "content": "What is the total amount on this invoice?",
      "timestamp": "2024-01-15T10:02:00"
    },
    {
      "message_id": "msg_124",
      "role": "assistant",
      "content": "The total amount on this invoice is $1,234.56.",
      "timestamp": "2024-01-15T10:02:01"
    }
  ],
  "total_messages": 2
}
```

---

### 12. Create Reminder

```bash
curl -X POST "${API_URL}/api/v1/reminders" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "'"${DOC_ID}"'",
    "title": "Pay invoice #12345",
    "description": "Payment due for ABC Company invoice",
    "reminder_date": "2024-02-15T09:00:00Z",
    "notification_method": "email",
    "notification_target": "user@example.com"
  }' \
  | jq
```

**Expected Response:**
```json
{
  "reminder_id": "reminder_DEF456",
  "document_id": "doc_ABC123",
  "title": "Pay invoice #12345",
  "description": "Payment due for ABC Company invoice",
  "reminder_date": "2024-02-15T09:00:00",
  "status": "pending",
  "created_at": "2024-01-15T10:03:00",
  "sent_at": null,
  "notification_method": "email"
}
```

**Save reminder ID:**
```bash
export REMINDER_ID="reminder_DEF456"
```

---

### 13. List Reminders

**All reminders:**
```bash
curl -X GET "${API_URL}/api/v1/reminders" | jq
```

**Filter by date range:**
```bash
curl -X GET "${API_URL}/api/v1/reminders?start_date=2024-02-01T00:00:00Z&end_date=2024-02-28T23:59:59Z" | jq
```

**Filter by status:**
```bash
curl -X GET "${API_URL}/api/v1/reminders?status=pending" | jq
```

---

### 14. Get Calendar View

```bash
curl -X GET "${API_URL}/api/v1/reminders/calendar?start_date=2024-02-01T00:00:00Z&end_date=2024-02-28T23:59:59Z" | jq
```

**Expected Response:**
```json
{
  "start_date": "2024-02-01",
  "end_date": "2024-02-28",
  "items": [
    {
      "date": "2024-02-15",
      "reminders": [
        {
          "reminder_id": "reminder_DEF456",
          "title": "Pay invoice #12345",
          "reminder_date": "2024-02-15T09:00:00"
        }
      ],
      "count": 1
    }
  ]
}
```

---

### 15. Update Reminder

```bash
curl -X PUT "${API_URL}/api/v1/reminders/${REMINDER_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "reminder_date": "2024-02-16T10:00:00Z",
    "title": "URGENT: Pay invoice #12345"
  }' \
  | jq
```

---

### 16. Search Documents

**Search by text:**
```bash
curl -X GET "${API_URL}/api/v1/search?query=invoice&limit=10" | jq
```

**Search by category:**
```bash
curl -X GET "${API_URL}/api/v1/search?category=invoice" | jq
```

**Search by date range:**
```bash
curl -X GET "${API_URL}/api/v1/search?start_date=2024-01-01T00:00:00Z&end_date=2024-01-31T23:59:59Z" | jq
```

**Expected Response:**
```json
{
  "results": [
    {
      "document_id": "doc_ABC123",
      "uploaded_at": "2024-01-15T10:00:00",
      "ocr_text_preview": "INVOICE\nInvoice #: 12345\nDate: 2024-01-15...",
      "category": "invoice",
      "image_count": 1,
      "has_analysis": true
    }
  ],
  "total": 1,
  "query": "invoice"
}
```

---

### 17. Export to PDF

```bash
curl -X POST "${API_URL}/api/v1/documents/${DOC_ID}/export/pdf" \
  -H "Content-Type: application/json" \
  -d '{
    "include_images": true,
    "include_analysis": true
  }' \
  | jq
```

**Expected Response:**
```json
{
  "document_id": "doc_ABC123",
  "pdf_url": "s3://postmate-storage/doc_ABC123/export.pdf",
  "status": "generated",
  "message": "PDF generated successfully"
}
```

---

### 18. Download PDF

```bash
# Get redirect URL
curl -X GET "${API_URL}/api/v1/documents/${DOC_ID}/download?file_type=pdf" -L -o document.pdf

# Or just get the redirect URL
curl -X GET "${API_URL}/api/v1/documents/${DOC_ID}/download?file_type=pdf" -s -o /dev/null -w "%{redirect_url}\n"
```

**Download original image:**
```bash
curl -X GET "${API_URL}/api/v1/documents/${DOC_ID}/download?file_type=original" -L -o original.jpg
```

**Download Textract JSON:**
```bash
curl -X GET "${API_URL}/api/v1/documents/${DOC_ID}/download?file_type=textract_json" -L -o textract.json
```

---

### 19. Delete Reminder

```bash
curl -X DELETE "${API_URL}/api/v1/reminders/${REMINDER_ID}"
```

**Expected Response:** HTTP 204 No Content

---

## Complete Workflow Script

Save this as `test_workflow.sh`:

```bash
#!/bin/bash

API_URL="http://localhost:8080"

echo "=== PostMate Complete Workflow Test ==="

# 1. Health check
echo -e "\n1. Health Check"
curl -s "${API_URL}/health" | jq -r '.status'

# 2. Upload
echo -e "\n2. Uploading document..."
UPLOAD_RESPONSE=$(curl -s -X POST "${API_URL}/api/v1/upload" \
  -F "files=@tests/sample_data/test_image.jpg")

DOC_ID=$(echo $UPLOAD_RESPONSE | jq -r '.document_id')
echo "Document ID: $DOC_ID"

# 3. Trigger OCR
echo -e "\n3. Triggering OCR..."
curl -s -X POST "${API_URL}/api/v1/documents/${DOC_ID}/process_ocr" | jq -r '.message'

# 4. Wait for OCR
echo -e "\n4. Waiting for OCR to complete..."
sleep 10

# 5. Get OCR result
echo -e "\n5. OCR Result:"
curl -s "${API_URL}/api/v1/documents/${DOC_ID}/ocr" | jq -r '.ocr_text' | head -n 5

# 6. Request analysis
echo -e "\n6. Requesting analysis..."
curl -s -X POST "${API_URL}/api/v1/analyze/${DOC_ID}" | jq -r '.message'

# 7. Wait for analysis
sleep 10

# 8. Get analysis
echo -e "\n8. Analysis Result:"
curl -s "${API_URL}/api/v1/analyze/${DOC_ID}/result" | jq '{category, confidence, summary}'

# 9. Chat
echo -e "\n9. Asking question..."
ANSWER=$(curl -s -X POST "${API_URL}/api/v1/chat/${DOC_ID}" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is this document about?"}' | jq -r '.answer')
echo "Answer: $ANSWER"

# 10. Create reminder
echo -e "\n10. Creating reminder..."
curl -s -X POST "${API_URL}/api/v1/reminders" \
  -H "Content-Type: application/json" \
  -d "{
    \"document_id\": \"${DOC_ID}\",
    \"title\": \"Review document\",
    \"reminder_date\": \"2024-12-31T10:00:00Z\"
  }" | jq -r '.reminder_id'

echo -e "\n=== Workflow Complete ==="
```

Run with:
```bash
chmod +x test_workflow.sh
./test_workflow.sh
```

---

## Error Handling Examples

### Invalid document ID:
```bash
curl -X GET "${API_URL}/api/v1/documents/invalid_id/status" | jq
```

**Response:**
```json
{
  "detail": "Document invalid_id not found"
}
```

### OCR before upload complete:
```bash
curl -X POST "${API_URL}/api/v1/documents/${DOC_ID}/process_ocr"
```

**Response (if already processing):**
```json
{
  "document_id": "doc_ABC123",
  "status": "already_processing",
  "message": "OCR processing already in progress"
}
```

---

## Production Tips

1. **Use jq for JSON parsing:**
   ```bash
   brew install jq  # macOS
   apt-get install jq  # Linux
   ```

2. **Save responses to files:**
   ```bash
   curl "${API_URL}/api/v1/analyze/${DOC_ID}/result" > analysis.json
   ```

3. **Pretty print JSON:**
   ```bash
   curl -s "${API_URL}/health" | jq '.'
   ```

4. **Extract specific fields:**
   ```bash
   curl -s "${API_URL}/api/v1/documents/${DOC_ID}/status" | jq -r '.ocr_status'
   ```

5. **Loop through results:**
   ```bash
   curl -s "${API_URL}/api/v1/search?query=invoice" | jq -r '.results[].document_id'
   ```
