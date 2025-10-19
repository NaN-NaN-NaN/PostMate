"""
Test LLM prompt formatting and JSON validation
"""

import pytest
import json
from app.services.llm import LLMService


def test_extract_json_from_clean_response():
    """Test extracting JSON from clean LLM response"""

    service = LLMService()

    response = '{"category": "invoice", "confidence": 0.95, "summary": "Test"}'

    result = service._extract_json_from_response(response)

    assert isinstance(result, dict)
    assert result["category"] == "invoice"
    assert result["confidence"] == 0.95


def test_extract_json_from_markdown_response():
    """Test extracting JSON from response with markdown code blocks"""

    service = LLMService()

    response = """```json
{
  "category": "receipt",
  "confidence": 0.88,
  "summary": "Grocery receipt"
}
```"""

    result = service._extract_json_from_response(response)

    assert isinstance(result, dict)
    assert result["category"] == "receipt"
    assert result["confidence"] == 0.88


def test_extract_json_from_plain_markdown():
    """Test extracting JSON from plain markdown block"""

    service = LLMService()

    response = """```
{
  "category": "letter",
  "confidence": 0.92
}
```"""

    result = service._extract_json_from_response(response)

    assert isinstance(result, dict)
    assert result["category"] == "letter"


def test_chunk_and_token_counting():
    """Test text chunking by token count"""

    service = LLMService()

    # Create text with known length
    text = "This is a test sentence. " * 100  # ~500 tokens

    # Count tokens
    token_count = service._count_tokens(text)
    assert token_count > 0, "Token count should be positive"

    # Split into chunks
    chunks = service._split_into_chunks(text, max_tokens=200)

    # Verify chunks
    assert len(chunks) > 1, "Should split into multiple chunks"

    # Verify each chunk is within limit
    for chunk in chunks:
        chunk_tokens = service._count_tokens(chunk)
        assert chunk_tokens <= 200, f"Chunk has {chunk_tokens} tokens, exceeds 200"


def test_chunk_respects_paragraphs():
    """Test that chunking preserves paragraph boundaries when possible"""

    service = LLMService()

    # Create text with clear paragraphs
    para1 = "First paragraph. " * 10
    para2 = "Second paragraph. " * 10
    para3 = "Third paragraph. " * 10

    text = f"{para1}\n\n{para2}\n\n{para3}"

    chunks = service._split_into_chunks(text, max_tokens=1000)

    # With large enough token limit, should keep paragraphs together
    # At minimum, paragraphs shouldn't be split mid-sentence
    for chunk in chunks:
        # Check that chunk doesn't start/end mid-sentence (naive check)
        if chunk.strip():
            assert not chunk.strip().startswith('. '), \
                "Chunk shouldn't start mid-sentence"


def test_default_prompt_fallback():
    """Test that default prompts are used when template files don't exist"""

    service = LLMService()

    # Test getting default analysis prompt
    prompt = service._get_default_prompt("analysis_prompt.txt")

    assert "JSON" in prompt, "Analysis prompt should mention JSON"
    assert "category" in prompt, "Analysis prompt should mention category"
    assert "{OCR_TEXT}" in prompt, "Analysis prompt should have OCR_TEXT placeholder"

    # Test getting default chat prompt
    chat_prompt = service._get_default_prompt("chat_prompt.txt")

    assert "{CONTEXT}" in chat_prompt, "Chat prompt should have CONTEXT placeholder"

    # Test getting default summary prompt
    summary_prompt = service._get_default_prompt("summary_prompt.txt")

    assert "{TEXT}" in summary_prompt, "Summary prompt should have TEXT placeholder"


def test_analysis_result_schema_validation(sample_llm_analysis_response):
    """Test that analysis results match expected schema"""

    result = sample_llm_analysis_response

    # Check required fields
    assert "category" in result, "Missing category field"
    assert "confidence" in result, "Missing confidence field"
    assert "summary" in result, "Missing summary field"
    assert "key_entities" in result, "Missing key_entities field"
    assert "suggested_tags" in result, "Missing suggested_tags field"

    # Check types
    assert isinstance(result["category"], str)
    assert isinstance(result["confidence"], (int, float))
    assert isinstance(result["summary"], str)
    assert isinstance(result["key_entities"], dict)
    assert isinstance(result["suggested_tags"], list)

    # Check value ranges
    assert 0.0 <= result["confidence"] <= 1.0, \
        "Confidence should be between 0 and 1"

    # Check category is valid
    valid_categories = ["invoice", "receipt", "letter", "contract", "form", "other"]
    assert result["category"] in valid_categories, \
        f"Category '{result['category']}' not in valid list"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
