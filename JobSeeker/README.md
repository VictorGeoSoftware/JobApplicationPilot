# JobSeeker

`JobSeeker` is a single trigger-driven autonomous job-search and career-coaching agent for Victor Palma Carrasco. It replaces the previous three separate recruiter briefs (mobile, defense, AI) with one unified agent.

## Purpose

When triggered from the `job pilot` browser extension, the agent should:

- run a live job search across three tracks,
- apply the candidate-fit, fully-remote, and geography/eligibility constraints,
- and generate a standalone HTML report in this folder including a Profile Strengthening coaching section.

## Search Tracks

- **AI-First / Forward Deployed Engineer** — FDE, Applied AI, LLM Engineer, AI Product Engineer.
- **Defense & Military Tech** — defense/armament/aerospace software, forward-deployed/field engineering, tactical/situational-awareness systems (flags clearance/citizenship).
- **Android / Kotlin Core** (fallback) — Senior/Staff Android, Kotlin/Ktor backend, KMP.

## Capabilities

- **Opportunity sourcing** — strongest recent, realistically-applicable remote roles per track.
- **Profile strengthening** — prioritized, specific actions to close gaps versus target-role requirements (e.g. hardening Python/TypeScript into independent proficiency, defense-domain credibility, FDE positioning).

## Primary Files

- `KOOG_AGENT_PROMPT.md` - master prompt for the single agent (real profile + 3 tracks + coaching)
- `AGENT_INSTRUCTIONS.md` - consolidated appended instruction set
- `job_search_report.html` - generated output file

The live engine lives in the backend at `../job pilot/backend/app/services/job_seeker_agent.py`, which reads these two files and renders the report.

## Trigger Contract

The current `job pilot` extension/backend integration triggers the workflow via a backend endpoint.

Expected behavior when the trigger is pressed:

- backend performs autonomous search workflow
- backend writes `JobSeeker/job_search_report.html`
- backend returns metadata including file path and summary

## Output Artifact

Open this file in a browser after generation:

- `JobSeeker/job_search_report.html`
