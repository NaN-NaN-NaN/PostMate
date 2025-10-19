"""
PostMate Backend - Upload & Document Status Endpoints

Purpose: Handle multi-file image uploads, document status polling, and OCR processing.

API Endpoints:
    POST /api/v1/upload - Upload one or more images
    GET /api/v1/documents/{doc_id}/status - Get document processing status
    POST /api/v1/documents/{doc_id}/process_ocr - Trigger OCR processing
    GET /api/v1/documents/{doc_id}/ocr - Get OCR results

Testing:
    # Upload single image
    curl -X POST http://localhost:8080/api/v1/upload \\
      -F "files=@test.jpg"

    # Upload multiple images
    curl -X POST http://localhost:8080/api/v1/upload \\
      -F "files=@invoice1.jpg" \\
      -F "files=@invoice2.jpg"

    # Check status
    curl http://localhost:8080/api/v1/documents/{doc_id}/status

    # Trigger OCR
    curl -X POST http://localhost:8080/api/v1/documents/{doc_id}/process_ocr

AWS Deployment Notes:
    - File uploads are saved to S3 (or local storage in dev mode)
    - OCR processing uses FastAPI BackgroundTasks (local) or SQS+Lambda (production)
    - Max upload size enforced by nginx/ALB (configure in infrastructure)
"""

from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks, status
from typing import List, Optional
from pydantic import BaseModel, Field
import logging
from datetime import datetime
import shortuuid

from app.config import settings
from app.services.storage import StorageService
from app.services.db import DatabaseService
from app.services.textract import TextractService
from app.models.document import Document, DocumentStatus, ProcessingStatus
from app.workers.background_tasks import process_ocr_task

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
storage_service = StorageService()
db_service = DatabaseService()
textract_service = TextractService()


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class UploadResponse(BaseModel):
    """Response after successful upload"""
    document_id: str = Field(..., description="Unique document identifier")
    status: str = Field(..., description="Current processing status")
    uploaded_files: int = Field(..., description="Number of files uploaded")
    message: str = Field(..., description="Success message")


class DocumentStatusResponse(BaseModel):
    """Document processing status response"""
    document_id: str
    status: DocumentStatus
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    ocr_status: ProcessingStatus
    analysis_status: ProcessingStatus
    image_count: int
    ocr_text: Optional[str] = None
    error_message: Optional[str] = None


class OCRTriggerResponse(BaseModel):
    """Response after triggering OCR"""
    document_id: str
    status: str
    message: str


class OCRResultResponse(BaseModel):
    """OCR result response"""
    document_id: str
    ocr_status: ProcessingStatus
    ocr_text: Optional[str] = None
    confidence: Optional[float] = None
    page_count: Optional[int] = None
    processed_at: Optional[datetime] = None
    textract_json_url: Optional[str] = None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def validate_upload_files(files: List[UploadFile]) -> None:
    """
    Validate uploaded files (format, size, count)

    Raises:
        HTTPException: If validation fails
    """
    # Check file count
    if len(files) > settings.MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many files. Maximum {settings.MAX_FILES_PER_UPLOAD} files allowed."
        )

    if len(files) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided"
        )

    supported_formats = settings.supported_formats_list

    for file in files:
        # Check file extension
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must have a filename"
            )

        file_ext = file.filename.split('.')[-1].lower()
        if file_ext not in supported_formats:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format: {file_ext}. Supported: {', '.join(supported_formats)}"
            )

        # Check file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning

        if file_size > settings.max_upload_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File {file.filename} exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB"
            )

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File {file.filename} is empty"
            )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_images(
    files: List[UploadFile] = File(..., description="One or more image files to upload")
) -> UploadResponse:
    """
    Upload one or more images for document processing.

    Supports: JPG, JPEG, PNG, TIFF, BMP
    Max size per file: Configured in settings (default 10MB)
    Max files per request: Configured in settings (default 10)

    Returns:
        UploadResponse with document_id for tracking
    """
    logger.info(f"Received upload request with {len(files)} file(s)")

    # Validate files
    await validate_upload_files(files)

    try:
        # Generate unique document ID
        document_id = f"doc_{shortuuid.uuid()}"
        logger.info(f"Generated document ID: {document_id}")

        # Save files to storage
        image_urls = []
        image_keys = []

        for idx, file in enumerate(files):
            logger.info(f"Processing file {idx + 1}/{len(files)}: {file.filename}")

            # Read file content
            content = await file.read()

            # Generate storage key
            file_ext = file.filename.split('.')[-1].lower()
            storage_key = f"{document_id}/image_{idx + 1}.{file_ext}"

            # Save to storage (S3 or local)
            image_url = await storage_service.save_image(
                key=storage_key,
                content=content,
                content_type=file.content_type or f"image/{file_ext}"
            )

            image_urls.append(image_url)
            image_keys.append(storage_key)

            logger.info(f"Saved image {idx + 1} to: {storage_key}")

        # Create document record in database
        document = Document(
            document_id=document_id,
            status=DocumentStatus.UPLOADED,
            uploaded_at=datetime.utcnow(),
            image_urls=image_urls,
            image_keys=image_keys,
            image_count=len(files),
            ocr_status=ProcessingStatus.PENDING,
            analysis_status=ProcessingStatus.PENDING,
        )

        await db_service.save_document(document)
        logger.info(f"Document {document_id} saved to database")

        return UploadResponse(
            document_id=document_id,
            status=DocumentStatus.UPLOADED,
            uploaded_files=len(files),
            message=f"Successfully uploaded {len(files)} file(s). Use document_id to check status and process OCR."
        )

    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


