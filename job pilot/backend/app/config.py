from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: str = "openai"

    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_deployment: str = "claude-4.6-sonnet"
    ai_api_version: str = "2025-04-01-preview"

    claude_model: str = "claude-sonnet-4-5_gb_20250929"
    claude_max_tokens: int = 1400
    claude_temperature: float = 0.2

    server_host: str = "0.0.0.0"
    server_port: int = 8000

    max_context_chunks: int = 6
    max_question_logs: int = 500
    web_search_verify_ssl: bool = True


ROOT_DIR = Path(__file__).resolve().parents[2]
JOB_PILOT_DIR = ROOT_DIR.parent
DOCS_DIR = JOB_PILOT_DIR / "docs"
QUESTIONS_PATH = JOB_PILOT_DIR / "questions.json"
AGENT_CONFIG_PATH = JOB_PILOT_DIR / "AGENT_CONFIG.md"


settings = Settings()
