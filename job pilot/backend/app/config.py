from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    volvo_genai_base_url: str = "https://api.volvogenaihubqa.volvogroup.net"
    volvo_genai_api_key: str = ""
    volvo_genai_deployment: str = "claude-4.6-sonnet"
    volvo_genai_api_version: str = "2025-04-01-preview"

    server_host: str = "0.0.0.0"
    server_port: int = 8000

    max_context_chunks: int = 6
    max_question_logs: int = 500


ROOT_DIR = Path(__file__).resolve().parents[2]
JOB_PILOT_DIR = ROOT_DIR.parent
DOCS_DIR = JOB_PILOT_DIR / "docs"
QUESTIONS_PATH = JOB_PILOT_DIR / "questions.json"


settings = Settings()
