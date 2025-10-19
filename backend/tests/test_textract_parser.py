"""
Test Textract JSON parsing and reading order algorithm
"""

import pytest
from app.services.textract import TextractService


def test_textract_parser_reading_order(sample_textract_response):
    """Test that Textract parser maintains reading order (top-to-bottom, left-to-right)"""

    service = TextractService()

    # Parse the response
    text, confidence = service._parse_textract_response(sample_textract_response)

    # Check extracted text
    expected_lines = [
        "INVOICE",
        "Invoice #: 12345",
        "Date: 2024-01-15",
        "Total: $1,234.56"
    ]

    actual_lines = text.strip().split('\n')

    assert len(actual_lines) == len(expected_lines), \
        f"Expected {len(expected_lines)} lines, got {len(actual_lines)}"

    for expected, actual in zip(expected_lines, actual_lines):
        assert expected == actual, \
            f"Expected line '{expected}', got '{actual}'"

    # Check confidence (average of all confidences)
    expected_conf = (99.5 + 98.2 + 97.8 + 99.1) / 4
    assert abs(confidence - expected_conf) < 0.1, \
        f"Expected confidence ~{expected_conf}, got {confidence}"


def test_textract_parser_empty_response():
    """Test parsing empty Textract response"""

    service = TextractService()

    empty_response = {"Blocks": []}

    text, confidence = service._parse_textract_response(empty_response)

    assert text == "", "Expected empty text for empty response"
    assert confidence == 0.0, "Expected 0 confidence for empty response"


def test_textract_parser_multi_column():
    """Test parsing multi-column layout (reading order matters)"""

    service = TextractService()

    # Simulate two-column layout
    response = {
        "Blocks": [
            {
                "BlockType": "LINE",
                "Text": "Left Column Line 1",
                "Confidence": 99.0,
                "Geometry": {"BoundingBox": {"Top": 0.1, "Left": 0.1, "Width": 0.3, "Height": 0.05}}
            },
            {
                "BlockType": "LINE",
                "Text": "Right Column Line 1",
                "Confidence": 99.0,
                "Geometry": {"BoundingBox": {"Top": 0.1, "Left": 0.6, "Width": 0.3, "Height": 0.05}}
            },
            {
                "BlockType": "LINE",
                "Text": "Left Column Line 2",
                "Confidence": 99.0,
                "Geometry": {"BoundingBox": {"Top": 0.2, "Left": 0.1, "Width": 0.3, "Height": 0.05}}
            },
            {
                "BlockType": "LINE",
                "Text": "Right Column Line 2",
                "Confidence": 99.0,
                "Geometry": {"BoundingBox": {"Top": 0.2, "Left": 0.6, "Width": 0.3, "Height": 0.05}}
            }
        ]
    }

    text, confidence = service._parse_textract_response(response)

    lines = text.strip().split('\n')

    # Should read left-to-right for each row
    expected_order = [
        "Left Column Line 1",
        "Right Column Line 1",
        "Left Column Line 2",
        "Right Column Line 2"
    ]

    assert lines == expected_order, \
        f"Expected reading order {expected_order}, got {lines}"


def test_textract_parser_ignores_non_line_blocks():
    """Test that parser only processes LINE blocks"""

    service = TextractService()

    response = {
        "Blocks": [
            {
                "BlockType": "PAGE",
                "Text": "Should be ignored",
                "Confidence": 99.0,
                "Geometry": {"BoundingBox": {"Top": 0.0, "Left": 0.0, "Width": 1.0, "Height": 1.0}}
            },
            {
                "BlockType": "LINE",
                "Text": "Should be extracted",
                "Confidence": 98.0,
                "Geometry": {"BoundingBox": {"Top": 0.1, "Left": 0.1, "Width": 0.3, "Height": 0.05}}
            },
            {
                "BlockType": "WORD",
                "Text": "Also ignored",
                "Confidence": 99.0,
                "Geometry": {"BoundingBox": {"Top": 0.1, "Left": 0.1, "Width": 0.1, "Height": 0.05}}
            }
        ]
    }

    text, confidence = service._parse_textract_response(response)

    assert text.strip() == "Should be extracted", \
        "Parser should only extract LINE blocks"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
