"""
PostMate Backend - Analysis Endpoints

Purpose: Request and retrieve AI analysis of documents

API Endpoints:
    POST /api/v1/analyze/{doc_id} - Request analysis
    GET /api/v1/analyze/{doc_id}/status - Poll analysis status
    GET /api/v1/analyze/{doc_id}/result - Get analysis result

Testing:
    curl -X POST http://localhost:8080/api/v1/analyze/doc_xxx
    curl http://localhost:8080/api/v1/analyze/doc_xxx/status
    curl http://localhost:8080/api/v1/analyze/doc_xxx/result

AWS Deployment Notes:
    - Analysis runs in background (BackgroundTasks or Lambda)
    - Long documents are chunked and summarized before analysis
    - LLM returns strict JSON format
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import logging
import shortuuid

from app.config import settings
from app.services.db import DatabaseService
from app.services.llm import LLMService
from app.models.document import Document, ProcessingStatus
from app.models.analysis import Analysis, AnalysisStatus, DocumentCategory
from app.workers.background_tasks import process_analysis_task

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
db_service = DatabaseService()
llm_service = LLMService()


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class AnalyzeRequest(BaseModel):
    """Request to analyze document"""
    force_reanalyze: bool = Field(default=False, description="Force re-analysis even if exists")


class AnalyzeResponse(BaseModel):
    """Response after requesting analysis"""
    analysis_id: str
    document_id: str
    status: str
    message: str


class AnalysisStatusResponse(BaseModel):
    """Analysis status response"""
    analysis_id: str
    document_id: str
    status: AnalysisStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class AnalysisResultResponse(BaseModel):
    """Analysis result response"""
    analysis_id: str
    document_id: str
    category: DocumentCategory
    confidence: float
    summary: Optional[str] = None
    key_entities: Dict[str, Any] = Field(default_factory=dict)
    suggested_tags: list = Field(default_factory=list)
    completed_at: Optional[datetime] = None


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/analyze/{doc_id}", response_model=AnalyzeResponse)
async def request_analysis(
    doc_id: str,
    background_tasks: BackgroundTasks,
    request: AnalyzeRequest = AnalyzeRequest()
) -> AnalyzeResponse:
    """
    Request AI analysis of document

    Document must have completed OCR first.
    Analysis runs asynchronously - poll status endpoint for completion.

    Args:
        doc_id: Document ID to analyze
        request: Analysis request options

    Returns:
        AnalyzeResponse with analysis_id for tracking
    """
    logger.info(f"Analysis requested for document: {doc_id}")

    # Get document from database
    document = await db_service.get_document(doc_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found"
        )

    # Check if OCR is completed
    if document.ocr_status != ProcessingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OCR must be completed before analysis. Current status: {document.ocr_status}"
        )

    if not document.ocr_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OCR text available for analysis"
        )

    # Check if analysis already exists
    if not request.force_reanalyze:
        existing_analysis = await db_service.get_analysis_by_document(doc_id)
        if existing_analysis and existing_analysis.status == AnalysisStatus.COMPLETED:
            return AnalyzeResponse(
                analysis_id=existing_analysis.analysis_id,
                document_id=doc_id,
                status="already_completed",
                message="Analysis already exists. Use force_reanalyze=true to re-analyze."
            )

    try:
        # Create analysis record
        analysis_id = f"analysis_{shortuuid.uuid()}"
        analysis = Analysis(
            analysis_id=analysis_id,
            document_id=doc_id,
            status=AnalysisStatus.PROCESSING,
        )

        await db_service.save_analysis(analysis)

        # Update document
        document.analysis_status = ProcessingStatus.PROCESSING
        document.analysis_id = analysis_id
        await db_service.update_document(document)

        # Trigger background processing
        if settings.WORKER_MODE == "fastapi":
            background_tasks.add_task(process_analysis_task, analysis_id)
            logger.info(f"Added analysis task to BackgroundTasks for {analysis_id}")

        elif settings.WORKER_MODE == "lambda":
            # Send to SQS
            import boto3
            sqs = boto3.client('sqs', region_name=settings.AWS_REGION)

            sqs.send_message(
                QueueUrl=settings.SQS_QUEUE_URL,
                MessageBody=analysis_id,
                MessageAttributes={
                    'task_type': {
                        'StringValue': 'analysis',
                        'DataType': 'String'
                    }
                }
            )
            logger.info(f"Sent analysis task to SQS for {analysis_id}")

        return AnalyzeResponse(
            analysis_id=analysis_id,
            document_id=doc_id,
            status="processing",
            message="Analysis started. Poll status endpoint for completion."
        )

    except Exception as e:
        logger.error(f"Failed to start analysis: {e}", exc_info=True)

        # Update status on failure
        if 'analysis' in locals():
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = str(e)
            await db_service.update_analysis(analysis)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start analysis: {str(e)}"
        )


@router.get("/analyze/{doc_id}/status", response_model=AnalysisStatusResponse)
async def get_analysis_status(doc_id: str) -> AnalysisStatusResponse:
    """
    Get analysis status for a document

    Args:
        doc_id: Document ID

    Returns:
        AnalysisStatusResponse with current status
    """
    logger.info(f"Analysis status check for document: {doc_id}")

    # Get analysis from database
    analysis = await db_service.get_analysis_by_document(doc_id)

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis found for document {doc_id}"
        )

    return AnalysisStatusResponse(
        analysis_id=analysis.analysis_id,
        document_id=analysis.document_id,
        status=analysis.status,
        created_at=analysis.created_at,
        completed_at=analysis.completed_at,
        error_message=analysis.error_message,
    )


@router.get("/analyze/{doc_id}/result", response_model=AnalysisResultResponse)
async def get_analysis_result(doc_id: str) -> AnalysisResultResponse:
    """
    Get completed analysis result

    Args:
        doc_id: Document ID

    Returns:
        AnalysisResultResponse with extracted insights
    """
    logger.info(f"Analysis result requested for document: {doc_id}")

    # Get analysis from database
    analysis = await db_service.get_analysis_by_document(doc_id)

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis found for document {doc_id}"
        )

    if analysis.status != AnalysisStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Analysis not completed. Current status: {analysis.status}"
        )

    return AnalysisResultResponse(
        analysis_id=analysis.analysis_id,
        document_id=analysis.document_id,
        category=analysis.category,
        confidence=analysis.confidence,
        summary=analysis.summary,
        key_entities=analysis.key_entities,
        suggested_tags=analysis.suggested_tags,
        completed_at=analysis.completed_at,
    )
