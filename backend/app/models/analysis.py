"""
PostMate Backend - Analysis Model

Purpose: Document analysis result model
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class AnalysisStatus(str, Enum):
    """Analysis status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentCategory(str, Enum):
    """Document category types"""
    INVOICE = "invoice"
    RECEIPT = "receipt"
    LETTER = "letter"
    CONTRACT = "contract"
    FORM = "form"
    OTHER = "other"


class Analysis(BaseModel):
    """Analysis result model"""

    # Primary key
    analysis_id: str = Field(..., description="Unique analysis identifier")

    # Foreign key
    document_id: str = Field(..., description="Associated document ID")

    # Status
    status: AnalysisStatus = Field(default=AnalysisStatus.PENDING)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Analysis results
    category: DocumentCategory = Field(default=DocumentCategory.OTHER)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: Optional[str] = None
    key_entities: Dict[str, Any] = Field(default_factory=dict)
    suggested_tags: List[str] = Field(default_factory=list)

    # Raw LLM response (for debugging)
    raw_llm_response: Optional[str] = None

    # Error tracking
    error_message: Optional[str] = None

    class Config:
        use_enum_values = True

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item"""
        item = {
            'analysis_id': self.analysis_id,
            'document_id': self.document_id,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'category': self.category,
            'confidence': str(self.confidence),  # Store as string in DynamoDB
            'key_entities': self.key_entities,
            'suggested_tags': self.suggested_tags,
        }

        # Add optional fields
        if self.completed_at:
            item['completed_at'] = self.completed_at.isoformat()
        if self.summary:
            item['summary'] = self.summary
        if self.raw_llm_response:
            item['raw_llm_response'] = self.raw_llm_response
        if self.error_message:
            item['error_message'] = self.error_message

        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> 'Analysis':
        """Create from DynamoDB item"""
        return cls(
            analysis_id=item['analysis_id'],
            document_id=item['document_id'],
            status=item.get('status', AnalysisStatus.PENDING),
            created_at=datetime.fromisoformat(item['created_at']),
            completed_at=datetime.fromisoformat(item['completed_at']) if item.get('completed_at') else None,
            category=item.get('category', DocumentCategory.OTHER),
            confidence=float(item.get('confidence', 0.0)),
            summary=item.get('summary'),
            key_entities=item.get('key_entities', {}),
            suggested_tags=item.get('suggested_tags', []),
            raw_llm_response=item.get('raw_llm_response'),
            error_message=item.get('error_message'),
        )
