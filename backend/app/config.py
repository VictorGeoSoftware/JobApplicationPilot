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
    tavily_api_key: str = ""

    # Tavily search/extract tuning (subscription features)
    tavily_search_depth: str = "advanced"      # "basic" | "advanced"
    tavily_time_range: str = "week"            # "day" | "week" | "month" | "year"
    tavily_extract_depth: str = "advanced"     # "basic" | "advanced"
    tavily_max_results: int = 8

    # JobSeeker eligibility filtering
    job_search_exclude_contract: bool = True           # drop contractor/freelance roles
    job_search_require_sweden_eligibility: bool = True  # drop roles that are clearly not open to Sweden
    job_search_max_extracts: int = 18                  # cap full-page extracts per run (credit control)


# Repo root: backend/app/config.py -> parents[2] == project root.
# Data lives at the repo root alongside the backend/ folder.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = PROJECT_ROOT / "docs"
QUESTIONS_PATH = PROJECT_ROOT / "questions.json"
AGENT_CONFIG_PATH = PROJECT_ROOT / "AGENT_CONFIG.md"


settings = Settings()
