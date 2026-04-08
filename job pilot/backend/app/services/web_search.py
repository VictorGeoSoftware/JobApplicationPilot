from __future__ import annotations

import re

import httpx


class WebSearchService:
    async def search_company(self, company_name: str | None, job_url: str | None) -> str:
        subject = (company_name or "").strip() or self._infer_company_from_url(job_url)
        if not subject:
            return "No company information provided."

        query = f"{subject} engineering culture technology stack product"
        url = "https://duckduckgo.com/html/"

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.get(url, params={"q": query})
            response.raise_for_status()
            snippets = self._extract_snippets(response.text)
        except Exception:
            return f"Unable to fetch live web search results for {subject}."

        if not snippets:
            return f"No relevant search snippets found for {subject}."

        top = snippets[:4]
        return "\n".join(f"- {line}" for line in top)

    def _infer_company_from_url(self, job_url: str | None) -> str:
        if not job_url:
            return ""
        raw = job_url.split("//")[-1].split("/")[0]
        if raw.startswith("www."):
            raw = raw[4:]
        return raw.split(".")[0].replace("-", " ").strip()

    def _extract_snippets(self, html: str) -> list[str]:
        pattern = re.compile(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', re.IGNORECASE)
        title_hits = pattern.findall(html)

        def strip_tags(value: str) -> str:
            plain = re.sub(r"<[^>]+>", "", value)
            return " ".join(plain.split())

        return [strip_tags(hit) for hit in title_hits if strip_tags(hit)]
