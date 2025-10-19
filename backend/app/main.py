"""
PostMate Backend - FastAPI Application Entry Point

Purpose: Main application initialization with all API routes, middleware, and lifecycle events.

Testing:
    uvicorn app.main:app --reload --port 8080
    curl http://localhost:8080/health
    Open http://localhost:8080/docs for interactive API documentation

AWS Deployment Notes:
    - Runs on ECS Fargate or Lambda (using Mangum adapter for Lambda)
    - Health check endpoint used by ALB target group
    - CORS configured for production domains
    - Structured logging for CloudWatch
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging
import time
import sys
from typing import Dict, Any

from app.config import settings, validate_settings, print_config_summary
from app.api.v1 import upload, analyze, chat, reminders, search
from app.services.db import DatabaseService


# Configure logging
def setup_logging():
    """Configure structured logging"""
    log_level = getattr(logging, settings.LOG_LEVEL)

    if settings.LOG_FORMAT == "json":
        # JSON logging for production (CloudWatch)
        import json
        import datetime

        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "level": record.levelname,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                }
                if record.exc_info:
                    log_data["exception"] = self.formatException(record.exc_info)
                return json.dumps(log_data)

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
    else:
        # Text logging for local development
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=[handler],
        force=True
    )

    # Reduce noise from boto3/botocore
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger(__name__)


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager - runs on startup and shutdown
    """
    # Startup
    logger.info("Starting PostMate Backend")

    try:
        # Validate configuration
        validate_settings()
        logger.info("Configuration validated successfully")

        # Print config summary in debug mode
        if settings.DEBUG:
            print_config_summary()

        # Initialize database service and verify tables exist
        db_service = DatabaseService()
        await db_service.verify_tables()
        logger.info("Database tables verified")

        # Initialize scheduler if using apscheduler
        if settings.SCHEDULER_PROVIDER == "apscheduler":
            from app.workers.background_tasks import start_scheduler
            start_scheduler()
            logger.info("APScheduler started for reminders")

        logger.info(f"PostMate Backend ready - Environment: {settings.ENVIRONMENT}")

    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        raise

    yield

    # Shutdown
    logger.info("Shutting down PostMate Backend")

    # Cleanup resources
    if settings.SCHEDULER_PROVIDER == "apscheduler":
        from app.workers.background_tasks import shutdown_scheduler
        shutdown_scheduler()
        logger.info("APScheduler stopped")


# Create FastAPI application
app = FastAPI(
    title="PostMate API",
    description="Document processing service with OCR, AI analysis, chat, and reminders",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# =============================================================================
# MIDDLEWARE
# =============================================================================

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing"""
    start_time = time.time()

    # Log request
    logger.info(f"Request: {request.method} {request.url.path}")

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration = time.time() - start_time

    # Log response
    logger.info(
        f"Response: {request.method} {request.url.path} "
        f"Status: {response.status_code} Duration: {duration:.3f}s"
    )

    # Add custom headers
    response.headers["X-Process-Time"] = str(duration)

    return response


# =============================================================================
# EXCEPTION HANDLERS
# =============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed messages"""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": exc.errors(),
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    if settings.DEBUG:
        # Return detailed error in debug mode
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "detail": str(exc),
                "type": type(exc).__name__,
            }
        )
    else:
        # Return generic error in production
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred. Please try again later."
            }
        )


# =============================================================================
# ROUTES
# =============================================================================

# Health check endpoint (for ALB/ECS)
@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for load balancers and monitoring
    """
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0",
        "services": {
            "storage": "local" if settings.USE_LOCAL_STORAGE else "s3",
            "ocr": settings.OCR_PROVIDER,
            "llm": settings.LLM_PROVIDER,
            "database": "dynamodb-local" if settings.USE_DYNAMODB_LOCAL else "dynamodb",
        }
    }


# Root endpoint
@app.get("/", tags=["Root"])
async def root() -> Dict[str, str]:
    """
    Root endpoint with API information
    """
    return {
        "service": "PostMate API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


# Include API v1 routers
app.include_router(
    upload.router,
    prefix=settings.API_V1_PREFIX,
    tags=["Upload & Documents"]
)

app.include_router(
    analyze.router,
    prefix=settings.API_V1_PREFIX,
    tags=["Analysis"]
)

app.include_router(
    chat.router,
    prefix=settings.API_V1_PREFIX,
    tags=["Chat"]
)

app.include_router(
    reminders.router,
    prefix=settings.API_V1_PREFIX,
    tags=["Reminders"]
)

app.include_router(
    search.router,
    prefix=settings.API_V1_PREFIX,
    tags=["Search & Export"]
)


# =============================================================================
# LAMBDA HANDLER (for AWS Lambda deployment)
# =============================================================================

# Uncomment if deploying to AWS Lambda with Mangum
# from mangum import Mangum
# lambda_handler = Mangum(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
