"""
PostMate Backend - Background Tasks & Scheduler

Purpose: Background task processors for OCR, analysis, PDF generation, and reminder scheduling.

Testing:
    # Tasks run automatically when triggered via API endpoints
    # For local testing with FastAPI BackgroundTasks

AWS Deployment Notes:
    - Production: Use SQS + Lambda workers instead of FastAPI BackgroundTasks
    - Reminder scheduler: EventBridge rule triggers Lambda every 5 minutes
    - See lambda/ directory for Lambda handler implementations
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
import json

from app.config import settings
from app.services.db import DatabaseService
from app.services.storage import StorageService
from app.services.textract import TextractService
from app.services.llm import LLMService
from app.services.pdfgen import PDFGenService
from app.models.document import Document, DocumentStatus, ProcessingStatus
from app.models.analysis import Analysis, AnalysisStatus
from app.models.reminder import ReminderStatus

logger = logging.getLogger(__name__)

# Initialize services
db_service = DatabaseService()
storage_service = StorageService()
textract_service = TextractService()
llm_service = LLMService()
pdf_service = PDFGenService()

# Global scheduler instance
scheduler = None


# =============================================================================
# OCR PROCESSING TASK
# =============================================================================

async def process_ocr_task(document_id: str):
    """
    Background task to process OCR for a document

    Args:
        document_id: Document ID to process
    """
    logger.info(f"Starting OCR processing for document: {document_id}")

    try:
        # Get document
        document = await db_service.get_document(document_id)

        if not document:
            logger.error(f"Document not found: {document_id}")
            return

        # Get images from storage
        images = []

        for image_key in document.image_keys:
            logger.info(f"Fetching image: {image_key}")

            # Determine if using S3 or local storage
            if settings.USE_LOCAL_STORAGE:
                image_content = await storage_service.get_image(image_key)
                images.append((image_content, None, None))
            else:
                # For Textract, pass S3 reference
                bucket = settings.S3_BUCKET_NAME
                key = f"{settings.S3_PREFIX_IMAGES}{image_key}"
                images.append((None, bucket, key))

        # Extract text from all images
        if len(images) == 1:
            # Single image
            image_content, s3_bucket, s3_key = images[0]
            if image_content:
                # Use image bytes
                ocr_text, confidence, raw_json = await textract_service.extract_text_from_image(
                    image_content=image_content
                )
            else:
                # Use S3 reference
                ocr_text, confidence, raw_json = await textract_service.extract_text_from_image(
                    image_content=None,
                    s3_bucket=s3_bucket,
                    s3_key=s3_key
                )

            raw_jsons = [raw_json] if raw_json else []

        else:
            # Multiple images - need to load content for multi-image processing
            loaded_images = []
            for image_content, s3_bucket, s3_key in images:
                if not image_content and s3_bucket and s3_key:
                    # Load from S3
                    image_content = await storage_service._get_s3(s3_key)
                loaded_images.append((image_content, s3_bucket, s3_key))

            ocr_text, confidence, raw_jsons = await textract_service.extract_text_from_multiple_images(
                loaded_images
            )

        logger.info(f"OCR completed: {len(ocr_text)} characters, {confidence:.1f}% confidence")

        # Save Textract JSON if available
        textract_json_key = None
        if raw_jsons and settings.OCR_PROVIDER == "textract":
            textract_json_key = f"{document_id}/textract.json"
            json_bytes = json.dumps(raw_jsons).encode('utf-8')
            await storage_service.save_textract_json(textract_json_key, json_bytes)
            logger.info(f"Saved Textract JSON: {textract_json_key}")

        # Update document
        document.ocr_text = ocr_text
        document.ocr_confidence = confidence
        document.textract_json_key = textract_json_key
        document.page_count = len(images)
        document.ocr_status = ProcessingStatus.COMPLETED
        document.status = DocumentStatus.COMPLETED
        document.processed_at = datetime.utcnow()

        await db_service.update_document(document)

        logger.info(f"OCR processing completed for document: {document_id}")

    except Exception as e:
        logger.error(f"OCR processing failed for {document_id}: {e}", exc_info=True)

        # Update document status to failed
        document = await db_service.get_document(document_id)
        if document:
            document.ocr_status = ProcessingStatus.FAILED
            document.status = DocumentStatus.FAILED
            document.error_message = str(e)
            await db_service.update_document(document)


# =============================================================================
# ANALYSIS PROCESSING TASK
# =============================================================================

async def process_analysis_task(analysis_id: str):
    """
    Background task to process document analysis

    Args:
        analysis_id: Analysis ID to process
    """
    logger.info(f"Starting analysis processing for: {analysis_id}")

    try:
        # Get analysis
        analysis = await db_service.get_analysis(analysis_id)

        if not analysis:
            logger.error(f"Analysis not found: {analysis_id}")
            return

        # Get document
        document = await db_service.get_document(analysis.document_id)

        if not document or not document.ocr_text:
            logger.error(f"Document or OCR text not found for analysis: {analysis_id}")
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = "Document or OCR text not found"
            await db_service.update_analysis(analysis)
            return

        # Perform analysis
        logger.info(f"Analyzing document: {analysis.document_id}")
        result = await llm_service.analyze_document(document.ocr_text)

        # Update analysis
        analysis.category = result.get('category', 'other')
        analysis.confidence = result.get('confidence', 0.0)
        analysis.summary = result.get('summary')
        analysis.key_entities = result.get('key_entities', {})
        analysis.suggested_tags = result.get('suggested_tags', [])
        analysis.raw_llm_response = json.dumps(result)
        analysis.status = AnalysisStatus.COMPLETED
        analysis.completed_at = datetime.utcnow()

        await db_service.update_analysis(analysis)

        # Update document
        document.analysis_status = ProcessingStatus.COMPLETED
        await db_service.update_document(document)

        logger.info(f"Analysis completed: {analysis_id}, category={analysis.category}")

    except Exception as e:
        logger.error(f"Analysis processing failed for {analysis_id}: {e}", exc_info=True)

        # Update analysis status to failed
        analysis = await db_service.get_analysis(analysis_id)
        if analysis:
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = str(e)
            await db_service.update_analysis(analysis)

            # Update document
            document = await db_service.get_document(analysis.document_id)
            if document:
                document.analysis_status = ProcessingStatus.FAILED
                await db_service.update_document(document)


# =============================================================================
# PDF GENERATION TASK
# =============================================================================

async def generate_pdf_task(document_id: str):
    """
    Background task to generate PDF

    Args:
        document_id: Document ID to generate PDF for
    """
    logger.info(f"Starting PDF generation for document: {document_id}")

    try:
        # Get document
        document = await db_service.get_document(document_id)

        if not document:
            logger.error(f"Document not found: {document_id}")
            return

        # Get analysis if available
        analysis = None
        if document.analysis_id:
            analysis = await db_service.get_analysis(document.analysis_id)

        # Generate PDF
        pdf_bytes = await pdf_service.generate_pdf(
            document=document,
            analysis=analysis,
            include_images=True
        )

        # Save to storage
        pdf_key = f"{document_id}/export.pdf"
        pdf_url = await storage_service.save_pdf(pdf_key, pdf_bytes)

        # Update document
        document.pdf_key = pdf_key
        document.pdf_url = pdf_url
        await db_service.update_document(document)

        logger.info(f"PDF generated successfully: {pdf_key}")

    except Exception as e:
        logger.error(f"PDF generation failed for {document_id}: {e}", exc_info=True)


# =============================================================================
# REMINDER SCHEDULER (for local development)
# =============================================================================

def start_scheduler():
    """
    Start APScheduler for reminder checking (local development only)

    In production, use AWS EventBridge + Lambda instead
    """
    global scheduler

    if settings.SCHEDULER_PROVIDER != "apscheduler":
        logger.info("Scheduler: Using EventBridge (production)")
        return

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        scheduler = AsyncIOScheduler()

        # Schedule reminder check every 5 minutes
        scheduler.add_job(
            check_pending_reminders,
            'interval',
            minutes=5,
            id='check_reminders',
            replace_existing=True
        )

        scheduler.start()
        logger.info("APScheduler started for reminders (checking every 5 minutes)")

    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}", exc_info=True)


def shutdown_scheduler():
    """Shutdown scheduler"""
    global scheduler

    if scheduler:
        scheduler.shutdown()
        logger.info("APScheduler stopped")


async def check_pending_reminders():
    """
    Check for pending reminders that are due

    This function is called by:
    - APScheduler (local development)
    - EventBridge + Lambda (production)
    """
    logger.info("Checking pending reminders")

    try:
        # Get reminders due now
        cutoff_time = datetime.utcnow()
        reminders = await db_service.get_pending_reminders(cutoff_time)

        logger.info(f"Found {len(reminders)} pending reminders")

        for reminder in reminders:
            try:
                # Send notification
                await send_reminder_notification(reminder)

                # Update reminder status
                reminder.status = ReminderStatus.SENT
                reminder.sent_at = datetime.utcnow()
                await db_service.update_reminder(reminder)

                logger.info(f"Reminder sent: {reminder.reminder_id}")

            except Exception as e:
                logger.error(f"Failed to send reminder {reminder.reminder_id}: {e}")

    except Exception as e:
        logger.error(f"Failed to check reminders: {e}", exc_info=True)


async def send_reminder_notification(reminder):
    """
    Send reminder notification

    Args:
        reminder: Reminder object

    Note: This is a stub - implement actual notification logic based on settings.EMAIL_PROVIDER
    """
    logger.info(f"Sending reminder notification: {reminder.title}")

    # Get document for context
    document = await db_service.get_document(reminder.document_id)

    # Build notification message
    message = f"""
    Reminder: {reminder.title}

    {reminder.description or ''}

    Document ID: {reminder.document_id}
    Uploaded: {document.uploaded_at if document else 'Unknown'}

    This is an automated reminder from PostMate.
    """

    # TODO: Implement actual notification based on settings
    if settings.EMAIL_PROVIDER == "ses":
        # Use AWS SES
        logger.info("Would send via SES (not implemented in demo)")
        pass

    elif settings.EMAIL_PROVIDER == "sendgrid":
        # Use SendGrid
        logger.info("Would send via SendGrid (not implemented in demo)")
        pass

    elif settings.EMAIL_PROVIDER == "smtp":
        # Use SMTP
        logger.info("Would send via SMTP (not implemented in demo)")
        pass

    # For demo, just log
    logger.info(f"Reminder notification (demo): {message}")
