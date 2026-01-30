"""
Core configuration and settings for the application.
Uses Pydantic Settings for environment variable management.
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "PanScience Q&A"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="DEBUG")
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    
    # MongoDB
    MONGODB_URL: str = Field(..., env="MONGODB_URL")
    DATABASE_NAME: str = Field(default="panscience", env="DATABASE_NAME")
    
    # Redis (optional)
    REDIS_URL: Optional[str] = Field(default=None, env="REDIS_URL")
    REDIS_ENABLED: bool = Field(default=False, env="REDIS_ENABLED")
    
    # OpenAI (Optional - can use free alternatives)
    OPENAI_API_KEY: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    OPENAI_MODEL: str = Field(default="gpt-4-turbo-preview", env="OPENAI_MODEL")
    OPENAI_EMBEDDING_MODEL: str = Field(default="text-embedding-3-small", env="OPENAI_EMBEDDING_MODEL")
    
    # Deepgram API (Optional - for transcription)
    DEEPGRAM_API_KEY: Optional[str] = Field(default=None, env="DEEPGRAM_API_KEY")
    
    # Transcription Settings
    TRANSCRIPTION_PROVIDER: str = Field(default="local", env="TRANSCRIPTION_PROVIDER")  # local, openai, deepgram
    WHISPER_MODEL_SIZE: str = Field(default="base", env="WHISPER_MODEL_SIZE")  # tiny, base, small, medium, large
    
    # Free AI Options (no API keys needed!)
    USE_FREE_EMBEDDINGS: bool = Field(default=True, env="USE_FREE_EMBEDDINGS")
    USE_FREE_TRANSCRIPTION: bool = Field(default=True, env="USE_FREE_TRANSCRIPTION")
    USE_FREE_LLM: bool = Field(default=True, env="USE_FREE_LLM")
    FREE_LLM_MODEL: str = Field(default="mistral", env="FREE_LLM_MODEL")  # Ollama model
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    
    # JWT Authentication
    JWT_SECRET_KEY: str = Field(..., env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 24, env="ACCESS_TOKEN_EXPIRE_MINUTES")  # 24 hours
    
    # File Upload
    UPLOAD_DIR: str = Field(default="./uploads", env="UPLOAD_DIR")
    MAX_FILE_SIZE: int = Field(default=500 * 1024 * 1024, env="MAX_FILE_SIZE")  # 500MB
    ALLOWED_EXTENSIONS: list[str] = ["pdf", "mp3", "wav", "mp4", "avi", "mov", "m4a"]
    
    # Vector Store
    VECTOR_STORE_TYPE: str = Field(default="faiss", env="VECTOR_STORE_TYPE")  # faiss or pinecone
    FAISS_INDEX_PATH: str = Field(default="./faiss_index", env="FAISS_INDEX_PATH")
    PINECONE_API_KEY: Optional[str] = Field(default=None, env="PINECONE_API_KEY")
    PINECONE_ENVIRONMENT: Optional[str] = Field(default=None, env="PINECONE_ENVIRONMENT")
    PINECONE_INDEX_NAME: Optional[str] = Field(default=None, env="PINECONE_INDEX_NAME")
    
    # Chunking
    CHUNK_SIZE: int = Field(default=1000, env="CHUNK_SIZE")
    CHUNK_OVERLAP: int = Field(default=200, env="CHUNK_OVERLAP")
    
    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=False, env="RATE_LIMIT_ENABLED")
    RATE_LIMIT_CALLS: int = Field(default=100, env="RATE_LIMIT_CALLS")
    RATE_LIMIT_PERIOD: int = Field(default=60, env="RATE_LIMIT_PERIOD")  # seconds
    
    # Redis Configuration
    REDIS_HOST: str = Field(default="localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    REDIS_DB: int = Field(default=0, env="REDIS_DB")
    REDIS_PASSWORD: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    ENABLE_REDIS: bool = Field(default=False, env="ENABLE_REDIS")
    
    # Update JWT to use existing field names
    SECRET_KEY: str = Field(default="change-this-secret-key-in-production", env="JWT_SECRET_KEY")
    ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Singleton instance
settings = Settings()
