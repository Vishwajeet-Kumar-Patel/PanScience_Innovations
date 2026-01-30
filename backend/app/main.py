"""
Main FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import os

from app.core.config import settings
from app.core.database import db_manager
from app.core.cache import cache
from app.core.rate_limit import RateLimitMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("Starting application...")
    await db_manager.connect()
    logger.info("Database connected")
    
    if settings.ENABLE_REDIS:
        logger.info("Redis cache enabled")
    else:
        logger.info("Using in-memory cache (Redis disabled)")
    
    logger.info("Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    await db_manager.disconnect()
    await cache.close()
    logger.info("Application shut down successfully")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-Powered Document & Multimedia Q&A Application with Authentication",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add rate limiting middleware (before CORS)
if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(RateLimitMiddleware)
    logger.info(f"Rate limiting enabled: {settings.RATE_LIMIT_CALLS} requests per {settings.RATE_LIMIT_PERIOD}s")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to PanScience Q&A API",
        "docs": "/docs",
        "health": "/health"
    }


# Mount static files for media playback (must be before API routers)
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
if os.path.exists(UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
    logger.info(f"Mounted uploads directory: {UPLOAD_DIR}")
else:
    logger.warning(f"Uploads directory not found: {UPLOAD_DIR}")


# Import and include API routers
from app.api import documents, chat, upload, media, auth

# Register authentication router
app.include_router(auth.router, prefix=settings.API_V1_PREFIX, tags=["Authentication"])

# Register other API routers
app.include_router(upload.router, prefix=settings.API_V1_PREFIX, tags=["Upload"])
app.include_router(documents.router, prefix=settings.API_V1_PREFIX, tags=["Documents"])
app.include_router(chat.router, prefix=settings.API_V1_PREFIX, tags=["Chat"])
app.include_router(media.router, prefix=settings.API_V1_PREFIX, tags=["Media"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
