"""
Application configuration using Pydantic Settings.
"""

import os
import secrets
from pathlib import Path
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env path: prefer backend/.env when running as backend (so creds in backend/.env are always loaded)
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _BACKEND_ROOT / ".env"


def generate_secure_secret() -> str:
    """Generate a cryptographically secure random secret."""
    return secrets.token_urlsafe(32)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )
    
    # Application
    APP_NAME: str = "IntelliDocs"
    DEBUG: bool = False
    
    # CORS (include alternate frontend ports)
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8000",
    ]
    
    # Database (Neon PostgreSQL)
    DATABASE_URL: str = ""
    # Database SSL behavior
    DB_SSL_INSECURE: bool = False
    
    # Redis: Upstash REST for hosted, REDIS_URL for local Compose (redis://)
    UPSTASH_REDIS_REST_URL: str = ""
    UPSTASH_REDIS_REST_TOKEN: str = ""
    REDIS_URL: str = ""
    
    # AWS
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    
    # File storage: "local" keeps originals on disk for the source viewer.
    # "s3" uses S3_BUCKET_NAME. Default local so preview works without AWS.
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_DIR: str = "data/documents"

    # S3
    S3_BUCKET_NAME: str = "intellidocs-documents"
    
    # LLM Provider: "bedrock", "nvidia", "openai", or "anthropic"
    LLM_PROVIDER: str = "bedrock"  # Set to "nvidia" to use NVIDIA API
    
    # NVIDIA API (alternative to Bedrock)
    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.ai/v1"
    NVIDIA_MODEL_ID: str = "nvidia/llama-3.1-nemotron-70b-instruct"  # Default NVIDIA model
    
    # AWS Bedrock
    BEDROCK_MODEL_ID: str = "amazon.nova-pro-v1:0"
    BEDROCK_AUX_MODEL_ID: str = "amazon.nova-lite-v1:0"  # Cheaper model for HyDE, multi-query, routing (~6x cheaper)
    BEDROCK_EMBEDDING_MODEL_ID: str = "amazon.titan-embed-text-v2:0"
    EMBEDDING_MAX_CONCURRENCY: int = 8  # Concurrent embedding calls
    EMBEDDING_RPS: float = 6.0  # Requests/sec (Titan allows higher; 2 was too slow)
    EMBEDDING_JITTER_MS: int = 50  # Jitter to smooth bursts
    EMBEDDING_BATCH_SIZE: int = 16  # Batch size for embed_texts
    
    # RAG Configuration (token-based chunking)
    # Small chunks: ~300 tokens (~1200 chars) - for precise retrieval
    CHUNK_SIZE_SMALL: int = 300
    # Large chunks: ~700 tokens (~2800 chars) - for context-rich retrieval
    CHUNK_SIZE_LARGE: int = 700
    # Default chunk size (tokens, not words - 1 token ≈ 4 chars)
    CHUNK_SIZE: int = 300
    CHUNK_OVERLAP: int = 75  # Token overlap (higher = fewer split sentences at boundaries)
    TOP_K_RESULTS: int = 12  # More chunks = better accuracy; Nova Pro handles long context well
    SEMANTIC_WEIGHT: float = 0.7
    # Multi-granularity: retrieve from both chunk sizes
    ENABLE_MULTI_GRANULARITY: bool = True
    # Advanced retrieval (HyDE, reranker, multi-query)
    ENABLE_HYDE: bool = True  # Hypothetical Document Embeddings
    ENABLE_RERANKER: bool = True  # Cross-encoder re-ranking
    ENABLE_MULTI_QUERY: bool = True  # Query expansion for ambiguous queries
    RERANK_RETRIEVE_MULTIPLIER: int = 3  # Retrieve 3x, rerank to top_k
    ENABLE_LLM_QUERY_ROUTING: bool = False  # Disabled: heuristic routing + HYBRID fallback is fast enough

    # Ingestion pruning (skip low-value chunks before embedding)
    ENABLE_CHUNK_PRUNING: bool = True
    PRUNE_MIN_TOKENS: int = 30
    PRUNE_MAX_TOKENS: int = 1200
    PRUNE_MIN_ALNUM_RATIO: float = 0.6
    PRUNE_MIN_UNIQUE_RATIO: float = 0.25
    ENABLE_CHUNK_DEDUP: bool = True
    ENABLE_SELECTIVE_EMBEDDING: bool = True
    SEMANTIC_CHUNKING: bool = False  # If True, split by paragraph/section boundaries instead of sentences
    EMBEDDING_TOP_PCT: float = 0.4  # Embed top 40% scored chunks
    # Multimodal ingest / retrieval / grounding
    ENABLE_STRUCTURED_CHUNKS: bool = True  # Extract tables and figures with page bboxes
    ENABLE_CLIP: bool = True  # CLIP visual retrieval fused via RRF
    ENABLE_NLI_FILTER: bool = True  # Drop generated claims not entailed by evidence
    ENABLE_IDENTIFIER_SEARCH: bool = True  # Exact SKU/FIG/site ILIKE; disable for metric runs
    VISUAL_RRF_WEIGHT: float = 0.7  # Visual list weight vs a text list in RRF
    CLIP_MODEL_ID: str = "clip-ViT-B-32"
    NLI_MODEL_ID: str = "cross-encoder/nli-deberta-v3-small"
    NLI_BACKEND: str = "auto"  # auto|minicheck|mnli|mock
    CLIP_DIM: int = 512
    MIN_FIGURE_PX: int = 40
    EVAL_REAL_ENCODERS: bool = False
    EVAL_DENSE_MODEL: str = "BAAI/bge-small-en-v1.5"
    EVAL_VISION_MODEL: str = "clip-ViT-B-32"
    EMBEDDING_TOKEN_BUDGET_PCT: float = 0.5  # Embed up to 50% of doc tokens
    EMBEDDING_TOKEN_BUDGET_MIN: int = 12000
    EMBEDDING_TOKEN_BUDGET_MAX: int = 30000
    
    # Caching
    CACHE_TTL_SECONDS: int = 86400  # 24 hours
    SEMANTIC_CACHE_THRESHOLD: float = 0.95  # Tighter threshold to avoid returning cached answers for different questions

    # Performance tuning
    DB_POOL_SIZE: int = 8
    DB_MAX_OVERFLOW: int = 16
    DB_POOL_RECYCLE_SECONDS: int = 300
    REDIS_POOL_SIZE: int = 10

    # Mock mode: no AWS calls, no charges. Use for cost-free benchmarking.
    MOCK_LLM_AND_EMBEDDINGS: bool = False

    # Auth (JWT_SECRET_KEY must be set in production)
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REQUIRE_AUTH_FOR_CHAT: bool = False  # Forced on when ENVIRONMENT=production
    
    # Environment
    ENVIRONMENT: str = "development"

    # Observability / OpenTelemetry
    OTEL_EXPORTER: str = ""           # Set "otlp" to enable OTLP export
    OTEL_EXPORTER_ENDPOINT: str = ""  # e.g. https://otel.example.com:4317

    @field_validator("JWT_SECRET_KEY", mode="before")
    @classmethod
    def validate_jwt_secret(cls, v):
        # If empty or default, generate/use secure random
        if not v or v == "intellidocs-dev-only-change-in-production":
            env_secret = os.getenv("JWT_SECRET_KEY", "")
            if env_secret and env_secret != "intellidocs-dev-only-change-in-production":
                return env_secret
            # Generate a secure random key for development
            generated = generate_secure_secret()
            if os.getenv("ENVIRONMENT") == "production":
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a secure random value in production. "
                    "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )
            return generated
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return v


settings = Settings()


def auth_required() -> bool:
    """Chat, upload, and AI helpers require a user in production."""
    if settings.REQUIRE_AUTH_FOR_CHAT:
        return True
    return settings.ENVIRONMENT.lower() == "production"
