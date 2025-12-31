from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Cognive Control Plane API", alias="APP_NAME")
    environment: str = Field(default="development", alias="APP_ENV")

    # Database
    database_url: str = Field(alias="DATABASE_URL")
    database_url_async: str | None = Field(default=None, alias="DATABASE_URL_ASYNC")
    # Optional read replica URLs for read-heavy queries.
    # Provide as comma-separated URLs, e.g.:
    # DATABASE_READ_URLS=postgresql+psycopg2://...@postgres_replica_1:5432/db,postgresql+psycopg2://...@postgres_replica_2:5432/db
    database_read_urls: str | None = Field(default=None, alias="DATABASE_READ_URLS")
    # Async equivalents (must use asyncpg)
    database_read_urls_async: str | None = Field(default=None, alias="DATABASE_READ_URLS_ASYNC")

    # Redis
    redis_url: str = Field(alias="REDIS_URL")
    redis_max_connections: int = Field(default=50, alias="REDIS_MAX_CONNECTIONS")
    redis_socket_timeout: float = Field(default=5.0, alias="REDIS_SOCKET_TIMEOUT")
    redis_socket_connect_timeout: float = Field(default=5.0, alias="REDIS_SOCKET_CONNECT_TIMEOUT")

    # Cache TTL defaults (in seconds)
    cache_ttl_llm_pricing: int = Field(default=3600, alias="CACHE_TTL_LLM_PRICING")  # 1 hour
    cache_ttl_agent_config: int = Field(default=300, alias="CACHE_TTL_AGENT_CONFIG")  # 5 minutes
    cache_ttl_budget: int = Field(default=60, alias="CACHE_TTL_BUDGET")  # 1 minute (real-time)

    # RabbitMQ
    rabbitmq_url: str = Field(alias="RABBITMQ_URL")

    # Object Storage (S3-compatible: MinIO, AWS S3, etc.)
    # For MinIO: http://minio:9000
    # For AWS S3: https://s3.amazonaws.com or https://s3.<region>.amazonaws.com
    storage_endpoint: str = Field(alias="STORAGE_ENDPOINT")
    storage_access_key: str = Field(alias="STORAGE_ACCESS_KEY")
    storage_secret_key: str = Field(alias="STORAGE_SECRET_KEY")
    storage_region: str = Field(default="us-east-1", alias="STORAGE_REGION")
    storage_secure: bool = Field(default=False, alias="STORAGE_SECURE")  # True for HTTPS/AWS S3
    # Optional server-side encryption settings for uploads.
    # Examples:
    # - AWS SSE-S3: STORAGE_SSE=AES256
    # - AWS SSE-KMS: STORAGE_SSE=aws:kms and set STORAGE_SSE_KMS_KEY_ID
    storage_sse: str | None = Field(default=None, alias="STORAGE_SSE")
    storage_sse_kms_key_id: str | None = Field(default=None, alias="STORAGE_SSE_KMS_KEY_ID")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()

