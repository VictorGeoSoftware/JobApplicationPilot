from __future__ import annotations

import base64

import httpx

from app.config import settings


class VolvoGenAIClient:
    def __init__(self) -> None:
        self.endpoint = (
            f"{settings.volvo_genai_base_url}/azure-openai-data-inference/openai/deployments/"
            f"{settings.volvo_genai_deployment}/chat/completions"
        )

    async def generate_answer(
        self,
        system_prompt: str,
        user_prompt: str,
        screenshot_base64: str | None,
    ) -> str:
        if not settings.volvo_genai_api_key:
            raise RuntimeError("VOLVO_GENAI_API_KEY is missing")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        if screenshot_base64:
            messages.append(self._build_vision_message(screenshot_base64))

        payload = {
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 1200,
        }

        params = {"api-version": settings.volvo_genai_api_version}
        headers = {"api-key": settings.volvo_genai_api_key}

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.endpoint, params=params, headers=headers, json=payload)

        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

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
