from __future__ import annotations

import base64

import httpx

from app.config import settings
from app.services.llm_client import MissingConfigError, UpstreamModelError


class AIClient:
    def __init__(self) -> None:
        self.provider = "openai"
        self.model = settings.ai_deployment
        self.endpoint = (
            f"{settings.ai_base_url}/azure-openai-data-inference/openai/deployments/"
            f"{settings.ai_deployment}/chat/completions"
        )

    async def generate_answer(
        self,
        system_prompt: str,
        user_prompt: str,
        screenshot_base64: str | None,
    ) -> str:
        if not settings.ai_api_key:
            raise MissingConfigError("AI_API_KEY is missing")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        params = {"api-version": settings.ai_api_version}
        headers = {"api-key": settings.ai_api_key}

        vision_error: str | None = None
        if screenshot_base64:
            try:
                vision_messages = [*messages, self._build_vision_message(screenshot_base64)]
                return await self._send_request(vision_messages, params=params, headers=headers)
            except UpstreamModelError as error:
                vision_error = str(error)

        answer = await self._send_request(messages, params=params, headers=headers)
        if vision_error:
            return f"{answer}\n\n(Note: screenshot vision processing fallback was used due to upstream format limitations.)"
        return answer

    async def _send_request(self, messages: list[dict], params: dict, headers: dict) -> str:
        payload = {"messages": messages}

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.endpoint, params=params, headers=headers, json=payload)

        if response.status_code >= 400:
            detail = response.text.strip()
            snippet = detail[:500] if detail else "No response body"
            raise UpstreamModelError(f"AI provider {response.status_code}: {snippet}")

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            text_parts = [part.get("text", "") for part in content if isinstance(part, dict)]
            return "\n".join(part for part in text_parts if part).strip()
        return str(content).strip()

    def _build_vision_message(self, screenshot_base64: str) -> dict:
        content_type = "image/png"
        image_data = screenshot_base64.strip()

        if image_data.startswith("data:"):
            head, encoded = image_data.split(",", 1)
            image_data = encoded
            if ";base64" in head and ":" in head:
                content_type = head.split(":", 1)[1].split(";", 1)[0]

        base64.b64decode(image_data, validate=False)

        return {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Analyze this job application screenshot. Extract visible prompts and key constraints "
                        "to improve the answer quality."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{content_type};base64,{image_data}"},
                },
            ],
        }
