"""
PostMate Backend - Document Model

Purpose: Document data model with DynamoDB serialization
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class DocumentStatus(str, Enum):
    """Document processing status"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStatus(str, Enum):
    """Individual processing step status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(BaseModel):
    """Document model"""

    # Primary key
    document_id: str = Field(..., description="Unique document identifier")

    # Status
    status: DocumentStatus = Field(default=DocumentStatus.UPLOADED)

    # Timestamps
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None

    # Images
    image_urls: List[str] = Field(default_factory=list, description="S3 URLs or local paths")
    image_keys: List[str] = Field(default_factory=list, description="Storage keys")
    image_count: int = Field(default=0)

    # OCR results
    ocr_status: ProcessingStatus = Field(default=ProcessingStatus.PENDING)
    ocr_text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    textract_json_key: Optional[str] = None
    page_count: Optional[int] = None

    # Analysis
    analysis_status: ProcessingStatus = Field(default=ProcessingStatus.PENDING)
    analysis_id: Optional[str] = None

    # PDF export
    pdf_key: Optional[str] = None
    pdf_url: Optional[str] = None

    # Error tracking
    error_message: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item"""
        item = {
            'document_id': self.document_id,
            'status': self.status,
            'uploaded_at': self.uploaded_at.isoformat(),
            'image_urls': self.image_urls,
            'image_keys': self.image_keys,
            'image_count': self.image_count,
            'ocr_status': self.ocr_status,
            'analysis_status': self.analysis_status,
            'metadata': self.metadata,
        }

        # Add optional fields
        if self.processed_at:
            item['processed_at'] = self.processed_at.isoformat()
        if self.ocr_text:
            item['ocr_text'] = self.ocr_text
        if self.ocr_confidence is not None:
            item['ocr_confidence'] = str(self.ocr_confidence)  # DynamoDB doesn't support float
        if self.textract_json_key:
            item['textract_json_key'] = self.textract_json_key
        if self.page_count:
            item['page_count'] = self.page_count
        if self.analysis_id:
            item['analysis_id'] = self.analysis_id
        if self.pdf_key:
            item['pdf_key'] = self.pdf_key
        if self.pdf_url:
            item['pdf_url'] = self.pdf_url
        if self.error_message:
            item['error_message'] = self.error_message

        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> 'Document':
        """Create from DynamoDB item"""
        return cls(
            document_id=item['document_id'],
            status=item['status'],
            uploaded_at=datetime.fromisoformat(item['uploaded_at']),
            processed_at=datetime.fromisoformat(item['processed_at']) if item.get('processed_at') else None,
            image_urls=item.get('image_urls', []),
            image_keys=item.get('image_keys', []),
            image_count=item.get('image_count', 0),
            ocr_status=item.get('ocr_status', ProcessingStatus.PENDING),
            ocr_text=item.get('ocr_text'),
            ocr_confidence=float(item['ocr_confidence']) if item.get('ocr_confidence') else None,
            textract_json_key=item.get('textract_json_key'),
            page_count=item.get('page_count'),
            analysis_status=item.get('analysis_status', ProcessingStatus.PENDING),
            analysis_id=item.get('analysis_id'),
            pdf_key=item.get('pdf_key'),
            pdf_url=item.get('pdf_url'),
            error_message=item.get('error_message'),
            metadata=item.get('metadata', {}),
        )
