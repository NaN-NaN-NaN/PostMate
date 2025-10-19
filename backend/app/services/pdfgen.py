"""
PostMate Backend - PDF Generation Service

Purpose: Generate annotated PDFs with OCR text, analysis results, and original images.

Testing:
    service = PDFGenService()
    pdf_bytes = await service.generate_pdf(document, analysis)

AWS Deployment Notes:
    - PDFs saved to S3 for storage
    - Uses ReportLab for PDF generation (pure Python, no external dependencies)
    - Can handle multi-page documents with images
"""

import logging
from typing import Optional
from datetime import datetime
import io

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.lib import colors

from app.config import settings
from app.models.document import Document
from app.models.analysis import Analysis

logger = logging.getLogger(__name__)


class PDFGenService:
    """
    PDF generation service for creating annotated document exports
    """

    def __init__(self):
        self.page_size = letter if settings.PDF_PAGE_SIZE == "LETTER" else A4
        self.margin = settings.PDF_MARGIN
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2C3E50'),
            spaceAfter=30,
            alignment=TA_CENTER,
        ))

        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#34495E'),
            spaceAfter=12,
            spaceBefore=12,
        ))

        # Body text style
        self.styles.add(ParagraphStyle(
            name='BodyText',
            parent=self.styles['Normal'],
            fontSize=settings.PDF_FONT_SIZE,
            alignment=TA_JUSTIFY,
            spaceAfter=12,
        ))

    async def generate_pdf(
        self,
        document: Document,
        analysis: Optional[Analysis] = None,
        include_images: bool = True
    ) -> bytes:
        """
        Generate annotated PDF for document

        Args:
            document: Document object with OCR text
            analysis: Optional analysis results
            include_images: Whether to include original images

        Returns:
            PDF bytes
        """
        logger.info(f"Generating PDF for document {document.document_id}")

        # Create PDF buffer
        buffer = io.BytesIO()

        # Create document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=self.page_size,
            rightMargin=self.margin,
            leftMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin,
        )

        # Build content
        story = []

        # Title page
        story.extend(self._build_title_page(document, analysis))
        story.append(PageBreak())

        # Analysis section
        if analysis:
            story.extend(self._build_analysis_section(analysis))
            story.append(PageBreak())

        # OCR text section
        if document.ocr_text:
            story.extend(self._build_ocr_section(document))
            story.append(PageBreak())

        # Images section
        if include_images and document.image_urls:
            story.extend(self._build_images_section(document))

        # Build PDF
        doc.build(story)

        # Get PDF bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()

        logger.info(f"PDF generated: {len(pdf_bytes)} bytes")

        return pdf_bytes

    def _build_title_page(self, document: Document, analysis: Optional[Analysis]) -> list:
        """Build title page content"""
        elements = []

        # Title
        elements.append(Paragraph("PostMate Document Report", self.styles['CustomTitle']))
        elements.append(Spacer(1, 0.5 * inch))

        # Document info table
        data = [
            ['Document ID:', document.document_id],
            ['Uploaded:', document.uploaded_at.strftime('%Y-%m-%d %H:%M:%S UTC')],
            ['Pages:', str(document.page_count or document.image_count)],
            ['OCR Status:', document.ocr_status],
        ]

        if analysis:
            data.extend([
                ['Category:', analysis.category],
                ['Confidence:', f"{analysis.confidence * 100:.1f}%"],
            ])

        table = Table(data, colWidths=[2 * inch, 4 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ECF0F1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2C3E50')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#BDC3C7')),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 0.5 * inch))

        # Generation timestamp
        elements.append(Paragraph(
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            self.styles['Normal']
        ))

        return elements

    def _build_analysis_section(self, analysis: Analysis) -> list:
        """Build analysis section content"""
        elements = []

        elements.append(Paragraph("Analysis Results", self.styles['CustomTitle']))
        elements.append(Spacer(1, 0.3 * inch))

        # Summary
        elements.append(Paragraph("Summary", self.styles['SectionHeader']))
        elements.append(Paragraph(analysis.summary or "No summary available", self.styles['BodyText']))
        elements.append(Spacer(1, 0.2 * inch))

        # Key entities
        if analysis.key_entities:
            elements.append(Paragraph("Key Information", self.styles['SectionHeader']))

            entity_data = [[k, str(v)] for k, v in analysis.key_entities.items() if v]

            if entity_data:
                entity_table = Table(entity_data, colWidths=[2 * inch, 4 * inch])
                entity_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8F8F5')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2C3E50')),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#BDC3C7')),
                ]))

                elements.append(entity_table)
                elements.append(Spacer(1, 0.2 * inch))

        # Tags
        if analysis.suggested_tags:
            elements.append(Paragraph("Tags", self.styles['SectionHeader']))
            tags_text = ", ".join(analysis.suggested_tags)
            elements.append(Paragraph(tags_text, self.styles['BodyText']))

        return elements

    def _build_ocr_section(self, document: Document) -> list:
        """Build OCR text section"""
        elements = []

        elements.append(Paragraph("Extracted Text (OCR)", self.styles['CustomTitle']))
        elements.append(Spacer(1, 0.3 * inch))

        # OCR confidence
        if document.ocr_confidence:
            elements.append(Paragraph(
                f"OCR Confidence: {document.ocr_confidence:.1f}%",
                self.styles['Normal']
            ))
            elements.append(Spacer(1, 0.2 * inch))

        # OCR text
        # Split into paragraphs and escape HTML
        text_paragraphs = document.ocr_text.split('\n\n')

        for para in text_paragraphs:
            if para.strip():
                # Escape HTML entities
                para_escaped = para.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                elements.append(Paragraph(para_escaped, self.styles['BodyText']))

        return elements

    def _build_images_section(self, document: Document) -> list:
        """Build images section"""
        elements = []

        elements.append(Paragraph("Original Images", self.styles['CustomTitle']))
        elements.append(Spacer(1, 0.3 * inch))

        # Note: In production, you'd fetch images from storage
        # For now, we'll add placeholders
        for idx, image_url in enumerate(document.image_urls, 1):
            elements.append(Paragraph(f"Image {idx}", self.styles['SectionHeader']))
            elements.append(Paragraph(f"Source: {image_url}", self.styles['Normal']))

            # TODO: Fetch actual image from storage and embed
            # image_bytes = await storage_service.get_image(document.image_keys[idx-1])
            # img = RLImage(io.BytesIO(image_bytes))
            # img.drawHeight = 4 * inch
            # img.drawWidth = 6 * inch
            # elements.append(img)

            elements.append(Spacer(1, 0.3 * inch))

            if idx < len(document.image_urls):
                elements.append(PageBreak())

        return elements

    async def generate_simple_pdf(
        self,
        title: str,
        content: str
    ) -> bytes:
        """
        Generate simple PDF with just title and content

        Args:
            title: PDF title
            content: Text content

        Returns:
            PDF bytes
        """
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=self.page_size,
            rightMargin=self.margin,
            leftMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin,
        )

        story = [
            Paragraph(title, self.styles['CustomTitle']),
            Spacer(1, 0.5 * inch),
            Paragraph(content, self.styles['BodyText']),
        ]

        doc.build(story)

        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes
