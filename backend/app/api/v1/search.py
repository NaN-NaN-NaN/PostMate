"""
PostMate Backend - Search & Export Endpoints

Purpose: Search documents and export to PDF

API Endpoints:
    GET /api/v1/search - Search documents
    POST /api/v1/documents/{doc_id}/export/pdf - Generate annotated PDF
    GET /api/v1/documents/{doc_id}/download - Download file

Testing:
    curl "http://localhost:8080/api/v1/search?query=invoice&limit=10"
    curl -X POST http://localhost:8080/api/v1/documents/doc_xxx/export/pdf
    curl http://localhost:8080/api/v1/documents/doc_xxx/download

AWS Deployment Notes:
    - Search uses DynamoDB scan (consider OpenSearch for production)
    - PDFs generated on-demand and saved to S3
    - Download returns presigned S3 URLs
"""

from fastapi import APIRouter, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import StreamingResponse, RedirectResponse
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging
import io

from app.config import settings
from app.services.db import DatabaseService
from app.services.storage import StorageService
from app.services.pdfgen import PDFGenService
from app.models.document import Document
from app.models.analysis import DocumentCategory
from app.workers.background_tasks import generate_pdf_task

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
db_service = DatabaseService()
storage_service = StorageService()
pdf_service = PDFGenService()


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class DocumentSearchResult(BaseModel):
    """Search result item"""
    document_id: str
    uploaded_at: datetime
    ocr_text_preview: Optional[str] = None
    category: Optional[str] = None
    image_count: int
    has_analysis: bool


class SearchResponse(BaseModel):
    """Search response"""
    results: List[DocumentSearchResult]
    total: int
    query: Optional[str]


class PDFExportRequest(BaseModel):
    """PDF export request"""
    include_images: bool = Field(default=True, description="Include original images in PDF")
    include_analysis: bool = Field(default=True, description="Include analysis results")


class PDFExportResponse(BaseModel):
    """PDF export response"""
    document_id: str
    pdf_url: Optional[str] = None
    status: str
    message: str


# =============================================================================
# SEARCH ENDPOINT
# =============================================================================

@router.get("/search", response_model=SearchResponse)
async def search_documents(
    query: Optional[str] = Query(None, description="Search query (searches OCR text)"),
    category: Optional[DocumentCategory] = Query(None, description="Filter by category"),
    start_date: Optional[datetime] = Query(None, description="Filter by upload date (start)"),
    end_date: Optional[datetime] = Query(None, description="Filter by upload date (end)"),
    limit: int = Query(100, le=settings.SEARCH_MAX_RESULTS, description="Max results")
) -> SearchResponse:
    """
    Search documents with filters

    Note: This is a simple scan-based search for demo.
    For production, consider:
    - Amazon OpenSearch Service
    - DynamoDB Streams + Lambda + OpenSearch pipeline
    - ElasticSearch

    Args:
        query: Text search in OCR content
        category: Filter by document category
        start_date: Filter by upload date (start)
        end_date: Filter by upload date (end)
        limit: Maximum results

    Returns:
        SearchResponse with matching documents
    """
    logger.info(f"Search: query='{query}', category={category}, limit={limit}")

    # Check if feature is enabled
    if not settings.ENABLE_SEARCH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search feature is disabled"
        )

    try:
        # Search documents
        documents = await db_service.search_documents(
            query=query,
            category=category,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )

        # If category filter specified, filter by analysis category
        if category:
            filtered_docs = []
            for doc in documents:
                if doc.analysis_id:
                    analysis = await db_service.get_analysis(doc.analysis_id)
                    if analysis and analysis.category == category:
                        filtered_docs.append(doc)
            documents = filtered_docs

        # Build search results
        results = []

        for doc in documents:
            # Get category from analysis if available
            doc_category = None
            if doc.analysis_id:
                analysis = await db_service.get_analysis(doc.analysis_id)
                if analysis:
                    doc_category = analysis.category

            # Preview first 200 chars of OCR text
            ocr_preview = None
            if doc.ocr_text:
                ocr_preview = doc.ocr_text[:200]
                if len(doc.ocr_text) > 200:
                    ocr_preview += "..."

            results.append(DocumentSearchResult(
                document_id=doc.document_id,
                uploaded_at=doc.uploaded_at,
                ocr_text_preview=ocr_preview,
                category=doc_category,
                image_count=doc.image_count,
                has_analysis=doc.analysis_id is not None,
            ))

        logger.info(f"Search returned {len(results)} results")

        return SearchResponse(
            results=results,
            total=len(results),
            query=query,
        )

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


