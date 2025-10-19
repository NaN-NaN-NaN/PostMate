"""
PostMate Backend - Chat Models

Purpose: Chat message and session models
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Chat message model"""

    # Primary key
    message_id: str = Field(..., description="Unique message identifier")

    # Foreign key
    document_id: str = Field(..., description="Associated document ID")

    # Message data
    role: str = Field(..., description="user or assistant")
    content: str = Field(..., description="Message content")

    # Timestamp
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item"""
        return {
            'message_id': self.message_id,
            'document_id': self.document_id,
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
        }

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> 'ChatMessage':
        """Create from DynamoDB item"""
        return cls(
            message_id=item['message_id'],
            document_id=item['document_id'],
            role=item['role'],
            content=item['content'],
            timestamp=datetime.fromisoformat(item['timestamp']),
            metadata=item.get('metadata', {}),
        )


class ChatSession(BaseModel):
    """Chat session (for grouping messages)"""

    session_id: str
    document_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_message_at: Optional[datetime] = None
    message_count: int = 0
