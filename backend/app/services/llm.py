"""
PostMate Backend - LLM Service (Bedrock/OpenAI)

Purpose: AI analysis and chat using AWS Bedrock (production) or OpenAI (local dev).
Implements chunking + summarization for long documents and strict JSON output formatting.

Testing:
    # OpenAI mode
    service = LLMService()
    result = await service.analyze_document("Invoice text here...")

    # Bedrock mode (requires AWS credentials)
    service = LLMService()
    result = await service.chat("What is the total?", "Document context...")

AWS Deployment Notes:
    - Bedrock requires model access approval (AWS Console -> Bedrock -> Model Access)
    - Supports Claude 3 models (Sonnet, Haiku, Opus)
    - Use IAM role with bedrock:InvokeModel permission
    - Bedrock pricing: pay-per-token
"""

import logging
import json
from typing import Dict, List, Optional, Any
import boto3
from botocore.exceptions import ClientError
from openai import AsyncOpenAI
import tiktoken

from app.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """
    LLM service supporting both AWS Bedrock and OpenAI
    """

    def __init__(self):
        self.provider = settings.LLM_PROVIDER

        if self.provider == "bedrock":
            self.bedrock_client = boto3.client(
                'bedrock-runtime',
                region_name=settings.BEDROCK_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
            self.model_id = settings.BEDROCK_MODEL_ID
            logger.info(f"LLM: Using AWS Bedrock ({self.model_id})")

        else:
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            self.model_id = settings.OPENAI_MODEL
            logger.info(f"LLM: Using OpenAI ({self.model_id})")

        # Initialize tokenizer for chunking
        try:
            self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        except:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

    # =========================================================================
    # PUBLIC METHODS - DOCUMENT ANALYSIS
    # =========================================================================

    async def analyze_document(
        self,
        ocr_text: str,
        prompt_template: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze document and extract structured information

        Returns strict JSON format:
        {
            "category": "invoice|receipt|letter|other",
            "confidence": 0.95,
            "summary": "Brief summary...",
            "key_entities": {
                "date": "2024-01-15",
                "total_amount": "$123.45",
                "vendor": "Company Name",
                ...
            },
            "suggested_tags": ["tag1", "tag2"]
        }

        Args:
            ocr_text: Extracted text from OCR
            prompt_template: Optional custom prompt

        Returns:
            Structured analysis as dict
        """
        # Handle long documents with chunking
        if self._count_tokens(ocr_text) > settings.MAX_CHUNK_TOKENS:
            logger.info("Document too long, using chunking + summarization")
            ocr_text = await self.chunk_and_summarize(
                ocr_text,
                max_tokens=settings.MAX_CHUNK_TOKENS
            )

        # Load prompt template
        if not prompt_template:
            prompt_template = self._load_prompt_template("analysis_prompt.txt")

        # Format prompt
        prompt = prompt_template.replace("{OCR_TEXT}", ocr_text)

        # Get LLM response
        response_text = await self._call_llm(prompt)

        # Parse JSON response
        try:
            result = self._extract_json_from_response(response_text)
            logger.info(f"Analysis complete: category={result.get('category')}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            logger.error(f"Response was: {response_text}")

            # Return fallback response
            return {
                "category": "other",
                "confidence": 0.0,
                "summary": "Failed to parse analysis",
                "key_entities": {},
                "suggested_tags": [],
                "error": str(e)
            }

    # =========================================================================
    # PUBLIC METHODS - CHAT
    # =========================================================================

    async def chat(
        self,
        question: str,
        context: str,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Answer question about document using context

        Args:
            question: User's question
            context: Document OCR text (may be summarized if too long)
            chat_history: Previous messages [{"role": "user|assistant", "content": "..."}]

        Returns:
            Answer text
        """
        # Handle long context
        if self._count_tokens(context) > settings.MAX_CHUNK_TOKENS:
            logger.info("Context too long, summarizing")
            context = await self.chunk_and_summarize(
                context,
                max_tokens=settings.MAX_CHUNK_TOKENS // 2
            )

        # Load chat prompt template
        prompt_template = self._load_prompt_template("chat_prompt.txt")

        # Format system message
        system_message = prompt_template.replace("{CONTEXT}", context)

        # Build messages
        messages = [
            {"role": "system", "content": system_message}
        ]

        # Add chat history
        if chat_history:
            messages.extend(chat_history[-10:])  # Keep last 10 messages

        # Add current question
        messages.append({"role": "user", "content": question})

        # Get LLM response
        response = await self._call_llm_chat(messages)

        return response

    # =========================================================================
    # CHUNKING & SUMMARIZATION
    # =========================================================================

    async def chunk_and_summarize(
        self,
        text: str,
        max_tokens: int = 4000
    ) -> str:
        """
        Split long text into chunks and create combined summary

        Algorithm:
        1. Split text into chunks that fit within max_tokens
        2. Summarize each chunk individually
        3. Combine summaries into final text
        4. If combined summary still too long, recursively summarize

        Args:
            text: Long text to summarize
            max_tokens: Maximum tokens per chunk

        Returns:
            Summarized text that fits within token limit
        """
        logger.info(f"Chunking text: {self._count_tokens(text)} tokens")

        # Split into chunks
        chunks = self._split_into_chunks(text, max_tokens)
        logger.info(f"Split into {len(chunks)} chunks")

        # Summarize each chunk
        summaries = []
        prompt_template = self._load_prompt_template("summary_prompt.txt")

        for idx, chunk in enumerate(chunks, 1):
            logger.info(f"Summarizing chunk {idx}/{len(chunks)}")

            prompt = prompt_template.replace("{TEXT}", chunk)
            summary = await self._call_llm(prompt)
            summaries.append(summary)

        # Combine summaries
        combined = "\n\n".join(summaries)

        # If still too long, recursively summarize
        if self._count_tokens(combined) > max_tokens:
            logger.info("Combined summary still too long, recursing")
            return await self.chunk_and_summarize(combined, max_tokens)

        return combined

    def _split_into_chunks(self, text: str, max_tokens: int) -> List[str]:
        """
        Split text into chunks by token count

        Args:
            text: Text to split
            max_tokens: Max tokens per chunk

        Returns:
            List of text chunks
        """
        # Split by paragraphs first
        paragraphs = text.split('\n\n')

        chunks = []
        current_chunk = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = self._count_tokens(para)

            # If single paragraph exceeds limit, split by sentences
            if para_tokens > max_tokens:
                sentences = para.split('. ')
                for sentence in sentences:
                    sent_tokens = self._count_tokens(sentence)

                    if current_tokens + sent_tokens > max_tokens and current_chunk:
                        # Save current chunk
                        chunks.append('\n\n'.join(current_chunk))
                        current_chunk = []
                        current_tokens = 0

                    current_chunk.append(sentence)
                    current_tokens += sent_tokens

            else:
                # Add paragraph to current chunk
                if current_tokens + para_tokens > max_tokens and current_chunk:
                    # Save current chunk
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_tokens = 0

                current_chunk.append(para)
                current_tokens += para_tokens

        # Add final chunk
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))

        return chunks

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.tokenizer.encode(text))

    # =========================================================================
    # LLM API CALLS
    # =========================================================================

    async def _call_llm(self, prompt: str) -> str:
        """
        Call LLM with single prompt (for analysis/summarization)

        Args:
            prompt: Complete prompt text

        Returns:
            LLM response text
        """
        if self.provider == "bedrock":
            return await self._call_bedrock(prompt)
        else:
            return await self._call_openai(prompt)

    async def _call_llm_chat(self, messages: List[Dict[str, str]]) -> str:
        """
        Call LLM with chat messages (for Q&A)

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Assistant's response
        """
        if self.provider == "bedrock":
            # Convert messages to Bedrock format
            return await self._call_bedrock_chat(messages)
        else:
            return await self._call_openai_chat(messages)

    # =========================================================================
    # BEDROCK IMPLEMENTATION
    # =========================================================================

    async def _call_bedrock(self, prompt: str) -> str:
        """Call AWS Bedrock with prompt"""
        try:
            # Bedrock request format for Claude models
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": settings.BEDROCK_MAX_TOKENS,
                "temperature": settings.BEDROCK_TEMPERATURE,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }

            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            # Parse response
            response_body = json.loads(response['body'].read())
            text = response_body['content'][0]['text']

            return text

        except ClientError as e:
            logger.error(f"Bedrock API error: {e}")
            raise

    async def _call_bedrock_chat(self, messages: List[Dict[str, str]]) -> str:
        """Call Bedrock with chat messages"""
        try:
            # Extract system message if present
            system_message = ""
            chat_messages = []

            for msg in messages:
                if msg['role'] == 'system':
                    system_message = msg['content']
                else:
                    chat_messages.append(msg)

            # Bedrock request format
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": settings.BEDROCK_MAX_TOKENS,
                "temperature": settings.BEDROCK_TEMPERATURE,
                "messages": chat_messages
            }

            if system_message:
                request_body["system"] = system_message

            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            # Parse response
            response_body = json.loads(response['body'].read())
            text = response_body['content'][0]['text']

            return text

        except ClientError as e:
            logger.error(f"Bedrock chat error: {e}")
            raise

    # =========================================================================
    # OPENAI IMPLEMENTATION
    # =========================================================================

    async def _call_openai(self, prompt: str) -> str:
        """Call OpenAI with prompt"""
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=settings.OPENAI_MAX_TOKENS,
                temperature=settings.OPENAI_TEMPERATURE,
            )

            text = response.choices[0].message.content
            return text

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    async def _call_openai_chat(self, messages: List[Dict[str, str]]) -> str:
        """Call OpenAI with chat messages"""
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                max_tokens=settings.OPENAI_MAX_TOKENS,
                temperature=settings.OPENAI_TEMPERATURE,
            )

            text = response.choices[0].message.content
            return text

        except Exception as e:
            logger.error(f"OpenAI chat error: {e}")
            raise

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def _load_prompt_template(self, filename: str) -> str:
        """Load prompt template from file"""
        import os

        template_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "prompts",
            filename
        )

        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"Prompt template {filename} not found, using default")
            return self._get_default_prompt(filename)

    def _get_default_prompt(self, filename: str) -> str:
        """Get default prompt if template file not found"""
        if filename == "analysis_prompt.txt":
            return """Analyze the following document and return ONLY a JSON object (no markdown, no explanation):

{OCR_TEXT}

Return JSON in this exact format:
{
  "category": "invoice|receipt|letter|other",
  "confidence": 0.95,
  "summary": "Brief 1-2 sentence summary",
  "key_entities": {
    "date": "YYYY-MM-DD or null",
    "total_amount": "$XX.XX or null",
    "vendor": "Company name or null",
    "recipient": "Recipient name or null"
  },
  "suggested_tags": ["tag1", "tag2"]
}"""

        elif filename == "chat_prompt.txt":
            return """You are a helpful assistant answering questions about a document.

Document content:
{CONTEXT}

Answer questions accurately based on the document content. If information is not in the document, say so."""

        elif filename == "summary_prompt.txt":
            return """Summarize the following text concisely, preserving key information:

{TEXT}

Summary:"""

        return ""

    def _extract_json_from_response(self, response: str) -> Dict:
        """
        Extract JSON from LLM response (handles markdown code blocks)

        Args:
            response: LLM response text

        Returns:
            Parsed JSON dict
        """
        # Remove markdown code blocks if present
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()

        # Parse JSON
        return json.loads(response)
