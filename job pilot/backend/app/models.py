from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class RecruiterRequest(BaseModel):
    question: str = Field(min_length=3)
    company_name: str | None = None
    job_url: str | None = None
    screenshot_base64: str | None = None
    chat_history: list[ChatMessage] = Field(default_factory=list)


class RecruiterResponse(BaseModel):
    answer: str
    used_context_files: list[str]
    web_research: str
