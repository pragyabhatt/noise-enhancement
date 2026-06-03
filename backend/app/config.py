import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Resolve DB path absolutely so it is consistent across execution contexts
    DATABASE_URL: str = f"sqlite+aiosqlite:///{os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'catr_se.db'))}"

    
    # JWT authentication settings
    JWT_SECRET_KEY: str = "deal_labs_secure_jwt_secret_key_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # AES-256-GCM encryption key at rest (must be 32-byte URL-safe base64 encoded)
    # Generate using: base64.urlsafe_b64encode(os.urandom(32)).decode()
    ENCRYPTION_KEY: str = "ENCRYPTION_KEY_PLACEHOLDER_32_BYTES="
    
    # Directory paths
    MODELS_DIR: str = os.path.abspath(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
    )
    DATA_DIR: str = os.path.abspath(
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
    )
    
    UPLOAD_DIR: str = os.path.join(DATA_DIR, "uploads")
    EXPORT_DIR: str = os.path.join(DATA_DIR, "exports")
    
    # Network / Deployment
    CATR_OFFLINE: bool = True
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.EXPORT_DIR, exist_ok=True)
os.makedirs(settings.MODELS_DIR, exist_ok=True)
