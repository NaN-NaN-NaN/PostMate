"""
PostMate Backend - DynamoDB Database Service

Purpose: Unified database interface for DynamoDB (AWS or Local).
Handles documents, analyses, chats, and reminders.

Testing:
    # DynamoDB Local
    db = DatabaseService()
    await db.save_document(document)
    doc = await db.get_document("doc_123")

AWS Deployment Notes:
    - Tables created by deploy_aws.sh script
    - Uses on-demand billing (PAY_PER_REQUEST)
    - IAM role needs dynamodb:PutItem, GetItem, Query, Scan, UpdateItem, DeleteItem
    - Consider DynamoDB Streams for audit logging
    - Enable point-in-time recovery for production
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from app.config import settings
from app.models.document import Document
from app.models.analysis import Analysis
from app.models.chat import ChatMessage, ChatSession
from app.models.reminder import Reminder

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    Database service for DynamoDB operations
    """

    def __init__(self):
        # Initialize DynamoDB client
        if settings.USE_DYNAMODB_LOCAL:
            self.dynamodb = boto3.resource(
                'dynamodb',
                endpoint_url=settings.DYNAMODB_LOCAL_ENDPOINT,
                region_name=settings.AWS_REGION,
                aws_access_key_id='local',
                aws_secret_access_key='local'
            )
            logger.info(f"Database: Using DynamoDB Local at {settings.DYNAMODB_LOCAL_ENDPOINT}")
        else:
            self.dynamodb = boto3.resource(
                'dynamodb',
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
            logger.info("Database: Using DynamoDB AWS")

        # Get table references
        self.documents_table = self.dynamodb.Table(settings.DYNAMODB_TABLE_DOCUMENTS)
        self.analyses_table = self.dynamodb.Table(settings.DYNAMODB_TABLE_ANALYSES)
        self.chats_table = self.dynamodb.Table(settings.DYNAMODB_TABLE_CHATS)
        self.reminders_table = self.dynamodb.Table(settings.DYNAMODB_TABLE_REMINDERS)

    # =========================================================================
    # TABLE VERIFICATION
    # =========================================================================

    async def verify_tables(self):
        """Verify that all required tables exist"""
        tables = [
            self.documents_table,
            self.analyses_table,
            self.chats_table,
            self.reminders_table,
        ]

        for table in tables:
            try:
                table.load()
                logger.info(f"Table verified: {table.name}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    logger.error(f"Table not found: {table.name}")
                    raise
                else:
                    raise

    # =========================================================================
    # DOCUMENTS
    # =========================================================================

    async def save_document(self, document: Document) -> bool:
        """Save document to database"""
        try:
            item = document.to_dynamodb_item()
            self.documents_table.put_item(Item=item)
            logger.info(f"Saved document: {document.document_id}")
            return True

        except ClientError as e:
            logger.error(f"Failed to save document: {e}")
            raise

    async def get_document(self, document_id: str) -> Optional[Document]:
        """Get document by ID"""
        try:
            response = self.documents_table.get_item(
                Key={'document_id': document_id}
            )

            if 'Item' in response:
                return Document.from_dynamodb_item(response['Item'])

            return None

        except ClientError as e:
            logger.error(f"Failed to get document: {e}")
            raise

    async def update_document(self, document: Document) -> bool:
        """Update existing document"""
        try:
            item = document.to_dynamodb_item()
            self.documents_table.put_item(Item=item)
            logger.info(f"Updated document: {document.document_id}")
            return True

        except ClientError as e:
            logger.error(f"Failed to update document: {e}")
            raise

    async def search_documents(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Document]:
        """
        Search documents with filters

        Note: DynamoDB doesn't natively support full-text search.
        For production, consider:
        - Amazon OpenSearch Service
        - DynamoDB + Lambda + OpenSearch pipeline
        - Client-side filtering (as implemented here)
        """
        try:
            # Scan all documents (for demo; use secondary index in production)
            response = self.documents_table.scan(Limit=limit)

            documents = [
                Document.from_dynamodb_item(item)
                for item in response.get('Items', [])
            ]

            # Filter by query (simple contains search)
            if query:
                query_lower = query.lower()
                documents = [
                    doc for doc in documents
                    if doc.ocr_text and query_lower in doc.ocr_text.lower()
                ]

            # Filter by date range
            if start_date:
                documents = [
                    doc for doc in documents
                    if doc.uploaded_at >= start_date
                ]

            if end_date:
                documents = [
                    doc for doc in documents
                    if doc.uploaded_at <= end_date
                ]

            # Sort by upload date (newest first)
            documents.sort(key=lambda x: x.uploaded_at, reverse=True)

            logger.info(f"Search returned {len(documents)} documents")

            return documents

        except ClientError as e:
            logger.error(f"Failed to search documents: {e}")
            raise

    # =========================================================================
    # ANALYSES
    # =========================================================================

    async def save_analysis(self, analysis: Analysis) -> bool:
        """Save analysis to database"""
        try:
            item = analysis.to_dynamodb_item()
            self.analyses_table.put_item(Item=item)
            logger.info(f"Saved analysis: {analysis.analysis_id}")
            return True

        except ClientError as e:
            logger.error(f"Failed to save analysis: {e}")
            raise

    async def get_analysis(self, analysis_id: str) -> Optional[Analysis]:
        """Get analysis by ID"""
        try:
            response = self.analyses_table.get_item(
                Key={'analysis_id': analysis_id}
            )

            if 'Item' in response:
                return Analysis.from_dynamodb_item(response['Item'])

            return None

        except ClientError as e:
            logger.error(f"Failed to get analysis: {e}")
            raise

    async def get_analysis_by_document(self, document_id: str) -> Optional[Analysis]:
        """Get analysis for a document"""
        try:
            # Query using GSI on document_id (or scan if no GSI)
            response = self.analyses_table.scan(
                FilterExpression=Attr('document_id').eq(document_id)
            )

            items = response.get('Items', [])

            if items:
                # Return most recent analysis
                items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
                return Analysis.from_dynamodb_item(items[0])

            return None

        except ClientError as e:
            logger.error(f"Failed to get analysis by document: {e}")
            raise

    async def update_analysis(self, analysis: Analysis) -> bool:
        """Update existing analysis"""
        try:
            item = analysis.to_dynamodb_item()
            self.analyses_table.put_item(Item=item)
            logger.info(f"Updated analysis: {analysis.analysis_id}")
            return True

        except ClientError as e:
            logger.error(f"Failed to update analysis: {e}")
            raise

    # =========================================================================
    # CHATS
    # =========================================================================

    async def save_chat_message(self, message: ChatMessage) -> bool:
        """Save chat message"""
        try:
            item = message.to_dynamodb_item()
            self.chats_table.put_item(Item=item)
            logger.info(f"Saved chat message: {message.message_id}")
            return True

        except ClientError as e:
            logger.error(f"Failed to save chat message: {e}")
            raise

    async def get_chat_history(
        self,
        document_id: str,
        limit: int = 50
    ) -> List[ChatMessage]:
        """Get chat history for a document"""
        try:
            # Query using GSI on document_id (or scan if no GSI)
            response = self.chats_table.scan(
                FilterExpression=Attr('document_id').eq(document_id)
            )

            messages = [
                ChatMessage.from_dynamodb_item(item)
                for item in response.get('Items', [])
            ]

            # Sort by timestamp
            messages.sort(key=lambda x: x.timestamp)

            return messages[-limit:]  # Return last N messages

        except ClientError as e:
            logger.error(f"Failed to get chat history: {e}")
            raise

    # =========================================================================
    # REMINDERS
    # =========================================================================

    async def save_reminder(self, reminder: Reminder) -> bool:
        """Save reminder"""
        try:
            item = reminder.to_dynamodb_item()
            self.reminders_table.put_item(Item=item)
            logger.info(f"Saved reminder: {reminder.reminder_id}")
            return True

        except ClientError as e:
            logger.error(f"Failed to save reminder: {e}")
            raise

    async def get_reminder(self, reminder_id: str) -> Optional[Reminder]:
        """Get reminder by ID"""
        try:
            response = self.reminders_table.get_item(
                Key={'reminder_id': reminder_id}
            )

            if 'Item' in response:
                return Reminder.from_dynamodb_item(response['Item'])

            return None

        except ClientError as e:
            logger.error(f"Failed to get reminder: {e}")
            raise

    async def list_reminders(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[str] = None
    ) -> List[Reminder]:
        """List reminders with filters"""
        try:
            # Scan with filters
            filter_expressions = []

            if start_date:
                filter_expressions.append(
                    Attr('reminder_date').gte(start_date.isoformat())
                )

            if end_date:
                filter_expressions.append(
                    Attr('reminder_date').lte(end_date.isoformat())
                )

            if status:
                filter_expressions.append(
                    Attr('status').eq(status)
                )

            # Build filter expression
            if filter_expressions:
                filter_expr = filter_expressions[0]
                for expr in filter_expressions[1:]:
                    filter_expr = filter_expr & expr

                response = self.reminders_table.scan(
                    FilterExpression=filter_expr
                )
            else:
                response = self.reminders_table.scan()

            reminders = [
                Reminder.from_dynamodb_item(item)
                for item in response.get('Items', [])
            ]

            # Sort by reminder date
            reminders.sort(key=lambda x: x.reminder_date)

            return reminders

        except ClientError as e:
            logger.error(f"Failed to list reminders: {e}")
            raise

    async def update_reminder(self, reminder: Reminder) -> bool:
        """Update existing reminder"""
        try:
            item = reminder.to_dynamodb_item()
            self.reminders_table.put_item(Item=item)
            logger.info(f"Updated reminder: {reminder.reminder_id}")
            return True

        except ClientError as e:
            logger.error(f"Failed to update reminder: {e}")
            raise

    async def delete_reminder(self, reminder_id: str) -> bool:
        """Delete reminder"""
        try:
            self.reminders_table.delete_item(
                Key={'reminder_id': reminder_id}
            )
            logger.info(f"Deleted reminder: {reminder_id}")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete reminder: {e}")
            raise

    async def get_pending_reminders(self, cutoff_time: datetime) -> List[Reminder]:
        """Get reminders that are due (for scheduler)"""
        try:
            response = self.reminders_table.scan(
                FilterExpression=Attr('reminder_date').lte(cutoff_time.isoformat()) & Attr('status').eq('pending')
            )

            reminders = [
                Reminder.from_dynamodb_item(item)
                for item in response.get('Items', [])
            ]

            return reminders

        except ClientError as e:
            logger.error(f"Failed to get pending reminders: {e}")
            raise
