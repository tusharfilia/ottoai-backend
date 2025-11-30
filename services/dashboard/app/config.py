"""
Centralized configuration management for OttoAI backend.
Loads and validates all environment variables.
"""
import os
from typing import Optional, List


class Settings:
    """Application settings loaded from environment variables."""
    
    def __init__(self):
        # Database
        # Database URL with fallback for development
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./otto_dev.db")
        
        # Clerk Authentication
        self.CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY", "")
        self.CLERK_PUBLISHABLE_KEY = os.getenv("CLERK_PUBLISHABLE_KEY", "")
        self.CLERK_API_URL = os.getenv("CLERK_API_URL", "https://api.clerk.dev/v1")
        self.CLERK_ISSUER = os.getenv("CLERK_ISSUER", "https://elegant-bluebird-22.clerk.accounts.dev")
        self.CLERK_FRONTEND_ORIGIN = os.getenv("CLERK_FRONTEND_ORIGIN", "https://elegant-bluebird-22.clerk.accounts.dev")
        self.CLERK_WEBHOOK_SECRET = os.getenv("CLERK_WEBHOOK_SECRET")
        
        # Twilio
        self.TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")
        self.TWILIO_CALLBACK_NUMBER = os.getenv("TWILIO_CALLBACK_NUMBER", "")
        self.TWILIO_API_BASE_URL = os.getenv("TWILIO_API_BASE_URL", "https://api.twilio.com")
        
        # CallRail
        self.CALLRAIL_API_KEY = os.getenv("CALLRAIL_API_KEY", "")
        self.CALLRAIL_ACCOUNT_ID = os.getenv("CALLRAIL_ACCOUNT_ID", "")
        self.CALLRAIL_BASE_URL = os.getenv("CALLRAIL_BASE_URL", "https://api.callrail.com/v3")
        
        # Deepgram
        self.DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
        self.DEEPGRAM_API_BASE_URL = os.getenv("DEEPGRAM_API_BASE_URL", "https://api.deepgram.com")
        
        # OpenAI
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        # Multiple keys for rotation: comma-separated or OPENAI_API_KEY_1, OPENAI_API_KEY_2, etc.
        self.OPENAI_API_KEYS = os.getenv("OPENAI_API_KEYS", "")  # Comma-separated list
        self.OPENAI_KEY_ROTATION_STRATEGY = os.getenv("OPENAI_KEY_ROTATION_STRATEGY", "round_robin")  # round_robin, random, least_used
        
        # Bland AI
        self.BLAND_API_KEY = os.getenv("BLAND_API_KEY", "")
        
        # Google Maps (for geocoding)
        self.GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
        
        # UWC (Unified Workflow Composer) Integration
        # Default to Shunya mock for local development if not provided
        self.UWC_BASE_URL = os.getenv("UWC_BASE_URL") or "https://otto.shunyalabs.ai"
        self.UWC_API_KEY = os.getenv("UWC_API_KEY", "")
        self.UWC_JWT_SECRET = os.getenv("UWC_JWT_SECRET", "")
        self.UWC_HMAC_SECRET = os.getenv("UWC_HMAC_SECRET", "")
        self.UWC_VERSION = os.getenv("UWC_VERSION", "v1")
        self.USE_UWC_STAGING = os.getenv("USE_UWC_STAGING", "false").lower() in ("true", "1", "yes")
        
        # UWC Feature Flags
        self.ENABLE_UWC_RAG = os.getenv("ENABLE_UWC_RAG", "false").lower() in ("true", "1", "yes")
        self.ENABLE_UWC_ASR = os.getenv("ENABLE_UWC_ASR", "false").lower() in ("true", "1", "yes")
        self.ENABLE_UWC_TRAINING = os.getenv("ENABLE_UWC_TRAINING", "false").lower() in ("true", "1", "yes")
        self.ENABLE_UWC_FOLLOWUPS = os.getenv("ENABLE_UWC_FOLLOWUPS", "false").lower() in ("true", "1", "yes")
        self.ENABLE_UWC_SUMMARIZATION = os.getenv("ENABLE_UWC_SUMMARIZATION", "false").lower() in ("true", "1", "yes")
        
        # AWS S3 Storage
        self.AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
        self.AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        # Prefer explicit AWS_REGION, fall back to AWS_DEFAULT_REGION, then us-east-1
        self.AWS_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        # Use a safer default for non-production
        self.S3_BUCKET = os.getenv(
            "S3_BUCKET",
            "otto-documents-prod" if os.getenv("ENVIRONMENT", "development").lower() == "production" else "otto-documents-staging",
        )
        
        # Sentry Error Tracking
        self.SENTRY_DSN = os.getenv("SENTRY_DSN", "")
        self.SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
        
        # Environment
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
        
        # CORS Configuration
        allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,exp://*")
        self.ALLOWED_ORIGINS = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]
        
        # Redis Configuration
        self.REDIS_URL = os.getenv("REDIS_URL") or os.getenv("UPSTASH_REDIS_URL")
        
        # Rate Limiting Configuration
        self.ENABLE_RATE_LIMITING = os.getenv("ENABLE_RATE_LIMITING", "true").lower() in ("true", "1", "yes")
        self.RATE_LIMIT_USER = os.getenv("RATE_LIMIT_USER", "60/minute")
        self.RATE_LIMIT_TENANT = os.getenv("RATE_LIMIT_TENANT", "600/minute")
        
        # Celery Configuration
        self.ENABLE_CELERY = os.getenv("ENABLE_CELERY", "false").lower() in ("true", "1", "yes")
        self.ENABLE_CELERY_BEAT = os.getenv("ENABLE_CELERY_BEAT", "false").lower() in ("true", "1", "yes")
        
        # Idempotency Configuration
        self.IDEMPOTENCY_TTL_DAYS = int(os.getenv("IDEMPOTENCY_TTL_DAYS", "90"))
        
        # Observability Configuration
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.OBS_REDACT_PII = os.getenv("OBS_REDACT_PII", "true").lower() in ("true", "1", "yes")
        self.OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
        self.OTEL_SERVICE_NAME_API = os.getenv("OTEL_SERVICE_NAME_API", "otto-api")
        self.OTEL_SERVICE_NAME_WORKER = os.getenv("OTEL_SERVICE_NAME_WORKER", "otto-worker")
        
        # Development/Testing Configuration
        self.DEV_EMIT_KEY = os.getenv("DEV_EMIT_KEY")
        self.DEV_MODE = os.getenv("DEV_MODE", "false").lower() in ("true", "1", "yes")
        self.DEV_TEST_COMPANY_ID = os.getenv("DEV_TEST_COMPANY_ID", "dev-test-company")
        self.DEV_TEST_USER_ID = os.getenv("DEV_TEST_USER_ID", "dev-test-user")
        
        # Internal AI API Configuration (for Shunya/UWC integration)
        self.AI_INTERNAL_TOKEN = os.getenv("AI_INTERNAL_TOKEN", "")
        
        # Validate required settings
        self._validate_settings()
    
    def _validate_settings(self):
        """Validate required settings with environment-aware relaxations."""
        is_prod = self.is_production

        # In production enforce core third-party secrets
        if is_prod:
            required_settings = [
                ('CLERK_SECRET_KEY', self.CLERK_SECRET_KEY),
                ('TWILIO_ACCOUNT_SID', self.TWILIO_ACCOUNT_SID),
                ('TWILIO_AUTH_TOKEN', self.TWILIO_AUTH_TOKEN),
                ('CALLRAIL_API_KEY', self.CALLRAIL_API_KEY),
                ('DEEPGRAM_API_KEY', self.DEEPGRAM_API_KEY),
                ('OPENAI_API_KEY', self.OPENAI_API_KEY),
                ('BLAND_API_KEY', self.BLAND_API_KEY),
            ]
            for name, value in required_settings:
                if value in ['CHANGE_ME', f'your_{name.lower()}', '']:
                    raise ValueError(f'{name} must be set to a real value, not a placeholder')

        # Redis requirement handling
        if (self.ENABLE_CELERY or self.is_rate_limiting_enabled()) and not self.REDIS_URL:
            if is_prod:
                raise ValueError('REDIS_URL or UPSTASH_REDIS_URL must be set when Celery or rate limiting is enabled')
            # In non-production, auto-disable rate limiting to avoid startup crash
            self.ENABLE_RATE_LIMITING = False
    
    def is_rate_limiting_enabled(self) -> bool:
        """Check if rate limiting is enabled."""
        return self.ENABLE_RATE_LIMITING
    
    @property
    def clerk_jwks_url(self) -> str:
        """Get the Clerk JWKS URL."""
        return f"{self.CLERK_FRONTEND_ORIGIN}/.well-known/jwks.json"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT.lower() == "production"
    
    def is_uwc_enabled(self) -> bool:
        """Check if any UWC feature is enabled."""
        return any([
            self.ENABLE_UWC_RAG,
            self.ENABLE_UWC_ASR,
            self.ENABLE_UWC_TRAINING,
            self.ENABLE_UWC_FOLLOWUPS,
            self.ENABLE_UWC_SUMMARIZATION
        ])
    
    def is_storage_configured(self) -> bool:
        """Check if S3 storage is properly configured."""
        return bool(
            self.AWS_ACCESS_KEY_ID and 
            self.AWS_SECRET_ACCESS_KEY and 
            self.S3_BUCKET
        )


# Global settings instance
settings = Settings()
