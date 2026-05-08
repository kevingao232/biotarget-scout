from functools import lru_cache
from pydantic import BaseModel, Field
import os


class Settings(BaseModel):
    biotarget_env: str = Field(default=os.getenv("BIOTARGET_ENV", "dev"))
    log_level: str = Field(default=os.getenv("LOG_LEVEL", "INFO"))
    local_model_base_url: str = Field(default=os.getenv("LOCAL_MODEL_BASE_URL", "http://localhost:11434/v1"))
    local_model_name: str = Field(default=os.getenv("LOCAL_MODEL_NAME", "llama3.1"))
    openai_api_key: str = Field(default=os.getenv("OPENAI_API_KEY", ""))
    anthropic_api_key: str = Field(default=os.getenv("ANTHROPIC_API_KEY", ""))
    xai_api_key: str = Field(default=os.getenv("XAI_API_KEY", ""))
    ncbi_email: str = Field(default=os.getenv("NCBI_EMAIL", "you@example.com"))
    ncbi_api_key: str = Field(default=os.getenv("NCBI_API_KEY", ""))
    request_timeout_seconds: int = Field(default=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20")))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
