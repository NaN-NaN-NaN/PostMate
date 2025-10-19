"""
PostMate Backend - Chat Endpoints

Purpose: Q&A chat interface for asking questions about documents

API Endpoints:
    POST /api/v1/chat/{doc_id} - Ask question about document
    GET /api/v1/chat/{doc_id}/history - Get chat history

Testing:
    curl -X POST http://localhost:8080/api/v1/chat/doc_xxx \\
      -H "Content-Type: application/json" \\
      -d '{"question": "What is the total amount?"}'

    curl http://localhost:8080/api/v1/chat/doc_xxx/history

AWS Deployment Notes:
    - Chat uses document OCR text as context
    - Long documents are summarized to fit in context window
    - Chat history stored in DynamoDB for continuity
"""

from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging
import shortuuid

from app.config import settings
from app.services.db import DatabaseService
from app.services.llm import LLMService
from app.models.document import Document, ProcessingStatus
from app.models.chat import ChatMessage

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
db_service = DatabaseService()
llm_service = LLMService()


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class ChatRequest(BaseModel):
    """Chat question request"""
    question: str = Field(..., min_length=1, max_length=1000, description="Question about the document")


class ChatResponse(BaseModel):
    """Chat answer response"""
    message_id: str
    question: str
    answer: str
    timestamp: datetime


class ChatHistoryItem(BaseModel):
    """Chat history item"""
    message_id: str
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime


class ChatHistoryResponse(BaseModel):
    """Chat history response"""
    document_id: str
    messages: List[ChatHistoryItem]
    total_messages: int


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/chat/{doc_id}", response_model=ChatResponse)
async def ask_question(
    doc_id: str,
    request: ChatRequest
) -> ChatResponse:
    """
    Ask a question about a document

    Document must have completed OCR first.
    Uses document text as context for answering questions.

    Args:
        doc_id: Document ID
        request: Question to ask

    Returns:
        ChatResponse with answer
    """
    logger.info(f"Chat question for document {doc_id}: {request.question}")

    # Check if feature is enabled
    if not settings.ENABLE_CHAT:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat feature is disabled"
        )

    # Get document
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
            detail=f"OCR must be completed before chat. Current status: {document.ocr_status}"
        )

    if not document.ocr_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OCR text available for chat"
        )

    try:
        # Get chat history for context
        chat_history = await db_service.get_chat_history(doc_id, limit=10)

        # Convert to LLM format
        history_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in chat_history
        ]

        # Get answer from LLM
        answer = await llm_service.chat(
            question=request.question,
            context=document.ocr_text,
            chat_history=history_messages
        )

        # Save user question
        user_message_id = f"msg_{shortuuid.uuid()}"
        user_message = ChatMessage(
            message_id=user_message_id,
            document_id=doc_id,
            role="user",
            content=request.question,
        )
        await db_service.save_chat_message(user_message)

        # Save assistant answer
        assistant_message_id = f"msg_{shortuuid.uuid()}"
        assistant_message = ChatMessage(
            message_id=assistant_message_id,
            document_id=doc_id,
            role="assistant",
            content=answer,
        )
        await db_service.save_chat_message(assistant_message)

        logger.info(f"Chat answer generated for {doc_id}")

        return ChatResponse(
            message_id=assistant_message_id,
            question=request.question,
            answer=answer,
            timestamp=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat failed: {str(e)}"
        )


@router.get("/chat/{doc_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    doc_id: str,
    limit: int = 50
) -> ChatHistoryResponse:
    """
    Get chat history for a document

    Args:
        doc_id: Document ID
        limit: Maximum number of messages to return

    Returns:
        ChatHistoryResponse with message history
    """
    logger.info(f"Chat history requested for document: {doc_id}")

    # Verify document exists
    document = await db_service.get_document(doc_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found"
        )

    # Get chat history
    messages = await db_service.get_chat_history(doc_id, limit=limit)

    # Convert to response format
    history_items = [
        ChatHistoryItem(
            message_id=msg.message_id,
            role=msg.role,
            content=msg.content,
            timestamp=msg.timestamp,
        )
        for msg in messages
    ]

    return ChatHistoryResponse(
        document_id=doc_id,
        messages=history_items,
        total_messages=len(history_items),
    )
