"""
PostMate Backend - Configuration Module

Purpose: Centralized configuration management using Pydantic Settings.
Loads from environment variables with validation and type checking.

Testing:
    from app.config import settings
    print(settings.OCR_PROVIDER)  # tesseract or textract

AWS Deployment Notes:
    - Set environment variables in ECS task definition or Lambda configuration
    - Never hardcode AWS credentials; use IAM roles
    - Use AWS Systems Manager Parameter Store or Secrets Manager for sensitive values
"""

from typing import List, Literal, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json


class Settings(BaseSettings):
    """Application configuration loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # =============================================================================
    # CORE APPLICATION
    # =============================================================================
    ENVIRONMENT: Literal["local", "development", "staging", "production"] = "local"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = '["http://localhost:3000","http://localhost:8080"]'

    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    # =============================================================================
    # AWS CONFIGURATION
    # =============================================================================
    AWS_REGION: str = "us-east-1"
    AWS_ACCOUNT_ID: Optional[str] = None

    # AWS credentials (only for local testing; use IAM roles in production)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None

    # =============================================================================
    # STORAGE CONFIGURATION
    # =============================================================================
    USE_LOCAL_STORAGE: bool = True
    LOCAL_STORAGE_PATH: str = "./local_data"

    S3_BUCKET_NAME: str = "postmate-storage-dev"
    S3_PREFIX_IMAGES: str = "images/"
    S3_PREFIX_PDFS: str = "pdfs/"
    S3_PREFIX_TEXTRACT: str = "textract/"
    S3_PRESIGNED_URL_EXPIRY: int = 3600  # seconds

    # =============================================================================
    # OCR CONFIGURATION
    # =============================================================================
    OCR_PROVIDER: Literal["tesseract", "textract"] = "tesseract"

    # Tesseract
    TESSERACT_PATH: str = "/usr/bin/tesseract"
    TESSERACT_LANG: str = "eng"
    TESSERACT_CONFIG: str = "--oem 3 --psm 6"

    # Textract
    TEXTRACT_ASYNC: bool = True
    TEXTRACT_SNS_TOPIC_ARN: Optional[str] = None
    TEXTRACT_ROLE_ARN: Optional[str] = None

    # =============================================================================
    # LLM CONFIGURATION
    # =============================================================================
    LLM_PROVIDER: Literal["openai", "bedrock"] = "openai"

    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_MAX_TOKENS: int = 4000
    OPENAI_TEMPERATURE: float = 0.2

    # Bedrock
    BEDROCK_MODEL_ID: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    BEDROCK_REGION: str = "us-east-1"
    BEDROCK_MAX_TOKENS: int = 4000
    BEDROCK_TEMPERATURE: float = 0.2

    # LLM Processing
    MAX_CHUNK_TOKENS: int = 4000
    SUMMARY_MAX_TOKENS: int = 1000

    # =============================================================================
    # DATABASE CONFIGURATION
    # =============================================================================
    USE_DYNAMODB_LOCAL: bool = True
    DYNAMODB_LOCAL_ENDPOINT: str = "http://localhost:8000"

    DYNAMODB_TABLE_DOCUMENTS: str = "postmate-documents-local"
    DYNAMODB_TABLE_ANALYSES: str = "postmate-analyses-local"
    DYNAMODB_TABLE_CHATS: str = "postmate-chats-local"
    DYNAMODB_TABLE_REMINDERS: str = "postmate-reminders-local"

    DYNAMODB_READ_CAPACITY: int = 5
    DYNAMODB_WRITE_CAPACITY: int = 5
    DYNAMODB_BILLING_MODE: Literal["PAY_PER_REQUEST", "PROVISIONED"] = "PAY_PER_REQUEST"

    # =============================================================================
    # BACKGROUND WORKERS
    # =============================================================================
    WORKER_MODE: Literal["fastapi", "lambda"] = "fastapi"

    SQS_QUEUE_URL: Optional[str] = None
    SQS_QUEUE_NAME: str = "postmate-ocr-queue"

    LAMBDA_OCR_WORKER_ARN: Optional[str] = None
    LAMBDA_REMINDER_WORKER_ARN: Optional[str] = None

    # =============================================================================
    # REMINDERS & SCHEDULING
    # =============================================================================
    SCHEDULER_PROVIDER: Literal["apscheduler", "eventbridge"] = "apscheduler"

    EVENTBRIDGE_RULE_NAME: str = "postmate-reminder-check"
    EVENTBRIDGE_SCHEDULE_RATE: str = "rate(5 minutes)"

    # Email/Notification
    EMAIL_PROVIDER: Literal["ses", "sendgrid", "smtp"] = "ses"
    EMAIL_FROM_ADDRESS: str = "noreply@postmate.example.com"
    SENDGRID_API_KEY: Optional[str] = None
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None

    # =============================================================================
    # PDF GENERATION
    # =============================================================================
    PDF_FONT_NAME: str = "Helvetica"
    PDF_FONT_SIZE: int = 10
    PDF_PAGE_SIZE: Literal["LETTER", "A4"] = "LETTER"
    PDF_MARGIN: int = 72  # points

    # =============================================================================
    # SEARCH CONFIGURATION
    # =============================================================================
    SEARCH_MAX_RESULTS: int = 100
    SEARCH_ENABLE_FUZZY: bool = True

    # =============================================================================
    # SECURITY & AUTHENTICATION
    # =============================================================================
    SECRET_KEY: Optional[str] = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # =============================================================================
    # LOGGING & MONITORING
    # =============================================================================
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "json"
    LOG_FILE_PATH: str = "./logs/app.log"

    CLOUDWATCH_LOG_GROUP: str = "/aws/ecs/postmate"
    CLOUDWATCH_LOG_STREAM: str = "postmate-app"

    # =============================================================================
    # PERFORMANCE & LIMITS
    # =============================================================================
    MAX_UPLOAD_SIZE_MB: int = 10
    MAX_FILES_PER_UPLOAD: int = 10
    MAX_IMAGE_DIMENSION: int = 4096
    SUPPORTED_IMAGE_FORMATS: str = "jpg,jpeg,png,tiff,bmp"

    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60  # seconds

    # =============================================================================
    # FEATURE FLAGS
    # =============================================================================
    ENABLE_CHAT: bool = True
    ENABLE_REMINDERS: bool = True
    ENABLE_PDF_EXPORT: bool = True
    ENABLE_SEARCH: bool = True

    # =============================================================================
    # COMPUTED PROPERTIES
    # =============================================================================

    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.ENVIRONMENT == "production"

    @property
    def is_local(self) -> bool:
        """Check if running in local environment"""
        return self.ENVIRONMENT == "local"

    @property
    def max_upload_size_bytes(self) -> int:
        """Get max upload size in bytes"""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def supported_formats_list(self) -> List[str]:
        """Get list of supported image formats"""
        return [fmt.strip() for fmt in self.SUPPORTED_IMAGE_FORMATS.split(",")]

    @property
    def dynamodb_endpoint(self) -> Optional[str]:
        """Get DynamoDB endpoint (None for AWS service, URL for local)"""
        if self.USE_DYNAMODB_LOCAL:
            return self.DYNAMODB_LOCAL_ENDPOINT
        return None

    def get_table_name(self, table_type: str) -> str:
        """Get DynamoDB table name by type"""
        table_map = {
            "documents": self.DYNAMODB_TABLE_DOCUMENTS,
            "analyses": self.DYNAMODB_TABLE_ANALYSES,
            "chats": self.DYNAMODB_TABLE_CHATS,
            "reminders": self.DYNAMODB_TABLE_REMINDERS,
        }
        return table_map.get(table_type, "")


# Global settings instance
settings = Settings()


# Validation on startup
def validate_settings():
    """Validate required settings based on providers"""
    errors = []

    # Validate LLM provider
    if settings.LLM_PROVIDER == "openai" and not settings.OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY is required when LLM_PROVIDER=openai")

    # Validate OCR provider
    if settings.OCR_PROVIDER == "tesseract":
        import shutil
        if not shutil.which(settings.TESSERACT_PATH):
            errors.append(f"Tesseract not found at {settings.TESSERACT_PATH}")

    # Validate storage
    if not settings.USE_LOCAL_STORAGE and not settings.S3_BUCKET_NAME:
        errors.append("S3_BUCKET_NAME is required when USE_LOCAL_STORAGE=false")

    # Validate AWS region for AWS services
    if settings.OCR_PROVIDER == "textract" and not settings.AWS_REGION:
        errors.append("AWS_REGION is required when using Textract")

    if settings.LLM_PROVIDER == "bedrock" and not settings.BEDROCK_REGION:
        errors.append("BEDROCK_REGION is required when using Bedrock")

    if errors:
        error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(error_msg)


# Print config summary (for debugging)
def print_config_summary():
    """Print configuration summary (safe - no secrets)"""
    print("\n" + "="*60)
    print("PostMate Configuration Summary")
    print("="*60)
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Debug Mode: {settings.DEBUG}")
    print(f"Storage: {'Local FS' if settings.USE_LOCAL_STORAGE else f'S3 ({settings.S3_BUCKET_NAME})'}")
    print(f"OCR Provider: {settings.OCR_PROVIDER}")
    print(f"LLM Provider: {settings.LLM_PROVIDER}")
    print(f"Database: {'DynamoDB Local' if settings.USE_DYNAMODB_LOCAL else 'DynamoDB AWS'}")
    print(f"Worker Mode: {settings.WORKER_MODE}")
    print(f"Scheduler: {settings.SCHEDULER_PROVIDER}")
    print("="*60 + "\n")
