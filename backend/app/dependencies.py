"""
PostMate Backend - FastAPI Dependencies

Purpose: Shared dependencies for dependency injection
"""

from fastapi import Depends, HTTPException, status
from typing import Optional

from app.services.db import DatabaseService
from app.services.storage import StorageService
from app.services.textract import TextractService
from app.services.llm import LLMService
from app.services.pdfgen import PDFGenService


# Service dependencies
def get_db_service() -> DatabaseService:
    """Get database service instance"""
    return DatabaseService()


def get_storage_service() -> StorageService:
    """Get storage service instance"""
    return StorageService()


def get_textract_service() -> TextractService:
    """Get Textract/OCR service instance"""
    return TextractService()


def get_llm_service() -> LLMService:
    """Get LLM service instance"""
    return LLMService()


def get_pdf_service() -> PDFGenService:
    """Get PDF generation service instance"""
    return PDFGenService()
