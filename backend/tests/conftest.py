"""
Pytest configuration and fixtures
"""

import pytest
import os
import sys

# Add app to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def sample_textract_response():
    """Sample Textract API response for testing"""
    return {
        "Blocks": [
            {
                "BlockType": "LINE",
                "Text": "INVOICE",
                "Confidence": 99.5,
                "Geometry": {
                    "BoundingBox": {
                        "Top": 0.1,
                        "Left": 0.1,
                        "Width": 0.2,
                        "Height": 0.05
                    }
                }
            },
            {
                "BlockType": "LINE",
                "Text": "Invoice #: 12345",
                "Confidence": 98.2,
                "Geometry": {
                    "BoundingBox": {
                        "Top": 0.2,
                        "Left": 0.1,
                        "Width": 0.3,
                        "Height": 0.05
                    }
                }
            },
            {
                "BlockType": "LINE",
                "Text": "Date: 2024-01-15",
                "Confidence": 97.8,
                "Geometry": {
                    "BoundingBox": {
                        "Top": 0.25,
                        "Left": 0.1,
                        "Width": 0.3,
                        "Height": 0.05
                    }
                }
            },
            {
                "BlockType": "LINE",
                "Text": "Total: $1,234.56",
                "Confidence": 99.1,
                "Geometry": {
                    "BoundingBox": {
                        "Top": 0.8,
                        "Left": 0.6,
                        "Width": 0.3,
                        "Height": 0.05
                    }
                }
            }
        ]
    }


@pytest.fixture
def sample_llm_analysis_response():
    """Sample LLM analysis response"""
    return {
        "category": "invoice",
        "confidence": 0.95,
        "summary": "Invoice from ABC Company for services rendered, total amount $1,234.56",
        "key_entities": {
            "date": "2024-01-15",
            "total_amount": "$1,234.56",
            "vendor": "ABC Company",
            "invoice_number": "12345",
            "due_date": "2024-02-15"
        },
        "suggested_tags": ["invoice", "payment", "services"]
    }
