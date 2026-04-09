from __future__ import annotations

import base64

import httpx

from app.config import settings
from app.services.llm_client import MissingConfigError, UpstreamModelError


class ClaudeClient:
    def __init__(self) -> None:
        self.provider = "claude"
        self.model = settings.claude_model
        self.endpoint = f"{settings.ai_base_url}/anthropic/v1/messages"

    async def generate_answer(
        self,
        system_prompt: str,
        user_prompt: str,
        screenshot_base64: str | None,
    ) -> str:
        api_key = settings.ai_api_key.strip()
        if not api_key or api_key == "your_api_key_here":
            raise MissingConfigError("AI_API_KEY is missing")

        message_content: str | list[dict] = user_prompt
        if screenshot_base64:
            message_content = [
                {"type": "text", "text": user_prompt},
                self._build_image_block(screenshot_base64),
            ]

        payload = {
            "model": self.model,
            "max_tokens": settings.claude_max_tokens,
            "temperature": settings.claude_temperature,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": message_content,
                }
            ],
        }

        headers = {
            "x-api-key": api_key,
            "api-key": api_key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.endpoint, headers=headers, json=payload)

        if response.status_code >= 400:
            detail = response.text.strip()
            snippet = detail[:500] if detail else "No response body"
            raise UpstreamModelError(f"Claude request failed {response.status_code}: {snippet}")

        data = response.json()
        content = data.get("content", [])

        if isinstance(content, list):
            text_parts = [block.get("text", "") for block in content if isinstance(block, dict)]
            answer = "\n".join(part for part in text_parts if part).strip()
            if answer:
                return answer

        raise UpstreamModelError("Claude returned an empty response")

    def _build_image_block(self, screenshot_base64: str) -> dict:
        content_type = "image/png"
        image_data = screenshot_base64.strip()

        if image_data.startswith("data:"):
            head, encoded = image_data.split(",", 1)
            image_data = encoded
            if ";base64" in head and ":" in head:
                content_type = head.split(":", 1)[1].split(";", 1)[0]

        base64.b64decode(image_data, validate=False)

        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": content_type,
                "data": image_data,
            },
        }
