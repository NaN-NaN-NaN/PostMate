"""
PostMate Backend - Reminder Model

Purpose: Reminder model for document-related notifications
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class ReminderStatus(str, Enum):
    """Reminder status"""
    PENDING = "pending"
    SENT = "sent"
    CANCELLED = "cancelled"


class Reminder(BaseModel):
    """Reminder model"""

    # Primary key
    reminder_id: str = Field(..., description="Unique reminder identifier")

    # Foreign key
    document_id: str = Field(..., description="Associated document ID")

    # Reminder data
    title: str = Field(..., description="Reminder title")
    description: Optional[str] = None
    reminder_date: datetime = Field(..., description="When to send reminder")

    # Status
    status: ReminderStatus = Field(default=ReminderStatus.PENDING)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None

    # Notification settings
    notification_method: str = Field(default="email", description="email, sms, push")
    notification_target: Optional[str] = None  # email address, phone, etc.

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item"""
        item = {
            'reminder_id': self.reminder_id,
            'document_id': self.document_id,
            'title': self.title,
            'reminder_date': self.reminder_date.isoformat(),
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'notification_method': self.notification_method,
            'metadata': self.metadata,
        }

        # Add optional fields
        if self.description:
            item['description'] = self.description
        if self.sent_at:
            item['sent_at'] = self.sent_at.isoformat()
        if self.notification_target:
            item['notification_target'] = self.notification_target

        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> 'Reminder':
        """Create from DynamoDB item"""
        return cls(
            reminder_id=item['reminder_id'],
            document_id=item['document_id'],
            title=item['title'],
            description=item.get('description'),
            reminder_date=datetime.fromisoformat(item['reminder_date']),
            status=item.get('status', ReminderStatus.PENDING),
            created_at=datetime.fromisoformat(item['created_at']),
            sent_at=datetime.fromisoformat(item['sent_at']) if item.get('sent_at') else None,
            notification_method=item.get('notification_method', 'email'),
            notification_target=item.get('notification_target'),
            metadata=item.get('metadata', {}),
        )
