from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str
    openai_vision_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimension: int = 512

    # Gemini
    gemini_api_key: str = ""

    # Supabase
    supabase_url: str
    supabase_key: str
    supabase_storage_bucket: str = "complaint-images"

    # Tesseract
    tesseract_cmd: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    # Auth
    api_key: str

    # Rate Limiting
    rate_limit_per_minute: int = 10

    # Duplicate Detection
    duplicate_threshold: float = 0.92

    # App
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    max_file_size_mb: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()