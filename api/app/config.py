"""
Configuration management using Pydantic Settings.
Loads environment variables with validation and defaults.
"""

from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # =============================================================================
    # CORE APPLICATION SETTINGS
    # =============================================================================
    app_name: str = Field(default="HiLabs Roster Processing", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    app_env: str = Field(default="local", description="Environment (local, dev, prod)")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # =============================================================================
    # DATABASE CONFIGURATION
    # =============================================================================
    database_url: str = Field(
        default="postgresql+psycopg2://hilabs:hilabs@db:5432/hilabs",
        description="Database connection URL"
    )
    db_host: str = Field(default="db", description="Database host")
    db_port: int = Field(default=5432, description="Database port")
    db_name: str = Field(default="hilabs", description="Database name")
    db_user: str = Field(default="hilabs", description="Database user")
    db_password: str = Field(default="hilabs", description="Database password")
    
    # =============================================================================
    # OBJECT STORAGE (MinIO - S3 Compatible)
    # =============================================================================
    s3_endpoint: str = Field(default="http://minio:9000", description="S3 endpoint URL")
    s3_access_key: str = Field(default="minio", description="S3 access key")
    s3_secret_key: str = Field(default="minio123", description="S3 secret key")
    s3_bucket: str = Field(default="hilabs-artifacts", description="S3 bucket name")
    s3_region: str = Field(default="us-east-1", description="S3 region")
    s3_secure: bool = Field(default=False, description="Use HTTPS for S3")
    
    # =============================================================================
    # MESSAGE QUEUE (RabbitMQ)
    # =============================================================================
    celery_broker_url: str = Field(
        default="amqp://guest:guest@mq:5672//",
        description="Celery broker URL"
    )
    celery_result_backend: str = Field(default="rpc://", description="Celery result backend")
    celery_task_serializer: str = Field(default="json", description="Task serializer")
    celery_result_serializer: str = Field(default="json", description="Result serializer")
    celery_accept_content: List[str] = Field(default=["json"], description="Accepted content types")
    
    # =============================================================================
    # LOCAL VLM SERVICE
    # =============================================================================
    vlm_enabled: bool = Field(default=True, description="Enable VLM service")
    vlm_url: str = Field(default="http://vlm:8080", description="VLM service URL")
    vlm_timeout: int = Field(default=30, description="VLM request timeout in seconds")
    vlm_max_retries: int = Field(default=3, description="Maximum VLM retry attempts")
    vlm_model_name: str = Field(default="minicpm-v", description="VLM model name")
    
    # =============================================================================
    # EMAIL PROCESSING (Mailpit for testing)
    # =============================================================================
    smtp_host: str = Field(default="mailpit", description="SMTP host")
    smtp_port: int = Field(default=1025, description="SMTP port")
    smtp_user: Optional[str] = Field(default=None, description="SMTP username")
    smtp_password: Optional[str] = Field(default=None, description="SMTP password")
    smtp_use_tls: bool = Field(default=False, description="Use TLS for SMTP")
    
    # =============================================================================
    # SECURITY & COMPLIANCE
    # =============================================================================
    allow_egress: bool = Field(default=False, description="Allow outbound HTTP calls")
    allowed_domains: List[str] = Field(
        default=["localhost", "127.0.0.1", "db", "minio", "mq", "mailpit", "vlm"],
        description="Allowed external domains"
    )
    
    # PHI Protection
    mask_phi_in_logs: bool = Field(default=True, description="Mask PHI in logs")
    redact_npi_in_logs: bool = Field(default=True, description="Redact NPI in logs")
    redact_phone_in_logs: bool = Field(default=True, description="Redact phone in logs")
    
    # =============================================================================
    # OBSERVABILITY
    # =============================================================================
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")
    metrics_port: int = Field(default=9090, description="Metrics port")
    
    enable_tracing: bool = Field(default=True, description="Enable OpenTelemetry tracing")
    otel_service_name: str = Field(default="hilabs-roster-api", description="OTel service name")
    otel_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4317",
        description="OTel exporter endpoint"
    )
    
    # Structured logging
    log_format: str = Field(default="json", description="Log format (json, text)")
    log_file_path: str = Field(default="/app/logs/app.log", description="Log file path")
    
    # =============================================================================
    # API CONFIGURATION
    # =============================================================================
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_workers: int = Field(default=1, description="Number of API workers")
    api_reload: bool = Field(default=False, description="Auto-reload on changes")
    
    # CORS settings
    cors_origins: List[str] = Field(
        default=["http://localhost:8000", "http://localhost:8025", "http://localhost:9001", "http://localhost:3000"],
        description="CORS allowed origins"
    )
    cors_credentials: bool = Field(default=True, description="Allow CORS credentials")
    
    # Local LLM settings
    local_llm_enabled: bool = Field(default=False, env="LOCAL_LLM_ENABLED", description="Enable local LLM for classification and mapping")
    local_llm_model: str = Field(default="microsoft/DialoGPT-small", env="LOCAL_LLM_MODEL", description="Hugging Face model name for local LLM")
    local_llm_max_tokens: int = Field(default=512, env="LOCAL_LLM_MAX_TOKENS", description="Maximum tokens for LLM generation")
    
    # =============================================================================
    # TRAINED SLM CONFIGURATION
    # =============================================================================
    slm_enabled: bool = Field(default=True, env="SLM_ENABLED", description="Enable trained SLM for data extraction")
    slm_base_url: str = Field(default="http://localhost:5000/v1", env="SLM_BASE_URL", description="SLM service base URL")
    slm_model_name: str = Field(default="gpt-4.1", env="SLM_MODEL_NAME", description="SLM model name")
    slm_api_key: str = Field(default="dummy-key", env="SLM_API_KEY", description="SLM API key (not needed for local)")
    slm_timeout: int = Field(default=30, env="SLM_TIMEOUT", description="SLM request timeout in seconds")
    slm_max_tokens: int = Field(default=4000, env="SLM_MAX_TOKENS", description="Maximum tokens for SLM generation")
    slm_temperature: float = Field(default=0.1, env="SLM_TEMPERATURE", description="SLM temperature for generation")
    slm_fallback_enabled: bool = Field(default=True, env="SLM_FALLBACK_ENABLED", description="Enable fallback to rule-based extraction")
    
    # =============================================================================
    # PROCESSING CONFIGURATION
    # =============================================================================
    max_file_size_mb: int = Field(default=50, description="Maximum file size in MB")
    max_upload_mb: int = Field(default=50, description="Maximum upload size in MB")
    max_attachment_size_mb: int = Field(default=25, description="Maximum attachment size in MB")
    
    # Processing timeouts (in seconds)
    extract_timeout: int = Field(default=300, description="Extraction timeout")
    normalize_timeout: int = Field(default=60, description="Normalization timeout")
    validate_timeout: int = Field(default=30, description="Validation timeout")
    export_timeout: int = Field(default=120, description="Export timeout")
    
    # VLM processing limits
    vlm_max_pages: int = Field(default=10, description="Maximum pages for VLM processing")
    vlm_confidence_threshold: float = Field(default=0.7, description="VLM confidence threshold")
    
    # =============================================================================
    # EXCEL EXPORT SETTINGS
    # =============================================================================
    excel_template_version: str = Field(default="1.0", description="Excel template version")
    excel_include_provenance_sheet: bool = Field(default=True, description="Include provenance sheet")
    excel_default_missing_value: str = Field(
        default="Information not found",
        description="Default value for missing data"
    )
    
    # =============================================================================
    # DEVELOPMENT SETTINGS
    # =============================================================================
    dev_mode: bool = Field(default=False, description="Development mode")
    dev_auto_reload: bool = Field(default=False, description="Auto-reload in dev")
    dev_show_sql: bool = Field(default=False, description="Show SQL queries in dev")
    
    # Test data
    enable_test_endpoints: bool = Field(default=False, description="Enable test endpoints")
    
    @validator('log_level')
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'log_level must be one of {valid_levels}')
        return v.upper()
    
    @validator('app_env')
    def validate_app_env(cls, v):
        """Validate app environment."""
        valid_envs = ['local', 'dev', 'prod']
        if v.lower() not in valid_envs:
            raise ValueError(f'app_env must be one of {valid_envs}')
        return v.lower()
    
    @validator('cors_origins', pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    
    @validator('allowed_domains', pre=True)
    def parse_allowed_domains(cls, v):
        """Parse allowed domains from string or list."""
        if isinstance(v, str):
            return [domain.strip() for domain in v.split(',')]
        return v
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


# Global settings instance
settings = Settings()
