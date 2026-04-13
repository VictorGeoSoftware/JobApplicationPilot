from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from app.config import settings


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str


class WebSearchService:
    def __init__(self) -> None:
        self.search_url = "https://duckduckgo.com/html/"
        self.verify_ssl = settings.web_search_verify_ssl

    async def search_company(self, company_name: str | None, job_url: str | None) -> str:
        subject = (company_name or "").strip() or self._infer_company_from_url(job_url)
        if not subject:
            return "No company information provided."

        query = f"{subject} engineering culture technology stack product"

        try:
            hits = await self.search(query, limit=4)
        except Exception:
            return f"Unable to fetch live web search results for {subject}."

        if not hits:
            return f"No relevant search snippets found for {subject}."

        return "\n".join(f"- {hit.title} ({hit.url})" for hit in hits)

    async def search(self, query: str, limit: int = 5) -> list[SearchHit]:
        async with httpx.AsyncClient(timeout=12.0, verify=self.verify_ssl) as client:
            response = await client.get(self.search_url, params={"q": query})
        response.raise_for_status()
        hits = self._extract_hits(response.text)
        return hits[:limit]

    def _infer_company_from_url(self, job_url: str | None) -> str:
        if not job_url:
            return ""
        raw = job_url.split("//")[-1].split("/")[0]
        if raw.startswith("www."):
            raw = raw[4:]
        return raw.split(".")[0].replace("-", " ").strip()

    def _extract_hits(self, html: str) -> list[SearchHit]:
        anchor_pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            re.IGNORECASE,
        )
        snippet_pattern = re.compile(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', re.IGNORECASE)

        anchors = anchor_pattern.findall(html)
        snippets = snippet_pattern.findall(html)
        hits: list[SearchHit] = []

        for idx, (raw_href, raw_title) in enumerate(anchors):
            title = self._strip_tags(raw_title)
            if not title:
                continue

            url = self._normalize_duckduckgo_href(raw_href)
            snippet = self._strip_tags(snippets[idx]) if idx < len(snippets) else ""
            hits.append(SearchHit(title=title, url=url, snippet=snippet))

        return hits

    def _normalize_duckduckgo_href(self, href: str) -> str:
        if not href:
            return ""

        if href.startswith("//"):
            href = f"https:{href}"

        parsed = urlparse(href)
        if "duckduckgo.com" not in parsed.netloc:
            return href

        query = parse_qs(parsed.query)
        target = query.get("uddg", [""])[0]
        return unquote(target) if target else href

    def _strip_tags(self, value: str) -> str:
        plain = re.sub(r"<[^>]+>", "", value)
        return " ".join(plain.split())
