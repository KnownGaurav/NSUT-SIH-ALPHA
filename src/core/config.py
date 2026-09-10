import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings loaded from environment variables and .env file.
    Follows 12-factor application design principles.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # API Configuration
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    API_PREFIX: str = "/api"
    PROJECT_NAME: str = "Dynamic Railway ETA Prediction Platform"
    VERSION: str = "1.0.0"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    # Data Provider: 'simulation' | 'railradar' | 'third_party' | 'cris_ntes'
    DATA_PROVIDER: str = "simulation"

    # Rail Radar Live Train API Configuration
    RAILRADAR_API_KEY: str = ""
    RAILRADAR_BASE_URL: str = "https://api.railradar.in/v1"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/railway_eta.db"

    # Redis Cache
    REDIS_URL: str = "redis://localhost:6379/0"

    # Weather
    OPEN_METEO_API_URL: str = "https://api.open-meteo.com/v1/forecast"

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_simulation(self) -> bool:
        return self.DATA_PROVIDER.lower().strip() == "simulation"

    @property
    def is_railradar(self) -> bool:
        return self.DATA_PROVIDER.lower().strip() == "railradar"


settings = Settings()
