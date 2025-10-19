"""
Test analysis endpoints
"""

import pytest
import json


def test_analysis_result_schema(sample_llm_analysis_response):
    """Test that sample analysis response has correct schema"""

    result = sample_llm_analysis_response

    # Required fields
    assert "category" in result
    assert "confidence" in result
    assert "summary" in result
    assert "key_entities" in result
    assert "suggested_tags" in result

    # Types
    assert isinstance(result["category"], str)
    assert isinstance(result["confidence"], (int, float))
    assert isinstance(result["summary"], str)
    assert isinstance(result["key_entities"], dict)
    assert isinstance(result["suggested_tags"], list)

    # Values
    assert 0.0 <= result["confidence"] <= 1.0


def test_analysis_category_validation(sample_llm_analysis_response):
    """Test that category is valid"""

    valid_categories = [
        "invoice",
        "receipt",
        "letter",
        "contract",
        "form",
        "other"
    ]

    category = sample_llm_analysis_response["category"]
    assert category in valid_categories


def test_key_entities_structure(sample_llm_analysis_response):
    """Test key entities structure"""

    entities = sample_llm_analysis_response["key_entities"]

    # Check common fields
    expected_fields = ["date", "total_amount", "vendor", "invoice_number"]

    for field in expected_fields:
        assert field in entities


def test_suggested_tags_format(sample_llm_analysis_response):
    """Test suggested tags format"""

    tags = sample_llm_analysis_response["suggested_tags"]

    # Should be a list
    assert isinstance(tags, list)

    # Should have at least one tag
    assert len(tags) > 0

    # All tags should be strings
    for tag in tags:
        assert isinstance(tag, str)
        assert len(tag) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
