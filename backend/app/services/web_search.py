from __future__ import annotations

from dataclasses import dataclass
import html
import re
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from app.config import settings


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    raw_content: str = ""
    published_date: str = ""
    employment_type: str = "unknown"     # "permanent" | "contract" | "unknown"
    sweden_eligibility: str = "unknown"  # "eligible" | "restricted" | "blocked" | "unknown"


# --- Eligibility / employment classification ------------------------------------

_CONTRACT_TITLE_MARKERS = (
    "freelance",
    "freelancer",
    "contractor",
    "contract role",
    "b2b",
    "interim",
)
_CONTRACT_BODY_MARKERS = (
    "freelance",
    "contractor",
    "contract position",
    "contract role",
    "b2b contract",
    "b2b only",
    "fixed-term",
    "fixed term",
    "/hour",
    "/hr",
    " per hour",
    "hourly rate",
    "daily rate",
    "self-employed",
    "umowa b2b",
    "zlecenie",
    "c2c",
)
_PERMANENT_MARKERS = (
    "permanent",
    "full-time employee",
    "full time employee",
    "tillsvidare",
    "fast anställning",
    "fast anstallning",
    "festanstellung",
    "unbefristet",
    "permanent contract",
    "permanent position",
)

# Sweden / EU eligibility signals
_ELIGIBLE_MARKERS = (
    "sweden",
    "sverige",
    "european union",
    " eu ",
    " eu,",
    " eu.",
    "eu-based",
    "eea",
    "europe",
    "european",
    "emea",
    "anywhere in europe",
    "cet",
    "cest",
    "nordic",
)
_US_ONLY_MARKERS = (
    "us only",
    "u.s. only",
    "usa only",
    "united states only",
    "must be located in the united states",
    "must reside in the united states",
    "must be based in the us",
    "authorized to work in the united states",
    "us work authorization",
    "us-based only",
)
# Single non-Sweden countries that, when paired with "only/based in/residents of",
# indicate a country-locked remote role.
_OTHER_COUNTRY_LOCKS = (
    "germany",
    "poland",
    "spain",
    "france",
    "united kingdom",
    "uk only",
    "ukraine",
    "lithuania",
    "romania",
    "portugal",
    "netherlands",
    "switzerland",
    "italy",
    "ireland",
    "india",
    "canada",
)
_RESTRICT_CONTEXT = ("only", "based in", "located in", "residents of", "must be in", "reside in")


def classify_employment(title: str, body: str) -> str:
    """Return 'contract', 'permanent', or 'unknown' from a job title + body text."""
    title_l = (title or "").lower()
    body_l = (body or "").lower()
    if any(marker in title_l for marker in _CONTRACT_TITLE_MARKERS):
        return "contract"
    has_contract = any(marker in body_l for marker in _CONTRACT_BODY_MARKERS)
    has_permanent = any(marker in body_l for marker in _PERMANENT_MARKERS)
    if has_contract and not has_permanent:
        return "contract"
    if has_permanent:
        return "permanent"
    return "unknown"


def classify_sweden_eligibility(body: str) -> tuple[str, str]:
    """Return (status, note) where status is eligible|restricted|blocked|unknown."""
    text = (body or "").lower()
    if not text:
        return "unknown", "No description text available to verify eligibility."

    mentions_eu = any(marker in text for marker in _ELIGIBLE_MARKERS)

    if any(marker in text for marker in _US_ONLY_MARKERS) and not mentions_eu:
        return "blocked", "Listing states US-only work authorization."

    for country in _OTHER_COUNTRY_LOCKS:
        if country in text:
            window_ok = any(
                f"{ctx} {country}" in text or f"{country} {ctx}" in text or f"{country} only" in text
                for ctx in _RESTRICT_CONTEXT
            )
            if window_ok and "sweden" not in text and not _broad_eu(text):
                return "restricted", f"Listing appears locked to {country.strip()}."

    if "sweden" in text or _broad_eu(text):
        return "eligible", "Listing references Sweden / EU / Europe eligibility."
    if mentions_eu:
        return "eligible", "Listing references European eligibility."
    return "unknown", "Eligibility for Sweden could not be confirmed from the text."


def _broad_eu(text: str) -> bool:
    return any(
        marker in text
        for marker in ("anywhere in europe", "across europe", "eu-wide", "european union", "eea", "emea", "remote europe", "europe remote")
    )


# --- Source / domain hygiene ----------------------------------------------------

# Domains that virtually never host an applyable job posting. Matched on the
# registrable domain so subdomains are covered too. Also used as Tavily
# `exclude_domains` so the noise is filtered at the source (saving credits).
NON_LISTING_DOMAINS: tuple[str, ...] = (
    "news.ycombinator.com",
    "ycombinator.com",
    "github.com",
    "gist.github.com",
    "gitlab.com",
    "bitbucket.org",
    "gstars.dev",
    "instagram.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "reddit.com",
    "tiktok.com",
    "pinterest.com",
    "youtube.com",
    "youtu.be",
    "medium.com",
    "dev.to",
    "quora.com",
    "stackoverflow.com",
    "stackexchange.com",
    "t.me",
    "telegram.me",
)

# Path fragments that indicate a blog/index/sitemap rather than a single role.
NON_LISTING_PATH_MARKERS: tuple[str, ...] = (
    "/blog/",
    "/blog-",
    "/categories",
    "/category/",
    "/tag/",
    "/tags/",
    "/plan-site",
    "/sitemap",
    "/job-description-templates",
    "/articles/",
    "/news/",
)


