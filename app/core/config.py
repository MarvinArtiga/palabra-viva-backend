from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    app_name: str = "Palabra Viva API"
    api_prefix: str = "/api/v1"

    # Carpeta donde viven los JSON
    data_dir: str = "app/data"

    # Orígenes permitidos (frontend en dev)
    cors_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    class Config:
        env_file = ".env"


settings = Settings()