from __future__ import annotations

from typing import Protocol


class MissingConfigError(RuntimeError):
    pass


class UpstreamModelError(RuntimeError):
    pass


class LLMClient(Protocol):
    provider: str
    model: str

    async def generate_answer(
        self,
        system_prompt: str,
        user_prompt: str,
        screenshot_base64: str | None,
    ) -> str: ...
