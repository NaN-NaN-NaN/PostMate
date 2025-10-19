"""
PostMate Backend - Reminders Endpoints

Purpose: Create and manage reminders for documents

API Endpoints:
    POST /api/v1/reminders - Create reminder
    GET /api/v1/reminders - List reminders (filter by date range)
    GET /api/v1/reminders/calendar - Calendar view
    GET /api/v1/reminders/{reminder_id} - Get reminder
    PUT /api/v1/reminders/{reminder_id} - Update reminder
    DELETE /api/v1/reminders/{reminder_id} - Delete reminder

Testing:
    curl -X POST http://localhost:8080/api/v1/reminders \\
      -H "Content-Type: application/json" \\
      -d '{
        "document_id": "doc_xxx",
        "title": "Pay invoice",
        "reminder_date": "2024-02-15T10:00:00Z"
      }'

AWS Deployment Notes:
    - EventBridge rule triggers Lambda every 5 minutes to check pending reminders
    - Notifications sent via SES (email) or SNS (SMS)
"""

from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import logging
import shortuuid

from app.config import settings
from app.services.db import DatabaseService
from app.models.reminder import Reminder, ReminderStatus

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
db_service = DatabaseService()


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateReminderRequest(BaseModel):
    """Create reminder request"""
    document_id: str = Field(..., description="Document to remind about")
    title: str = Field(..., min_length=1, max_length=200, description="Reminder title")
    description: Optional[str] = Field(None, max_length=1000, description="Optional description")
    reminder_date: datetime = Field(..., description="When to send reminder")
    notification_method: str = Field(default="email", description="email, sms, push")
    notification_target: Optional[str] = Field(None, description="Email address, phone, etc.")