def is_non_listing_url(url: str) -> bool:
    """True when a URL is a known non-listing source (social, forum, repo, blog)."""
    if not url:
        return True
    try:
        parsed = urlparse(url if "//" in url else f"https://{url}")
    except ValueError:
        return True
    host = (parsed.netloc or "").lower().lstrip("www.")
    path = (parsed.path or "").lower()
    for domain in NON_LISTING_DOMAINS:
        if host == domain or host.endswith(f".{domain}"):
            return True
    return any(marker in path for marker in NON_LISTING_PATH_MARKERS)


# Phrases that signal we are looking at a real job description rather than an
# aggregator/category page or navigation boilerplate.
_JD_STRONG_MARKERS = (
    "responsibilities",
    "key responsibilities",
    "what you'll do",
    "what you will do",
    "what you’ll do",
    "about the role",
    "about you",
    "who you are",
    "your profile",
    "requirements",
    "minimum qualifications",
    "preferred qualifications",
    "qualifications",
    "we offer",
    "what we offer",
    "role overview",
    "apply for this job",
    "job description",
)


def looks_like_job_description(text: str) -> bool:
    """Heuristic: does this text read like a single role's description?

    Used to decide whether a page still needs a full-content Extract pass.
    Aggregator/category pages and nav boilerplate rarely contain two or more
    of these structural JD phrases, even when they are long.
    """
    body = (text or "").lower()
    if len(body) < 300:
        return False
    strong = sum(1 for marker in _JD_STRONG_MARKERS if marker in body)
    return strong >= 2


class WebSearchService:
    def __init__(self) -> None:
        self.search_url = "https://html.duckduckgo.com/html/"
        self.tavily_url = "https://api.tavily.com/search"
        self.tavily_extract_url = "https://api.tavily.com/extract"
        self.tavily_api_key = settings.tavily_api_key.strip()
        self.search_depth = settings.tavily_search_depth
        self.time_range = settings.tavily_time_range
        self.extract_depth = settings.tavily_extract_depth
        self.verify_ssl = settings.web_search_verify_ssl
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
        }

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

    async def search(
        self,
        query: str,
        limit: int = 5,
        *,
        time_range: str | None = None,
        topic: str = "general",
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        include_raw_content: bool = False,
    ) -> list[SearchHit]:
        if self.tavily_api_key:
            try:
                hits = await self._search_tavily(
                    query,
                    limit,
                    time_range=time_range if time_range is not None else self.time_range,
                    topic=topic,
                    include_domains=include_domains,
                    exclude_domains=exclude_domains,
                    include_raw_content=include_raw_content,
                )
                if hits:
                    return hits
            except Exception:
                pass
        return await self._search_duckduckgo(query, limit)

    async def _search_tavily(
        self,
        query: str,
        limit: int,
        *,
        time_range: str | None = None,
        topic: str = "general",
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        include_raw_content: bool = False,
    ) -> list[SearchHit]:
        payload: dict[str, object] = {
            "query": query,
            "max_results": limit,
            "search_depth": self.search_depth,
            "topic": topic,
            "include_raw_content": include_raw_content,
        }
        if time_range:
            payload["time_range"] = time_range
        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains

        headers = {
            "Authorization": f"Bearer {self.tavily_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30.0, verify=self.verify_ssl) as client:
            response = await client.post(self.tavily_url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        hits: list[SearchHit] = []
        for item in data.get("results", []):
            title = self._strip_tags(str(item.get("title") or ""))
            url = str(item.get("url") or "")
            snippet = self._strip_tags(str(item.get("content") or ""))
            raw = item.get("raw_content")
            raw_content = self._strip_tags(str(raw)) if raw else ""
            published = str(item.get("published_date") or "")
            if title and url:
                hits.append(
                    SearchHit(
                        title=title,
                        url=url,
                        snippet=snippet,
                        raw_content=raw_content,
                        published_date=published,
                    )
                )
        return hits[:limit]

    async def extract(self, urls: list[str], extract_depth: str | None = None) -> dict[str, str]:
        """Fetch full page text for a batch of URLs via the Tavily Extract API.

        Returns a mapping of url -> cleaned page text. Empty when Tavily is
        unconfigured or all extractions fail.
        """
        clean_urls = [u for u in dict.fromkeys(urls) if u]
        if not clean_urls or not self.tavily_api_key:
            return {}

        headers = {
            "Authorization": f"Bearer {self.tavily_api_key}",
            "Content-Type": "application/json",
        }
        results: dict[str, str] = {}
        # Tavily Extract accepts up to 20 URLs per request.
        for start in range(0, len(clean_urls), 20):
            batch = clean_urls[start : start + 20]
            payload = {"urls": batch, "extract_depth": extract_depth or self.extract_depth}
            try:
                async with httpx.AsyncClient(timeout=40.0, verify=self.verify_ssl) as client:
                    response = await client.post(self.tavily_extract_url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
            except Exception:
                continue
            for item in data.get("results", []):
                url = str(item.get("url") or "")
                content = self._strip_tags(str(item.get("raw_content") or item.get("content") or ""))
                if url and content:
                    results[url] = content
        return results

    async def _search_duckduckgo(self, query: str, limit: int) -> list[SearchHit]:
        async with httpx.AsyncClient(
            timeout=12.0,
            verify=self.verify_ssl,
            follow_redirects=True,
            headers=self.headers,
        ) as client:
            response = await client.post(self.search_url, data={"q": query})
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
            if self._is_ad_link(raw_href, url):
                continue
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

    def _is_ad_link(self, raw_href: str, url: str) -> bool:
        markers = ("y.js", "ad_domain=", "ad_provider=", "duckduckgo.com/y")
        candidate = f"{raw_href} {url}".lower()
        return any(marker in candidate for marker in markers)

    def _strip_tags(self, value: str) -> str:
        plain = re.sub(r"<[^>]+>", "", value)
        return " ".join(html.unescape(plain).split())
