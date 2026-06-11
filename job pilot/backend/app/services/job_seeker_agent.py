from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json
import logging
from pathlib import Path
import re

from app.services.llm_client import LLMClient
from app.services.web_search import SearchHit, WebSearchService


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
        self.raw_output_path = self.agent_dir / "job_search_last_response_raw.txt"
        self.run_log_path = self.agent_dir / "job_search_run.log"

    async def run(self) -> dict[str, str | list[str]]:
        system_prompt = self._load_text(
            self.prompt_path,
            "You are JobSeeker, an autonomous elite tech recruiter agent. Return strict JSON only for backend rendering.",
        )
        instructions = self._load_text(self.instructions_path, "")
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        search_evidence, evidence_rows = await self._collect_search_evidence()

        user_prompt = (
            "Run the autonomous job search workflow now.\n\n"
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

        html = self._render_structured_report(timestamp=timestamp, payload=structured_payload)
        if fallback_used:
            self.logger.warning("JobSeeker fallback payload used. reason=%s", parse_reason)

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(html, encoding="utf-8")
        self.raw_output_path.write_text(raw_response, encoding="utf-8")
        self._append_run_log(
            timestamp,
            raw_response=raw_response,
            final_html=html,
            fallback_used=fallback_used,
            reason=parse_reason,
        )
        self.logger.info("JobSeeker run completed. fallback_used=%s output=%s", fallback_used, self.output_path)

        return {
            "report_path": str(self.output_path),
            "generated_at": timestamp,
            "prompt_files": [str(self.prompt_path), str(self.instructions_path)],
            "fallback_used": fallback_used,
            "agent_response_preview": self._build_response_preview(raw_response),
        }

    async def _collect_search_evidence(self) -> tuple[str, list[dict[str, str]]]:
        queries = [
            (
                "AI-First / Forward Deployed Engineer",
                "Forward Deployed Engineer",
                "Forward Deployed Engineer remote Europe LLM AI agents customer-facing jobs posted 2 days",
            ),
            (
                "AI-First / Forward Deployed Engineer",
                "Applied AI Engineer",
                "Applied AI Engineer remote EU LLM RAG MCP integration jobs posted 2 days",
            ),
            (
                "AI-First / Forward Deployed Engineer",
                "AI Product / LLM Engineer",
                "LLM Engineer AI Product Engineer remote Europe TypeScript Python jobs posted 2 days",
            ),
            (
                "Defense & Military Tech",
                "Defense Software Engineer",
                "Defense military software engineer Kotlin backend remote Europe Sweden jobs posted 2 days",
            ),
            (
                "Defense & Military Tech",
                "Defense Forward Deployed / Field Engineer",
                "Defense tech forward deployed field engineer Saab Helsing MilDef Anduril EU jobs posted 2 days",
            ),
            (
                "Defense & Military Tech",
                "Tactical / Situational-Awareness Engineer",
                "Defense AI situational awareness tactical software engineer Sweden EU remote jobs posted 2 days",
            ),
            (
                "Android / Kotlin Core",
                "Senior / Staff Android Engineer",
                "Senior Android Engineer Kotlin Jetpack Compose remote Europe jobs posted 2 days",
            ),
            (
                "Android / Kotlin Core",
                "Kotlin Backend / KMP Engineer",
                "Kotlin Ktor backend Kotlin Multiplatform engineer remote EU jobs posted 2 days",
            ),
        ]

        sections: list[str] = []
        evidence_rows: list[dict[str, str]] = []
        for track, role, query in queries:
            try:
                hits = await self.web_search.search(query, limit=5)
            except Exception as error:
                sections.append(
                    f"[{track} | {role}] query='{query}'\\n- Search failed: {error}"
                )
                evidence_rows.append(
                    {
                        "track": track,
                        "role": role,
                        "title": "Search failed",
                        "url": "",
                        "snippet": str(error),
                    }
                )
                continue

            sections.append(self._format_hits(track=track, role=role, query=query, hits=hits))
            for hit in hits:
                evidence_rows.append(
                    {
                        "track": track,
                        "role": role,
                        "title": hit.title,
                        "url": hit.url,
                        "snippet": hit.snippet or "No snippet provided",
                    }
                )

        return "\n\n".join(sections), evidence_rows

    def _format_hits(self, track: str, role: str, query: str, hits: list[SearchHit]) -> str:
        header = f"[{track} | {role}] query='{query}'"
        if not hits:
            return f"{header}\\n- No results"

        lines = [header]
        for hit in hits:
            snippet = hit.snippet or "No snippet provided"
            lines.append(f"- {hit.title} | {hit.url} | {snippet}")
        return "\n".join(lines)

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
                    "work_model_location": "See source listing",
                    "posted_date": "Not specified",
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

    def _render_structured_report(self, timestamp: str, payload: dict) -> str:
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
            "ul{padding-left:22px;}li{margin:6px 0;}a{color:#0b63ce;}p{margin:6px 0;}"
            "</style>\n"
            "  </head>\n"
            "  <body>\n"
            "    <main>\n"
            "      <h1>JobSeeker Report</h1>\n"
            f"      <p class=\"meta\">Generated at {escape(timestamp)}</p>\n"
            "      <section>\n"
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

    def _append_run_log(self, timestamp: str, raw_response: str, final_html: str, fallback_used: bool, reason: str) -> None:
        try:
            final_trimmed = final_html.strip().lower()
            line = (
                f"[{timestamp}] fallback_used={fallback_used} "
                f"reason={reason} raw_chars={len(raw_response)} final_chars={len(final_html)} "
                f"final_has_close_html={'</html>' in final_trimmed}\n"
            )
            with self.run_log_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception as error:
            self.logger.warning("Could not append JobSeeker run log: %s", error)