# =============================================================================
# PDF EXPORT ENDPOINT
# =============================================================================

@router.post("/documents/{doc_id}/export/pdf", response_model=PDFExportResponse)
async def export_pdf(
    doc_id: str,
    background_tasks: BackgroundTasks,
    request: PDFExportRequest = PDFExportRequest()
) -> PDFExportResponse:
    """
    Generate annotated PDF for document

    Includes:
    - Document metadata
    - OCR extracted text
    - Analysis results (if available)
    - Original images (optional)

    Args:
        doc_id: Document ID
        request: Export options

    Returns:
        PDFExportResponse with PDF URL
    """
    logger.info(f"PDF export requested for document: {doc_id}")

    # Check if feature is enabled
    if not settings.ENABLE_PDF_EXPORT:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PDF export feature is disabled"
        )

    # Get document
    document = await db_service.get_document(doc_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found"
        )

    # Check if PDF already exists
    if document.pdf_key and await storage_service.file_exists(document.pdf_key):
        pdf_url = await storage_service.get_presigned_url(document.pdf_key)
        return PDFExportResponse(
            document_id=doc_id,
            pdf_url=pdf_url,
            status="existing",
            message="PDF already exists. Returning existing PDF."
        )

    try:
        # Get analysis if requested
        analysis = None
        if request.include_analysis and document.analysis_id:
            analysis = await db_service.get_analysis(document.analysis_id)

        # Generate PDF
        pdf_bytes = await pdf_service.generate_pdf(
            document=document,
            analysis=analysis,
            include_images=request.include_images
        )

        # Save to storage
        pdf_key = f"{doc_id}/export.pdf"
        pdf_url = await storage_service.save_pdf(pdf_key, pdf_bytes)

        # Update document
        document.pdf_key = pdf_key
        document.pdf_url = pdf_url
        await db_service.update_document(document)

        logger.info(f"PDF generated and saved: {pdf_key}")

        # Get presigned URL for download
        download_url = await storage_service.get_presigned_url(pdf_key)

        return PDFExportResponse(
            document_id=doc_id,
            pdf_url=download_url,
            status="generated",
            message="PDF generated successfully"
        )

    except Exception as e:
        logger.error(f"PDF export failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF export failed: {str(e)}"
        )


# =============================================================================
# DOWNLOAD ENDPOINT
# =============================================================================

@router.get("/documents/{doc_id}/download")
async def download_file(
    doc_id: str,
    file_type: str = Query("pdf", description="File type: pdf, original, textract_json")
):
    """
    Download document file

    Args:
        doc_id: Document ID
        file_type: Type of file to download (pdf, original, textract_json)

    Returns:
        Redirect to presigned S3 URL or file stream
    """
    logger.info(f"Download requested: {doc_id}, type={file_type}")

    # Get document
    document = await db_service.get_document(doc_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found"
        )

    try:
        if file_type == "pdf":
            # Download PDF export
            if not document.pdf_key:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="PDF not generated yet. Use /export/pdf endpoint first."
                )

            url = await storage_service.get_presigned_url(document.pdf_key)
            return RedirectResponse(url=url)

        elif file_type == "original":
            # Download first original image
            if not document.image_keys:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No original images found"
                )

            # Return first image
            url = await storage_service.get_presigned_url(
                f"{settings.S3_PREFIX_IMAGES}{document.image_keys[0]}"
            )
            return RedirectResponse(url=url)

        elif file_type == "textract_json":
            # Download Textract JSON
            if not document.textract_json_key:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Textract JSON not available"
                )

            url = await storage_service.get_presigned_url(document.textract_json_key)
            return RedirectResponse(url=url)

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file_type: {file_type}. Use: pdf, original, or textract_json"
            )

    except Exception as e:
        logger.error(f"Download failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Download failed: {str(e)}"
        )
