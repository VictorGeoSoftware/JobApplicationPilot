from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json
import logging
from pathlib import Path
import re

from app.config import settings
from app.services.llm_client import LLMClient
from app.services.web_search import (
    NON_LISTING_DOMAINS,
    SearchHit,
    WebSearchService,
    classify_employment,
    classify_sweden_eligibility,
    is_non_listing_url,
    looks_like_job_description,
)


class JobSeekerAgent:
    def __init__(self, llm_client: LLMClient, web_search: WebSearchService, root_dir: Path) -> None:
        self.logger = logging.getLogger(__name__)
        self.llm_client = llm_client
        self.web_search = web_search
        self.root_dir = root_dir
        self.agent_dir = root_dir / "JobSeeker"
        self.prompt_path = self.agent_dir / "KOOG_AGENT_PROMPT.md"
        self.instructions_path = self.agent_dir / "AGENT_INSTRUCTIONS.md"
        self.output_path = self.agent_dir / "job_search_report.html"
        self.audit_path = self.agent_dir / "job_search_audit.json"
        self.raw_output_path = self.agent_dir / "job_search_last_response_raw.txt"
        self.run_log_path = self.agent_dir / "job_search_run.log"

    async def run(self, extra_prompt: str | None = None) -> dict[str, str | list[str]]:
        focus = (extra_prompt or "").strip()
        system_prompt = self._load_text(
            self.prompt_path,
            "You are JobSeeker, an autonomous elite tech recruiter agent. Return strict JSON only for backend rendering.",
        )
        instructions = self._load_text(self.instructions_path, "")
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        search_evidence, evidence_rows, audit = await self._collect_search_evidence(focus)

        focus_block = ""
        if focus:
            focus_block = (
                "OPERATOR FOCUS FOR THIS RUN (highest priority for ranking - overrides the default "
                "track weighting, but NOT the hard selection rules below):\n"
                f'"{focus}"\n'
                "Treat this as the candidate's explicit preference for this run. Surface roles matching this "
                "focus first in top_overall_matches, explain the fit in why_match, and place each match in the "
                "track section that fits best. A dedicated 'Operator Focus' evidence group was searched "
                "specifically for this. Do NOT relax the permanent-employment or Sweden/EU-eligibility hard "
                "rules for focus roles. If little or no matching evidence surfaced, say so explicitly in "
                "search_limitations instead of inventing roles.\n\n"
            )

        user_prompt = (
            "Run the autonomous job search workflow now.\n\n"
            f"{focus_block}"
            "Return strict JSON only (no markdown code fences, no prose).\n"
            "Use this exact top-level schema:\n"
            "{\n"
            '  "executive_summary": "string",\n'
            '  "top_overall_matches": [job],\n'
            '  "ai_fde_track": [job],\n'
            '  "defense_military_track": [job],\n'
            '  "android_core_track": [job],\n'
            '  "profile_strengthening": ["string"],\n'
            '  "methodology": ["string"],\n'
            '  "notable_risks": ["string"],\n'
            '  "search_limitations": ["string"]\n'
            "}\n"
            "Where each job is:\n"
            "{\n"
            '  "company": "string",\n'
            '  "company_description": "string",\n'
            '  "title": "string",\n'
            '  "role_category": "string",\n'
            '  "track": "AI-First / Forward Deployed Engineer|Defense & Military Tech|Android / Kotlin Core",\n'
            '  "work_model_location": "string",\n'
            '  "posted_date": "string",\n'
            '  "core_tech_stack": ["string"],\n'
            '  "direct_link": "string",\n'
            '  "why_match": "string",\n'
            '  "confidence": "High|Medium|Low",\n'
            '  "clearance_status": "string"\n'
            "}\n"
            "HARD SELECTION RULES (apply before ranking):\n"
            "- Exclude contractor, freelance, B2B, and hourly/temporary roles. Surface only permanent full-time employment.\n"
            "- Every surfaced role must be realistically open to a candidate based in Sweden (Sweden / EU / EEA / Europe-wide remote). "
            "Drop US-only and single-other-country-only remote roles. If eligibility cannot be confirmed from the evidence, set confidence Low and state it.\n"
            "- AI-First / Forward Deployed Engineer and Defense & Military Tech are the two PRIORITY tracks. "
            "Android / Kotlin Core is a fallback only (include at most the 1-2 strongest, and only to guarantee coverage).\n"
            "- Use the employment=, sweden_eligibility=, and posted= tags from the evidence. Do not contradict them or invent posting dates.\n"
            "profile_strengthening must contain 3-6 specific, prioritized actions that close the gap "
            "between the candidate's evidence and the recurring requirements seen in the live results "
            "(especially defense/FDE/AI-First), including hardening Python and TypeScript into independent proficiency.\n"
            "If evidence is insufficient, keep fields explicit and add limitations rather than inventing facts.\n\n"
            f"Generation timestamp: {timestamp}\n\n"
            f"Live web-search evidence (must be used and cited in the report):\n{search_evidence}\n\n"
            "Appended agent instructions:\n"
            f"{instructions}"
        )

        raw_response = await self.llm_client.generate_answer(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            screenshot_base64=None,
        )

        parsed_payload, parse_reason = self._parse_llm_payload(raw_response)
        fallback_used = parsed_payload is None
        structured_payload = (
            parsed_payload
            if parsed_payload is not None
            else self._build_fallback_structured_payload(timestamp=timestamp, evidence_rows=evidence_rows, raw_response=raw_response)
        )

        # Deterministic per-URL classification index (kept evidence) for report badges.
        evidence_index = {
            self._normalize_url(str(row["url"])): row
            for row in evidence_rows
            if row.get("url")
        }

        html = self._render_structured_report(
            timestamp=timestamp,
            payload=structured_payload,
            evidence_index=evidence_index,
            focus=focus,
        )
        if fallback_used:
            self.logger.warning("JobSeeker fallback payload used. reason=%s", parse_reason)

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(html, encoding="utf-8")
        self.raw_output_path.write_text(raw_response, encoding="utf-8")
        self._write_audit(timestamp=timestamp, audit=audit, fallback_used=fallback_used, parse_reason=parse_reason)
        self._append_run_log(
            timestamp,
            raw_response=raw_response,
            final_html=html,
            fallback_used=fallback_used,
            reason=parse_reason,
            focus=focus,
        )
        self.logger.info("JobSeeker run completed. fallback_used=%s output=%s", fallback_used, self.output_path)

        return {
            "report_path": str(self.output_path),
            "audit_path": str(self.audit_path),
            "generated_at": timestamp,
            "prompt_files": [str(self.prompt_path), str(self.instructions_path)],
            "fallback_used": fallback_used,
            "agent_response_preview": self._build_response_preview(raw_response),
            "applied_focus": focus or None,
        }

    async def _collect_search_evidence(self, focus: str = "") -> tuple[str, list[dict[str, str]], dict]:
        base_queries = self._build_query_set()
        focus_track = ""
        focus_queries: list[tuple[str, str, str, list[str] | None]] = []
        if focus:
            focus_track, focus_queries = await self._build_focus_queries(focus)
        # Focus queries go first so the Operator Focus track owns any URL that also
        # surfaces under a default track (dedupe is first-track-wins).
        queries = focus_queries + base_queries

        # 1) Collect recency-bounded hits per query (Tavily advanced + raw content).
        #    ATS/careers domains are biased in per-query via include_domains; known
        #    non-listing sources (social, forums, repos, blogs) are excluded at the
        #    source so the noise never costs us credits.
        collected: list[tuple[str, str, SearchHit]] = []
        search_errors: list[str] = []
        for track, role, query, include_domains in queries:
            try:
                hits = await self.web_search.search(
                    query,
                    limit=settings.tavily_max_results,
                    include_raw_content=True,
                    include_domains=include_domains,
                    exclude_domains=list(NON_LISTING_DOMAINS),
                )
            except Exception as error:
                search_errors.append(f"[{track} | {role}] search failed: {error}")
                continue
            for hit in hits:
                collected.append((track, role, hit))

        # 2) Dedupe by URL; the first (highest-priority) track to surface a URL owns
        #    it. Drop known non-listing sources that slipped past exclude_domains
        #    (e.g. blog/category/sitemap paths on otherwise-valid hosts).
        unique: dict[str, tuple[str, str, SearchHit]] = {}
        dropped_non_listing_rows: list[dict[str, str]] = []
        dropped_non_listing = 0
        for track, role, hit in collected:
            if not hit.url or hit.url in unique:
                continue
            if is_non_listing_url(hit.url):
                dropped_non_listing += 1
                dropped_non_listing_rows.append(
                    self._evidence_row(
                        track,
                        role,
                        hit,
                        "Non-listing source (social/forum/repo/blog/aggregator index).",
                        drop_reason="non-listing-source",
                    )
                )
                continue
            unique[hit.url] = (track, role, hit)

        # 3) Enrich candidates that don't yet read like a real job description with
        #    full-page text via Tavily Extract. Long aggregator/nav-heavy pages have
        #    plenty of characters but few JD structural markers, so a length check
        #    alone (the old <400 trigger) almost never fired.
        needs_extract = [
            url
            for url, (_, _, hit) in unique.items()
            if not looks_like_job_description(hit.raw_content)
        ][: settings.job_search_max_extracts]
        extracted = await self.web_search.extract(needs_extract)

        # 4) Classify employment + Sweden eligibility, then apply hard filters.
        kept: list[tuple[str, str, SearchHit, str]] = []
        dropped_rows: list[dict[str, str]] = list(dropped_non_listing_rows)
        dropped_contract = 0
        dropped_eligibility = 0
        for url, (track, role, hit) in unique.items():
            body = extracted.get(url) or hit.raw_content or hit.snippet
            hit.raw_content = body[:1800]
            hit.employment_type = classify_employment(hit.title, body)
            status, note = classify_sweden_eligibility(body)
            hit.sweden_eligibility = status

            if settings.job_search_exclude_contract and hit.employment_type == "contract":
                dropped_contract += 1
                dropped_rows.append(self._evidence_row(track, role, hit, note, drop_reason="contract"))
                continue
            if settings.job_search_require_sweden_eligibility and status == "blocked":
                dropped_eligibility += 1
                dropped_rows.append(self._evidence_row(track, role, hit, note, drop_reason="not-sweden-eligible"))
                continue
            kept.append((track, role, hit, note))

        # 5) Group surviving evidence by track for the prompt + fallback rows.
        by_track: dict[str, list[tuple[str, SearchHit]]] = {}
        evidence_rows: list[dict[str, str]] = []
        for track, role, hit, note in kept:
            by_track.setdefault(track, []).append((role, hit))
            evidence_rows.append(self._evidence_row(track, role, hit, note))

        sections: list[str] = []
        section_tracks: list[str] = []
        if focus_track:
            section_tracks.append(focus_track)
        section_tracks += [
            "AI-First / Forward Deployed Engineer",
            "Defense & Military Tech",
            "Android / Kotlin Core",
        ]
        for track in section_tracks:
            sections.append(self._format_track(track, by_track.get(track, [])))

        summary_counts = {
            "queries_run": len(queries),
            "raw_hits": len(collected),
            "unique_urls": len(unique),
            "dropped_non_listing": dropped_non_listing,
            "pages_extracted": len(extracted),
            "kept": len(kept),
            "dropped_contract": dropped_contract,
            "dropped_not_sweden_eligible": dropped_eligibility,
        }
        summary = (
            "[Filtering summary] "
            f"raw_hits={summary_counts['raw_hits']} unique={summary_counts['unique_urls']} "
            f"dropped_non_listing={dropped_non_listing} "
            f"kept={summary_counts['kept']} dropped_contract={dropped_contract} "
            f"dropped_not_sweden_eligible={dropped_eligibility} pages_extracted={len(extracted)}"
        )
        if search_errors:
            summary += "\nSearch errors:\n- " + "\n- ".join(search_errors)
        sections.append(summary)

        audit = {
            "summary": summary_counts,
            "kept": evidence_rows,
            "dropped": dropped_rows,
            "search_errors": search_errors,
        }
        return "\n\n".join(sections), evidence_rows, audit

    @staticmethod
    def _ats_domains() -> list[str]:
        return [
            "boards.greenhouse.io",
            "greenhouse.io",
            "jobs.lever.co",
            "lever.co",
            "jobs.ashbyhq.com",
            "ashbyhq.com",
            "myworkdayjobs.com",
            "smartrecruiters.com",
            "teamtailor.com",
            "join.com",
            "workable.com",
            "recruitee.com",
        ]

    async def _build_focus_queries(
        self, focus: str
    ) -> tuple[str, list[tuple[str, str, str, list[str] | None]]]:
        """Turn a free-text operator focus into a few targeted search queries.

        Primary path asks the LLM to expand the focus into concise keyword queries
        (robust to natural-language phrasing). Any failure degrades to a deterministic
        keyword fallback so the focus always produces at least one query.
        """
        eu = "remote Europe Sweden EU eligible full-time permanent not contract not freelance"
        label = "Operator Focus"
        queries: list[str] = []
        try:
            raw = await self.llm_client.generate_answer(
                system_prompt=(
                    "You convert a job seeker's free-text focus into concise web-search queries for "
                    "finding live job postings. Return STRICT JSON only - no prose, no code fences."
                ),
                user_prompt=(
                    f"Operator focus:\n{focus}\n\n"
                    'Return strict JSON exactly: {"label": "<2-4 word focus label>", '
                    '"queries": ["query1", "query2", "query3"]}\n'
                    "Rules: 2-4 queries; each is concise keywords (role titles + domain/tech terms) "
                    "suitable for a job-board search; do NOT add country/remote/eligibility words "
                    "(they are appended automatically); no duplicates."
                ),
                screenshot_base64=None,
            )
            data = self._loads_json_object(raw)
            if isinstance(data, dict):
                label = (str(data.get("label") or "").strip() or "Operator Focus")[:48]
                queries = [str(q).strip() for q in (data.get("queries") or []) if str(q).strip()][:4]
        except Exception as error:  # pragma: no cover - defensive: network/model issues
            self.logger.warning("Focus query expansion failed; using naive fallback: %s", error)

        if not queries:
            label, queries = self._naive_focus_queries(focus)

        track = f"Operator Focus: {label}"
        ats = self._ats_domains()
        out: list[tuple[str, str, str, list[str] | None]] = []
        for index, query in enumerate(queries):
            # Alternate broad and ATS-locked queries: breadth + high-signal listings.
            include = ats if index % 2 == 1 else None
            out.append((track, label, f"{query} {eu}", include))
        return track, out

    @staticmethod
    def _loads_json_object(raw: str) -> dict | None:
        text = (raw or "").strip()
        fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                return None
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None

    @staticmethod
    def _naive_focus_queries(focus: str) -> tuple[str, list[str]]:
        stop = {
            "hey", "hi", "hello", "im", "ive", "id", "ill", "quite", "into", "so", "like",
            "to", "find", "finding", "something", "in", "where", "can", "could", "you",
            "help", "me", "with", "that", "this", "a", "an", "the", "of", "for", "and",
            "or", "looking", "look", "want", "wanna", "would", "get", "role", "roles",
            "job", "jobs", "work", "working", "my", "am", "really", "very", "keen",
            "interested", "on", "prefer", "please", "thanks", "thank", "develop",
            "developing", "build", "building", "make", "making", "im,", "love", "loving",
        }
        words = re.findall(r"[a-zA-Z][a-zA-Z+#.]+", focus.lower())
        keywords: list[str] = []
        seen: set[str] = set()
        for word in words:
            if word in stop or word in seen:
                continue
            seen.add(word)
            keywords.append(word)
        keywords = keywords[:5]
        if not keywords:
            core = focus.strip()[:80] or "software engineer"
            return "Operator Focus", [f"{core} software engineer"]
        core = " ".join(keywords)
        label = " ".join(keywords[:3]).title()
        return label, [
            f"{core} software engineer",
            f"{core} developer engineer",
        ]

    def _build_query_set(self) -> list[tuple[str, str, str, list[str] | None]]:
        ai = "AI-First / Forward Deployed Engineer"
        defense = "Defense & Military Tech"
        android = "Android / Kotlin Core"
        # Eligibility + employment hints baked into every query.
        eu = "remote Europe Sweden EU eligible full-time permanent not contract not freelance"
        # Applicant-tracking systems that host real, applyable listings. Locking a
        # query to these (Tavily include_domains) trades breadth for a much higher
        # share of genuine job pages over blog/aggregator noise.
        ats = self._ats_domains()
        # Defense primes / well-known defense-tech employers' own careers domains.
        defense_careers = [
            "saab.com",
            "mildef.com",
            "helsing.ai",
            "anduril.com",
            "combitech.com",
            "quantum-systems.com",
        ]
        # (track, role, query, include_domains | None)
        return [
            # --- Track A: AI-First / Forward Deployed Engineer (PRIMARY) ---
            (ai, "Forward Deployed Engineer", f"Forward Deployed Engineer LLM AI agents customer-facing {eu}", None),
            (ai, "Forward Deployed Engineer (ATS)", "Forward Deployed Engineer OR Applied AI Engineer LLM agents permanent remote Europe", ats),
            (ai, "Applied AI Engineer", f"Applied AI Engineer RAG MCP LLM integration production {eu}", None),
            (ai, "AI Solutions / Customer Engineer", f"AI Solutions Engineer OR AI Customer Engineer GenAI product {eu}", None),
            (ai, "LLM / Generative AI Engineer (ATS)", "LLM Engineer OR Generative AI Engineer agentic AI orchestration permanent remote Europe", ats),
            (ai, "AI Solutions Architect", f"AI Solutions Architect LLM platform enterprise integration {eu}", None),
            # --- Track B: Defense & Military Tech (PRIMARY) ---
            (defense, "Defense Software Engineer", f"defense military software engineer backend full-stack {eu}", None),
            (defense, "Defense Primes (careers)", "software engineer OR forward deployed engineer OR autonomy engineer", defense_careers),
            (defense, "C2 / ISR / Situational Awareness", f"command control ISR situational awareness tactical software engineer defense {eu}", None),
            (defense, "Autonomy / Edge Defense Software", f"autonomy robotics edge software engineer defense drones aerospace {eu}", None),
            (defense, "AI for Defense (ATS)", "AI OR machine learning engineer defense tech permanent remote Europe", ats),
            (defense, "Nordic Defense Primes", f"Saab MilDef Combitech FMV defense software engineer Sweden {eu}", None),
            # --- Track C: Android / Kotlin Core (FALLBACK only) ---
            (android, "Senior / Staff Android (Kotlin/KMP)", f"Senior Staff Android Engineer Kotlin Jetpack Compose KMP {eu}", None),
        ]

    def _format_track(self, track: str, rows: list[tuple[str, SearchHit]]) -> str:
        header = f"=== {track} (kept: {len(rows)}) ==="
        if not rows:
            return f"{header}\n- No qualifying (non-contract, Sweden-eligible) results."

        lines = [header]
        for role, hit in rows:
            date = hit.published_date or "date n/a"
            evidence = (hit.raw_content or hit.snippet or "No snippet").strip()
            lines.append(
                f"- [{role}] {hit.title} | {hit.url}\n"
                f"  employment={hit.employment_type} sweden_eligibility={hit.sweden_eligibility} posted={date}\n"
                f"  evidence: {evidence[:600]}"
            )
        return "\n".join(lines)

    def _evidence_row(
        self,
        track: str,
        role: str,
        hit: SearchHit,
        note: str,
        drop_reason: str | None = None,
    ) -> dict[str, str]:
        row = {
            "track": track,
            "role": role,
            "title": hit.title,
            "url": hit.url,
            "snippet": hit.snippet or "No snippet provided",
            "employment_type": hit.employment_type,
            "sweden_eligibility": hit.sweden_eligibility,
            "eligibility_note": note,
            "posted_date": hit.published_date or "Not specified",
        }
        if drop_reason:
            row["drop_reason"] = drop_reason
        return row

    @staticmethod
    def _normalize_url(url: str) -> str:
        return url.strip().rstrip("/").lower()

    @staticmethod
    def _is_fresh(date_str: str) -> bool:
        """Heuristic: treat a posting as 'fresh' when it is <= 2 days old."""
        text = (date_str or "").lower()
        if any(token in text for token in ("hour", "minute", "today", "just posted")):
            return True
        if "yesterday" in text or "1 day" in text:
            return True
        match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
        if match:
            try:
                posted = datetime(
                    int(match.group(1)), int(match.group(2)), int(match.group(3)), tzinfo=timezone.utc
                )
            except ValueError:
                return False
            return 0 <= (datetime.now(timezone.utc) - posted).days <= 2
        return False

    def _write_audit(self, timestamp: str, audit: dict, fallback_used: bool, parse_reason: str) -> None:
        try:
            payload = {
                "generated_at": timestamp,
                "fallback_used": fallback_used,
                "parse_reason": parse_reason,
                **audit,
            }
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            self.audit_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as error:  # pragma: no cover - defensive I/O guard
            self.logger.warning("Could not write JobSeeker audit JSON: %s", error)

    def _load_text(self, path: Path, fallback: str) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return fallback

    def _parse_llm_payload(self, raw_response: str) -> tuple[dict | None, str]:
        text = raw_response.strip()
        if not text:
            return None, "empty_model_response"

        fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            return None, f"json_decode_error:{error.msg}"

        if not isinstance(payload, dict):
            return None, "json_root_not_object"

        return self._normalize_payload(payload), "json_parsed"

    def _normalize_payload(self, payload: dict) -> dict:
        return {
            "executive_summary": str(payload.get("executive_summary") or "No summary provided."),
            "top_overall_matches": self._normalize_jobs(payload.get("top_overall_matches"), "Top Overall Matches"),
            "ai_fde_track": self._normalize_jobs(payload.get("ai_fde_track"), "AI-First / Forward Deployed Engineer"),
            "defense_military_track": self._normalize_jobs(payload.get("defense_military_track"), "Defense & Military Tech"),
            "android_core_track": self._normalize_jobs(payload.get("android_core_track"), "Android / Kotlin Core"),
            "profile_strengthening": self._normalize_string_list(payload.get("profile_strengthening"), "No strengthening actions provided."),
            "methodology": self._normalize_string_list(payload.get("methodology"), "Methodology unavailable."),
            "notable_risks": self._normalize_string_list(payload.get("notable_risks"), "No risks listed."),
            "search_limitations": self._normalize_string_list(payload.get("search_limitations"), "No limitations listed."),
        }

    def _normalize_jobs(self, value: object, default_track: str) -> list[dict[str, str | list[str]]]:
        if not isinstance(value, list):
            return []

        jobs: list[dict[str, str | list[str]]] = []
        for item in value:
            if not isinstance(item, dict):
                continue

            stack = item.get("core_tech_stack")
            jobs.append(
                {
                    "company": str(item.get("company") or "Unknown company"),
                    "company_description": str(item.get("company_description") or "No company description provided."),
                    "title": str(item.get("title") or "Unknown title"),
                    "role_category": str(item.get("role_category") or "Unknown role category"),
                    "track": str(item.get("track") or default_track),
                    "work_model_location": str(item.get("work_model_location") or "Not specified"),
                    "posted_date": str(item.get("posted_date") or "Not specified"),
                    "core_tech_stack": self._normalize_string_list(stack, "Not specified"),
                    "direct_link": str(item.get("direct_link") or ""),
                    "why_match": str(item.get("why_match") or "No match rationale provided."),
                    "confidence": str(item.get("confidence") or "Medium"),
                    "clearance_status": str(item.get("clearance_status") or "Not specified"),
                }
            )
        return jobs

    def _normalize_string_list(self, value: object, fallback_value: str) -> list[str]:
        if isinstance(value, list):
            result = [str(item).strip() for item in value if str(item).strip()]
            if result:
                return result
        return [fallback_value]

    def _build_response_preview(self, raw_html: str) -> str:
        snippet = " ".join(raw_html.strip().split())
        if len(snippet) <= 280:
            return snippet
        return f"{snippet[:277]}..."

    def _build_fallback_structured_payload(self, timestamp: str, evidence_rows: list[dict[str, str]], raw_response: str) -> dict:
        grouped: dict[str, list[dict[str, str | list[str]]]] = {
            "ai_fde_track": [],
            "defense_military_track": [],
            "android_core_track": [],
        }

        for row in evidence_rows:
            if "Defense" in row["track"]:
                track_key = "defense_military_track"
            elif "Android" in row["track"]:
                track_key = "android_core_track"
            else:
                track_key = "ai_fde_track"
            grouped[track_key].append(
                {
                    "company": row["title"],
                    "company_description": row["snippet"],
                    "title": row["title"],
                    "role_category": row["role"],
                    "track": row["track"],
                    "work_model_location": (
                        f"Sweden eligibility: {row.get('sweden_eligibility', 'unknown')}; "
                        f"employment: {row.get('employment_type', 'unknown')}"
                    ),
                    "posted_date": row.get("posted_date") or "Not specified",
                    "core_tech_stack": ["Not specified"],
                    "direct_link": row["url"],
                    "why_match": "Derived from live search evidence due to JSON parse fallback.",
                    "confidence": "Medium",
                    "clearance_status": "Check source listing",
                }
            )

        top_matches = (grouped["ai_fde_track"] + grouped["defense_military_track"] + grouped["android_core_track"])[:6]
        return {
            "executive_summary": (
                "Fallback mode: The model did not return valid JSON, so this report is built directly from live web-search evidence. "
                f"Generated at {timestamp}."
            ),
            "top_overall_matches": top_matches,
            "ai_fde_track": grouped["ai_fde_track"],
            "defense_military_track": grouped["defense_military_track"],
            "android_core_track": grouped["android_core_track"],
            "profile_strengthening": [
                "Fallback mode: skill-gap coaching unavailable because the model did not return valid JSON.",
                "Re-run the agent to generate prioritized Profile Strengthening actions.",
            ],
            "methodology": [
                "Collected evidence from the predefined query set for AI/FDE, defense, and Android tracks.",
                "Rendered deterministic HTML from normalized payload structure.",
            ],
            "notable_risks": [
                "Model JSON output was invalid and required deterministic fallback.",
            ],
            "search_limitations": [
                "Role details may be incomplete where source snippets lacked metadata.",
                f"Model response preview: {self._build_response_preview(raw_response)}",
            ],
        }

    def _render_structured_report(self, timestamp: str, payload: dict, evidence_index: dict[str, dict] | None = None, focus: str = "") -> str:
        evidence_index = evidence_index or {}

        def render_badges(job: dict[str, str | list[str]]) -> str:
            evidence = evidence_index.get(self._normalize_url(str(job.get("direct_link", ""))))
            verified = evidence is not None
            employment = str((evidence or {}).get("employment_type") or "").lower()
            eligibility = str((evidence or {}).get("sweden_eligibility") or "").lower()
            posted = str((evidence or {}).get("posted_date") or job.get("posted_date") or "").strip()

            chips: list[tuple[str, str]] = []
            # Employment type
            if employment == "permanent":
                chips.append(("badge-ok", "Permanent"))
            elif employment == "contract":
                chips.append(("badge-bad", "Contract"))
            else:
                chips.append(("badge-muted", "Employment: unverified" if verified else "Employment: per listing"))
            # Sweden eligibility
            if eligibility == "eligible":
                chips.append(("badge-ok", "Sweden-eligible"))
            elif eligibility == "restricted":
                chips.append(("badge-warn", "Eligibility: restricted"))
            elif eligibility == "blocked":
                chips.append(("badge-bad", "Not Sweden-eligible"))
            else:
                chips.append(("badge-muted", "Eligibility: unverified" if verified else "Eligibility: per listing"))
            # Recency
            if posted and posted.lower() not in ("not specified", "n/a"):
                if self._is_fresh(posted):
                    chips.append(("badge-ok", f"Fresh \u00b7 {posted}"))
                else:
                    chips.append(("badge-muted", f"Posted {posted}"))
            # Provenance of the badges themselves
            chips.append(("badge-ok", "Evidence-verified") if verified else ("badge-muted", "Model-surfaced"))

            spans = "".join(f'<span class="badge {cls}">{escape(text)}</span>' for cls, text in chips)
            return f'<div class="badges">{spans}</div>'

        def render_jobs(items: list[dict[str, str | list[str]]], show_clearance: bool) -> str:
            if not items:
                return "<p>No matches found.</p>"

            parts: list[str] = []
            for job in items:
                stack = ", ".join(str(x) for x in job.get("core_tech_stack", []))
                link = str(job.get("direct_link", "")).strip()
                link_html = (
                    f'<a href="{escape(link)}" target="_blank" rel="noopener noreferrer">Open listing</a>'
                    if link
                    else "No link provided"
                )
                clearance_html = ""
                if show_clearance:
                    clearance_html = (
                        "<p><strong>Clearance / Citizenship:</strong> "
                        f"{escape(str(job.get('clearance_status', 'Not specified')))}</p>"
                    )

                parts.append(
                    "<article class=\"job\">"
                    f"<h4>{escape(str(job.get('title', 'Unknown title')))}</h4>"
                    f"{render_badges(job)}"
                    f"<p><strong>Company:</strong> {escape(str(job.get('company', 'Unknown company')))}</p>"
                    f"<p><strong>Company Description:</strong> {escape(str(job.get('company_description', 'N/A')))}</p>"
                    f"<p><strong>Role Category:</strong> {escape(str(job.get('role_category', 'N/A')))}</p>"
                    f"<p><strong>Work Model/Location:</strong> {escape(str(job.get('work_model_location', 'N/A')))}</p>"
                    f"<p><strong>Posted Date:</strong> {escape(str(job.get('posted_date', 'N/A')))}</p>"
                    f"<p><strong>Core Tech Stack:</strong> {escape(stack or 'N/A')}</p>"
                    f"<p><strong>Why Match:</strong> {escape(str(job.get('why_match', 'N/A')))}</p>"
                    f"<p><strong>Confidence:</strong> {escape(str(job.get('confidence', 'Medium')))}</p>"
                    f"<p><strong>Link:</strong> {link_html}</p>"
                    f"{clearance_html}"
                    "</article>"
                )
            return "".join(parts)

        def render_list(title: str, items: list[str]) -> str:
            safe_items = "".join(f"<li>{escape(item)}</li>" for item in items)
            return f"<section><h3>{escape(title)}</h3><ul>{safe_items}</ul></section>"

        summary = escape(str(payload.get("executive_summary") or "No summary provided."))
        top_matches = payload.get("top_overall_matches") if isinstance(payload.get("top_overall_matches"), list) else []
        ai_fde = payload.get("ai_fde_track") if isinstance(payload.get("ai_fde_track"), list) else []
        defense = payload.get("defense_military_track") if isinstance(payload.get("defense_military_track"), list) else []
        android_core = payload.get("android_core_track") if isinstance(payload.get("android_core_track"), list) else []
        profile_strengthening = self._normalize_string_list(payload.get("profile_strengthening"), "No strengthening actions provided.")
        methodology = self._normalize_string_list(payload.get("methodology"), "Methodology unavailable.")
        risks = self._normalize_string_list(payload.get("notable_risks"), "No risks listed.")
        limitations = self._normalize_string_list(payload.get("search_limitations"), "No limitations listed.")

        return (
            "<!doctype html>\n"
            '<html lang="en">\n'
            "  <head>\n"
            '    <meta charset="UTF-8" />\n'
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
            "    <title>JobSeeker Report</title>\n"
            "    <style>body{font-family:Arial,sans-serif;margin:28px;line-height:1.45;color:#0f172a;background:#f8fafc;}"
            "main{max-width:1050px;margin:0 auto;background:#fff;padding:20px;border-radius:12px;border:1px solid #e2e8f0;}"
            "h1{margin-bottom:4px;}h2{margin-top:22px;margin-bottom:10px;}h3{margin:12px 0 8px;}"
            ".meta{color:#475569;font-size:14px;margin-bottom:14px;}"
            ".job{border:1px solid #e2e8f0;border-radius:10px;padding:12px;margin:10px 0;background:#fdfefe;}"
            ".badges{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 10px;}"
            ".badge{font-size:12px;font-weight:600;padding:2px 9px;border-radius:999px;border:1px solid transparent;white-space:nowrap;}"
            ".badge-ok{background:#dcfce7;color:#166534;border-color:#bbf7d0;}"
            ".badge-warn{background:#fef9c3;color:#854d0e;border-color:#fde68a;}"
            ".badge-bad{background:#fee2e2;color:#991b1b;border-color:#fecaca;}"
            ".badge-muted{background:#f1f5f9;color:#475569;border-color:#e2e8f0;}"
            "ul{padding-left:22px;}li{margin:6px 0;}a{color:#0b63ce;}p{margin:6px 0;}"
            "</style>\n"
            "  </head>\n"
            "  <body>\n"
            "    <main>\n"
            "      <h1>JobSeeker Report</h1>\n"
            f"      <p class=\"meta\">Generated at {escape(timestamp)}</p>\n"
            + (f"      <p class=\"meta\"><strong>Operator focus:</strong> {escape(focus)}</p>\n" if focus else "")
            + "      <section>\n"
            "        <h2>Executive Summary</h2>\n"
            f"        <p>{summary}</p>\n"
            "      </section>\n"
            "      <section>\n"
            "        <h2>Top Overall Matches</h2>\n"
            f"        {render_jobs(top_matches, show_clearance=True)}\n"
            "      </section>\n"
            "      <section>\n"
            "        <h2>AI-First / Forward Deployed Engineer</h2>\n"
            f"        {render_jobs(ai_fde, show_clearance=False)}\n"
            "      </section>\n"
            "      <section>\n"
            "        <h2>Defense & Military Tech</h2>\n"
            f"        {render_jobs(defense, show_clearance=True)}\n"
            "      </section>\n"
            "      <section>\n"
            "        <h2>Android / Kotlin Core</h2>\n"
            f"        {render_jobs(android_core, show_clearance=False)}\n"
            "      </section>\n"
            f"      {render_list('Profile Strengthening', profile_strengthening)}\n"
            f"      {render_list('Methodology', methodology)}\n"
            f"      {render_list('Notable Risks / Caveats', risks)}\n"
            f"      {render_list('Search Limitations', limitations)}\n"
            "    </main>\n"
            "  </body>\n"
            "</html>\n"
        )

    def _append_run_log(self, timestamp: str, raw_response: str, final_html: str, fallback_used: bool, reason: str, focus: str = "") -> None:
        try:
            final_trimmed = final_html.strip().lower()
            focus_note = f" focus={focus[:80]!r}" if focus else ""
            line = (
                f"[{timestamp}] fallback_used={fallback_used} "
                f"reason={reason} raw_chars={len(raw_response)} final_chars={len(final_html)} "
                f"final_has_close_html={'</html>' in final_trimmed}{focus_note}\n"
            )
            with self.run_log_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception as error:
            self.logger.warning("Could not append JobSeeker run log: %s", error)
