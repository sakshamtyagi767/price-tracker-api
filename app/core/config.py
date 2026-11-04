from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # application info
    PROJECT_NAME: str = "Multi-Tenant Price Tracker API"
    API_V1_STR: str = "/api/v1"

    # Security & JWT Authentication
    SECRET_KEY: str = "CHANGE_THIS_TO_A_SUPER_SECRET_KEY_IN_PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # Database
    DATABASE_URL: str = "sqlite:///./price_tracker.db"

    # Task Queue / Broker (for Celery & Background Workers)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Pydantic Settings Configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignores any unexpected variables in .env without raising an error
    )


# Instantiate a singleton object that you can import across the app
settings = Settings()
