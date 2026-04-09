from __future__ import annotations

from app.config import settings
from app.services.ai_client import AIClient
from app.services.claude_client import ClaudeClient
from app.services.llm_client import LLMClient, MissingConfigError


def build_llm_client() -> LLMClient:
    provider = settings.llm_provider.lower().strip()

    if provider == "azure_openai":
        provider = "openai"

    if provider == "openai":
        return AIClient()

    if provider in {"claude", "anthropic"}:
        return ClaudeClient()

    raise MissingConfigError(
        "Unsupported LLM_PROVIDER. Use one of: openai, claude, anthropic"
    )