@router.get("/documents/{doc_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(doc_id: str) -> DocumentStatusResponse:
    """
    Get current processing status of a document.

    Use this endpoint to poll for OCR and analysis completion.

    Args:
        doc_id: Document ID from upload response

    Returns:
        DocumentStatusResponse with current status
    """
    logger.info(f"Status check for document: {doc_id}")

    # Get document from database
    document = await db_service.get_document(doc_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found"
        )

    return DocumentStatusResponse(
        document_id=document.document_id,
        status=document.status,
        uploaded_at=document.uploaded_at,
        processed_at=document.processed_at,
        ocr_status=document.ocr_status,
        analysis_status=document.analysis_status,
        image_count=document.image_count,
        ocr_text=document.ocr_text[:500] if document.ocr_text else None,  # Preview only
        error_message=document.error_message,
    )


@router.post("/documents/{doc_id}/process_ocr", response_model=OCRTriggerResponse)
async def trigger_ocr_processing(
    doc_id: str,
    background_tasks: BackgroundTasks
) -> OCRTriggerResponse:
    """
    Trigger OCR processing for uploaded document.

    Processing happens asynchronously:
    - Local/Dev: FastAPI BackgroundTasks (in-process)
    - Production: SQS message to Lambda worker

    Poll /documents/{doc_id}/status to check completion.

    Args:
        doc_id: Document ID to process

    Returns:
        OCRTriggerResponse confirming processing started
    """
    logger.info(f"OCR processing requested for document: {doc_id}")

    # Get document from database
    document = await db_service.get_document(doc_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found"
        )

    # Check if already processed or in progress
    if document.ocr_status == ProcessingStatus.COMPLETED:
        return OCRTriggerResponse(
            document_id=doc_id,
            status="already_completed",
            message="OCR already completed for this document"
        )

    if document.ocr_status == ProcessingStatus.PROCESSING:
        return OCRTriggerResponse(
            document_id=doc_id,
            status="already_processing",
            message="OCR processing already in progress"
        )

    try:
        # Update status to processing
        document.ocr_status = ProcessingStatus.PROCESSING
        document.status = DocumentStatus.PROCESSING
        await db_service.update_document(document)

        # Trigger background processing
        if settings.WORKER_MODE == "fastapi":
            # Use FastAPI BackgroundTasks for local/dev
            background_tasks.add_task(process_ocr_task, doc_id)
            logger.info(f"Added OCR task to BackgroundTasks for {doc_id}")

        elif settings.WORKER_MODE == "lambda":
            # Send message to SQS for Lambda processing
            import boto3
            sqs = boto3.client('sqs', region_name=settings.AWS_REGION)

            sqs.send_message(
                QueueUrl=settings.SQS_QUEUE_URL,
                MessageBody=doc_id,
                MessageAttributes={
                    'task_type': {
                        'StringValue': 'ocr',
                        'DataType': 'String'
                    }
                }
            )
            logger.info(f"Sent OCR task to SQS for {doc_id}")

        return OCRTriggerResponse(
            document_id=doc_id,
            status="processing",
            message="OCR processing started. Poll status endpoint for completion."
        )

    except Exception as e:
        logger.error(f"Failed to trigger OCR: {e}", exc_info=True)

        # Revert status on failure
        document.ocr_status = ProcessingStatus.FAILED
        document.error_message = str(e)
        await db_service.update_document(document)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start OCR processing: {str(e)}"
        )


@router.get("/documents/{doc_id}/ocr", response_model=OCRResultResponse)
async def get_ocr_result(doc_id: str) -> OCRResultResponse:
    """
    Get OCR results for a processed document.

    Returns full extracted text and metadata.

    Args:
        doc_id: Document ID

    Returns:
        OCRResultResponse with extracted text
    """
    logger.info(f"OCR result requested for document: {doc_id}")

    # Get document from database
    document = await db_service.get_document(doc_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found"
        )

    if document.ocr_status != ProcessingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OCR not completed. Current status: {document.ocr_status}"
        )

    # Get presigned URL for Textract JSON if available
    textract_json_url = None
    if document.textract_json_key:
        textract_json_url = await storage_service.get_presigned_url(
            document.textract_json_key
        )

    return OCRResultResponse(
        document_id=document.document_id,
        ocr_status=document.ocr_status,
        ocr_text=document.ocr_text,
        confidence=document.ocr_confidence,
        page_count=document.page_count,
        processed_at=document.processed_at,
        textract_json_url=textract_json_url,
    )
