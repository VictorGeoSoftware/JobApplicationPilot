from __future__ import annotations

from app.config import settings
from app.models import RecruiterRequest
from app.services.context_store import ContextStore
from app.services.volvo_genai_client import VolvoGenAIClient
from app.services.web_search import WebSearchService


class RecruiterAgent:
    def __init__(self, context_store: ContextStore, web_search: WebSearchService, llm_client: VolvoGenAIClient) -> None:
        self.context_store = context_store
        self.web_search = web_search
        self.llm_client = llm_client

    async def answer(self, payload: RecruiterRequest) -> tuple[str, list[str], str]:
        retrieved = self.context_store.retrieve(payload.question, limit=settings.max_context_chunks)
        context_blocks = [chunk.text for chunk in retrieved]
        context_files = sorted({chunk.file_name for chunk in retrieved})

        web_research = await self.web_search.search_company(payload.company_name, payload.job_url)
        chat_history = "\n".join(f"{item.role}: {item.content}" for item in payload.chat_history[-6:])

        user_prompt = self._build_user_prompt(
            question=payload.question,
            context_blocks=context_blocks,
            web_research=web_research,
            chat_history=chat_history,
            company_name=payload.company_name,
        )

        answer = await self.llm_client.generate_answer(
            system_prompt=self._system_prompt(),
            user_prompt=user_prompt,
            screenshot_base64=payload.screenshot_base64,
        )
        return answer, context_files, web_research

    def _system_prompt(self) -> str:
        return (
            "You are an Elite Technical Recruiter specialized in helping software engineers win job applications. "
            "Use STAR method thinking (Situation, Task, Action, Result), balance technical depth and soft skills, "
            "and tailor answers to the company context and user background. "
            "Always format your output with exactly these sections and emojis:\n"
            "🔍 The Real Intent\n"
            "🧠 The Strategy\n"
            "✍️ The Perfect Answer\n"
            "In The Perfect Answer section, produce final text that the candidate can directly paste into the application."
        )

    def _build_user_prompt(
        self,
        question: str,
        context_blocks: list[str],
        web_research: str,
        chat_history: str,
        company_name: str | None,
    ) -> str:
        docs_context = "\n\n".join(f"[Context {idx + 1}] {text}" for idx, text in enumerate(context_blocks))
        return (
            f"Candidate question:\n{question}\n\n"
            f"Target company: {company_name or 'Not provided'}\n\n"
            f"Recent chat context:\n{chat_history or 'None'}\n\n"
            f"RAG context from /docs:\n{docs_context or 'No local context found.'}\n\n"
            f"Web research notes:\n{web_research}\n\n"
            "Generate a strategic but concise answer. If context is missing, state assumptions briefly and avoid inventing facts."
        )
