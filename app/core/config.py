from pydantic import Field
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    app_name: str = "Palabra Viva API"
    api_prefix: str = "/api/v1"

    # Root para datos persistentes/cache. Fly puede montarlo en /app/data.
    data_dir: str = Field(default="./data", alias="DATA_DIR")

    # Lista separada por coma: https://mi-app.vercel.app,https://admin.vercel.app
    allowed_origins: str = Field(default="", alias="ALLOWED_ORIGINS")

    @property
    def cors_origins(self) -> List[str]:
        origins = [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]
        if origins:
            return origins
        return [
            "http://localhost",
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]


settings = Settings()