class UpdateReminderRequest(BaseModel):
    """Update reminder request"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    reminder_date: Optional[datetime] = None
    status: Optional[ReminderStatus] = None


class ReminderResponse(BaseModel):
    """Reminder response"""
    reminder_id: str
    document_id: str
    title: str
    description: Optional[str]
    reminder_date: datetime
    status: ReminderStatus
    created_at: datetime
    sent_at: Optional[datetime]
    notification_method: str


class ListRemindersResponse(BaseModel):
    """List reminders response"""
    reminders: List[ReminderResponse]
    total: int


class CalendarItem(BaseModel):
    """Calendar item"""
    date: str  # YYYY-MM-DD
    reminders: List[ReminderResponse]
    count: int


class CalendarResponse(BaseModel):
    """Calendar response"""
    start_date: str
    end_date: str
    items: List[CalendarItem]


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/reminders", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
async def create_reminder(
    request: CreateReminderRequest
) -> ReminderResponse:
    """
    Create a new reminder for a document

    Args:
        request: Reminder details

    Returns:
        ReminderResponse with created reminder
    """
    logger.info(f"Creating reminder for document {request.document_id}")

    # Check if feature is enabled
    if not settings.ENABLE_REMINDERS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reminders feature is disabled"
        )

    # Verify document exists
    document = await db_service.get_document(request.document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {request.document_id} not found"
        )

    # Validate reminder date is in the future
    if request.reminder_date <= datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reminder date must be in the future"
        )

    try:
        # Create reminder
        reminder_id = f"reminder_{shortuuid.uuid()}"
        reminder = Reminder(
            reminder_id=reminder_id,
            document_id=request.document_id,
            title=request.title,
            description=request.description,
            reminder_date=request.reminder_date,
            status=ReminderStatus.PENDING,
            notification_method=request.notification_method,
            notification_target=request.notification_target,
        )

        await db_service.save_reminder(reminder)

        logger.info(f"Reminder created: {reminder_id}")

        return ReminderResponse(
            reminder_id=reminder.reminder_id,
            document_id=reminder.document_id,
            title=reminder.title,
            description=reminder.description,
            reminder_date=reminder.reminder_date,
            status=reminder.status,
            created_at=reminder.created_at,
            sent_at=reminder.sent_at,
            notification_method=reminder.notification_method,
        )

    except Exception as e:
        logger.error(f"Failed to create reminder: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create reminder: {str(e)}"
        )


@router.get("/reminders", response_model=ListRemindersResponse)
async def list_reminders(
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    status_filter: Optional[ReminderStatus] = Query(None, alias="status", description="Filter by status")
) -> ListRemindersResponse:
    """
    List reminders with optional filters

    Args:
        start_date: Optional start date filter
        end_date: Optional end date filter
        status_filter: Optional status filter

    Returns:
        ListRemindersResponse with matching reminders
    """
    logger.info("Listing reminders")

    try:
        reminders = await db_service.list_reminders(
            start_date=start_date,
            end_date=end_date,
            status=status_filter
        )

        reminder_responses = [
            ReminderResponse(
                reminder_id=r.reminder_id,
                document_id=r.document_id,
                title=r.title,
                description=r.description,
                reminder_date=r.reminder_date,
                status=r.status,
                created_at=r.created_at,
                sent_at=r.sent_at,
                notification_method=r.notification_method,
            )
            for r in reminders
        ]

        return ListRemindersResponse(
            reminders=reminder_responses,
            total=len(reminder_responses),
        )

    except Exception as e:
        logger.error(f"Failed to list reminders: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list reminders: {str(e)}"
        )


@router.get("/reminders/calendar", response_model=CalendarResponse)
async def get_calendar(
    start_date: Optional[datetime] = Query(None, description="Calendar start date"),
    end_date: Optional[datetime] = Query(None, description="Calendar end date")
) -> CalendarResponse:
    """
    Get calendar view of reminders

    Args:
        start_date: Start date (default: today)
        end_date: End date (default: 30 days from start)

    Returns:
        CalendarResponse with reminders grouped by date
    """
    logger.info("Getting calendar view")

    # Default date range
    if not start_date:
        start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    if not end_date:
        end_date = start_date + timedelta(days=30)

    try:
        # Get reminders in range
        reminders = await db_service.list_reminders(
            start_date=start_date,
            end_date=end_date,
            status=ReminderStatus.PENDING  # Only show pending
        )

        # Group by date
        calendar_dict: Dict[str, List[Reminder]] = {}

        for reminder in reminders:
            date_key = reminder.reminder_date.strftime('%Y-%m-%d')
            if date_key not in calendar_dict:
                calendar_dict[date_key] = []
            calendar_dict[date_key].append(reminder)

        # Build calendar items
        calendar_items = []

        for date_key in sorted(calendar_dict.keys()):
            day_reminders = calendar_dict[date_key]

            reminder_responses = [
                ReminderResponse(
                    reminder_id=r.reminder_id,
                    document_id=r.document_id,
                    title=r.title,
                    description=r.description,
                    reminder_date=r.reminder_date,
                    status=r.status,
                    created_at=r.created_at,
                    sent_at=r.sent_at,
                    notification_method=r.notification_method,
                )
                for r in day_reminders
            ]

            calendar_items.append(CalendarItem(
                date=date_key,
                reminders=reminder_responses,
                count=len(reminder_responses),
            ))

        return CalendarResponse(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            items=calendar_items,
        )

    except Exception as e:
        logger.error(f"Failed to get calendar: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get calendar: {str(e)}"
        )


@router.get("/reminders/{reminder_id}", response_model=ReminderResponse)
async def get_reminder(reminder_id: str) -> ReminderResponse:
    """Get reminder by ID"""
    logger.info(f"Getting reminder: {reminder_id}")

    reminder = await db_service.get_reminder(reminder_id)

    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reminder {reminder_id} not found"
        )

    return ReminderResponse(
        reminder_id=reminder.reminder_id,
        document_id=reminder.document_id,
        title=reminder.title,
        description=reminder.description,
        reminder_date=reminder.reminder_date,
        status=reminder.status,
        created_at=reminder.created_at,
        sent_at=reminder.sent_at,
        notification_method=reminder.notification_method,
    )


@router.put("/reminders/{reminder_id}", response_model=ReminderResponse)
async def update_reminder(
    reminder_id: str,
    request: UpdateReminderRequest
) -> ReminderResponse:
    """Update reminder"""
    logger.info(f"Updating reminder: {reminder_id}")

    # Get existing reminder
    reminder = await db_service.get_reminder(reminder_id)

    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reminder {reminder_id} not found"
        )

    # Update fields
    if request.title is not None:
        reminder.title = request.title
    if request.description is not None:
        reminder.description = request.description
    if request.reminder_date is not None:
        # Validate future date
        if request.reminder_date <= datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reminder date must be in the future"
            )
        reminder.reminder_date = request.reminder_date
    if request.status is not None:
        reminder.status = request.status

    try:
        await db_service.update_reminder(reminder)

        logger.info(f"Reminder updated: {reminder_id}")

        return ReminderResponse(
            reminder_id=reminder.reminder_id,
            document_id=reminder.document_id,
            title=reminder.title,
            description=reminder.description,
            reminder_date=reminder.reminder_date,
            status=reminder.status,
            created_at=reminder.created_at,
            sent_at=reminder.sent_at,
            notification_method=reminder.notification_method,
        )

    except Exception as e:
        logger.error(f"Failed to update reminder: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update reminder: {str(e)}"
        )


@router.delete("/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reminder(reminder_id: str):
    """Delete reminder"""
    logger.info(f"Deleting reminder: {reminder_id}")

    # Verify exists
    reminder = await db_service.get_reminder(reminder_id)

    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reminder {reminder_id} not found"
        )

    try:
        await db_service.delete_reminder(reminder_id)
        logger.info(f"Reminder deleted: {reminder_id}")

    except Exception as e:
        logger.error(f"Failed to delete reminder: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete reminder: {str(e)}"
        )
