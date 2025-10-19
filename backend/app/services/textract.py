"""
PostMate Backend - OCR Service (Textract/Tesseract)

Purpose: Extract text from images using AWS Textract (production) or Tesseract (local dev).
Parses Textract JSON to preserve reading order and extract structured text.

Testing:
    # Tesseract mode
    service = TextractService()
    text = await service.extract_text_from_image(image_bytes)

    # Textract mode (requires AWS credentials)
    service = TextractService()
    result = await service.extract_text_textract(s3_bucket, s3_key)

AWS Deployment Notes:
    - Textract requires images in S3
    - Use async jobs for multi-page documents
    - SNS topic for job completion notifications
    - IAM role needs textract:DetectDocumentText and textract:AnalyzeDocument permissions
"""

import logging
import json
from typing import Dict, List, Optional, Tuple
import boto3
from botocore.exceptions import ClientError
import pytesseract
from PIL import Image
import io

from app.config import settings

logger = logging.getLogger(__name__)


class TextractService:
    """
    OCR service supporting both Textract (AWS) and Tesseract (local)
    """

    def __init__(self):
        self.provider = settings.OCR_PROVIDER

        if self.provider == "textract":
            self.textract_client = boto3.client(
                'textract',
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
            logger.info("OCR: Using AWS Textract")

        else:
            # Configure Tesseract
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH
            logger.info(f"OCR: Using Tesseract at {settings.TESSERACT_PATH}")

    # =========================================================================
    # PUBLIC METHODS
    # =========================================================================

    async def extract_text_from_image(
        self,
        image_content: bytes,
        s3_bucket: Optional[str] = None,
        s3_key: Optional[str] = None
    ) -> Tuple[str, float, Optional[Dict]]:
        """
        Extract text from image using configured OCR provider

        Args:
            image_content: Image binary content
            s3_bucket: S3 bucket name (for Textract)
            s3_key: S3 key (for Textract)

        Returns:
            Tuple of (extracted_text, confidence, raw_json)
        """
        if self.provider == "textract":
            return await self._extract_textract(s3_bucket, s3_key, image_content)
        else:
            return await self._extract_tesseract(image_content)

    async def extract_text_from_multiple_images(
        self,
        images: List[Tuple[bytes, Optional[str], Optional[str]]]
    ) -> Tuple[str, float, List[Dict]]:
        """
        Extract text from multiple images and combine

        Args:
            images: List of (image_content, s3_bucket, s3_key) tuples

        Returns:
            Tuple of (combined_text, avg_confidence, list_of_raw_jsons)
        """
        all_text = []
        all_confidence = []
        all_json = []

        for idx, (image_content, s3_bucket, s3_key) in enumerate(images, 1):
            logger.info(f"Processing image {idx}/{len(images)}")

            text, confidence, raw_json = await self.extract_text_from_image(
                image_content, s3_bucket, s3_key
            )

            all_text.append(f"--- Page {idx} ---\n{text}")
            all_confidence.append(confidence)
            if raw_json:
                all_json.append(raw_json)

        combined_text = "\n\n".join(all_text)
        avg_confidence = sum(all_confidence) / len(all_confidence) if all_confidence else 0.0

        return combined_text, avg_confidence, all_json

    # =========================================================================
    # TEXTRACT IMPLEMENTATION
    # =========================================================================

    async def _extract_textract(
        self,
        s3_bucket: Optional[str],
        s3_key: Optional[str],
        image_content: Optional[bytes] = None
    ) -> Tuple[str, float, Dict]:
        """
        Extract text using AWS Textract

        Args:
            s3_bucket: S3 bucket name
            s3_key: S3 object key
            image_content: Direct image bytes (alternative to S3)

        Returns:
            Tuple of (text, confidence, raw_response)
        """
        try:
            # Textract can accept either S3 reference or direct bytes
            if s3_bucket and s3_key:
                # Use S3 reference (recommended for production)
                response = self.textract_client.detect_document_text(
                    Document={
                        'S3Object': {
                            'Bucket': s3_bucket,
                            'Name': s3_key
                        }
                    }
                )
            elif image_content:
                # Use direct bytes (for small images, < 5MB)
                response = self.textract_client.detect_document_text(
                    Document={
                        'Bytes': image_content
                    }
                )
            else:
                raise ValueError("Either S3 reference or image_content must be provided")

            # Parse Textract response
            text, confidence = self._parse_textract_response(response)

            logger.info(f"Textract extracted {len(text)} characters with {confidence:.2f}% confidence")

            return text, confidence, response

        except ClientError as e:
            logger.error(f"Textract error: {e}")
            raise

    def _parse_textract_response(self, response: Dict) -> Tuple[str, float]:
        """
        Parse Textract response to extract text in reading order

        Algorithm:
        1. Extract all LINE blocks (Textract organizes text into blocks)
        2. Sort by geometry (top-to-bottom, left-to-right)
        3. Join lines with newlines to preserve document structure

        Args:
            response: Textract API response

        Returns:
            Tuple of (extracted_text, average_confidence)
        """
        blocks = response.get('Blocks', [])

        # Extract LINE blocks with geometry
        lines = []
        confidences = []

        for block in blocks:
            if block['BlockType'] == 'LINE':
                text = block.get('Text', '')
                confidence = block.get('Confidence', 0.0)

                # Get geometry for sorting
                geometry = block.get('Geometry', {})
                bounding_box = geometry.get('BoundingBox', {})

                top = bounding_box.get('Top', 0.0)
                left = bounding_box.get('Left', 0.0)

                lines.append({
                    'text': text,
                    'confidence': confidence,
                    'top': top,
                    'left': left
                })

                confidences.append(confidence)

        # Sort by reading order: top-to-bottom, then left-to-right
        # Group lines by vertical position (tolerance for same row)
        sorted_lines = sorted(lines, key=lambda x: (round(x['top'] * 100), x['left']))

        # Extract text
        extracted_text = '\n'.join(line['text'] for line in sorted_lines)

        # Calculate average confidence
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return extracted_text, avg_confidence

    # =========================================================================
    # TESSERACT IMPLEMENTATION
    # =========================================================================

    async def _extract_tesseract(
        self,
        image_content: bytes
    ) -> Tuple[str, float, None]:
        """
        Extract text using Tesseract OCR

        Args:
            image_content: Image binary content

        Returns:
            Tuple of (text, confidence, None)
        """
        try:
            # Open image with PIL
            image = Image.open(io.BytesIO(image_content))

            # Run Tesseract
            custom_config = settings.TESSERACT_CONFIG
            text = pytesseract.image_to_string(
                image,
                lang=settings.TESSERACT_LANG,
                config=custom_config
            )

            # Get confidence data
            data = pytesseract.image_to_data(
                image,
                lang=settings.TESSERACT_LANG,
                output_type=pytesseract.Output.DICT
            )

            # Calculate average confidence (excluding -1 values which mean no text)
            confidences = [
                float(conf) for conf in data['conf']
                if conf != -1 and str(conf).replace('.','').replace('-','').isdigit()
            ]

            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            logger.info(f"Tesseract extracted {len(text)} characters with {avg_confidence:.2f}% confidence")

            return text.strip(), avg_confidence, None

        except Exception as e:
            logger.error(f"Tesseract error: {e}")
            raise

    # =========================================================================
    # ASYNC TEXTRACT (for multi-page documents)
    # =========================================================================

    async def start_document_analysis_async(
        self,
        s3_bucket: str,
        s3_key: str
    ) -> str:
        """
        Start async Textract job for large/multi-page documents

        Args:
            s3_bucket: S3 bucket name
            s3_key: S3 object key

        Returns:
            Job ID for polling
        """
        if self.provider != "textract":
            raise NotImplementedError("Async jobs only available with Textract")

        try:
            response = self.textract_client.start_document_text_detection(
                DocumentLocation={
                    'S3Object': {
                        'Bucket': s3_bucket,
                        'Name': s3_key
                    }
                },
                NotificationChannel={
                    'SNSTopicArn': settings.TEXTRACT_SNS_TOPIC_ARN,
                    'RoleArn': settings.TEXTRACT_ROLE_ARN
                } if settings.TEXTRACT_SNS_TOPIC_ARN else None
            )

            job_id = response['JobId']
            logger.info(f"Started async Textract job: {job_id}")

            return job_id

        except ClientError as e:
            logger.error(f"Failed to start async Textract job: {e}")
            raise

    async def get_document_analysis_result(self, job_id: str) -> Tuple[str, str, Optional[Dict]]:
        """
        Get result of async Textract job

        Args:
            job_id: Job ID from start_document_analysis_async

        Returns:
            Tuple of (status, text, raw_response)
            Status: 'IN_PROGRESS', 'SUCCEEDED', 'FAILED'
        """
        if self.provider != "textract":
            raise NotImplementedError("Async jobs only available with Textract")

        try:
            response = self.textract_client.get_document_text_detection(
                JobId=job_id
            )

            status = response['JobStatus']

            if status == 'SUCCEEDED':
                text, confidence = self._parse_textract_response(response)
                return status, text, response

            return status, "", response

        except ClientError as e:
            logger.error(f"Failed to get Textract job result: {e}")
            raise
