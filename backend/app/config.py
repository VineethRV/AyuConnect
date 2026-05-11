"""Runtime configuration.

The backend supports three Gemma 4 inference paths so the same code runs on a
field laptop (Ollama), a Kaggle GPU notebook (Transformers), or a shared cluster
(vLLM) without code changes — only an env var.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Backend(str, Enum):
    OLLAMA = "ollama"
    TRANSFORMERS = "transformers"
    VLLM = "vllm"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AYU_", extra="ignore")

    backend: Backend = Backend.OLLAMA
    model_id: str = "google/gemma-4-E4B-it"

    ollama_host: str = "http://localhost:11434"
    vllm_base_url: str = "http://localhost:8000/v1"
    vllm_api_key: str = "token-ayuconnect"

    max_new_tokens: int = 768
    temperature: float = 0.4
    tool_loop_budget: int = 4

    allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    kb_path: str = "app/data/medical_kb.json"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
