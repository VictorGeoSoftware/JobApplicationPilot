# Job Application Pilot

An AI job-application copilot built around a single **Tavily-powered FastAPI
backend**. It does two things:

1. **Autonomous Job Search (JobSeeker)** — runs a live, multi-track web search
   (AI / Forward Deployed Engineer, Defense & Military Tech, Android / Kotlin),
   filters for remote + Sweden/EU + permanent roles, and writes a standalone HTML
   report with a Profile Strengthening coaching section.
2. **Recruiter-Answer assistant** — drafts strategic, STAR-structured answers to
   job-application questions, grounded in your CV/context files (`docs/`) and live
   research about the target company.

A Chrome/Brave **browser extension** is the optional UI that triggers both.

## Structure

```
.
├── backend/          FastAPI server (the core, Tavily-powered engine)
│   ├── app/          config, models, API, and services (LLM + web search + agents)
│   ├── requirements.txt
│   ├── run.py
│   ├── backend-start.sh / backend-stop.sh
│   └── .env          backend secrets & provider config (gitignored)
├── extension/        Chrome/Brave popup that calls the backend
├── JobSeeker/        search prompts + generated report
│   ├── KOOG_AGENT_PROMPT.md
│   ├── AGENT_INSTRUCTIONS.md
│   └── job_search_report.html   (generated)
├── docs/             candidate context (CV, cover letters) used for RAG
├── AGENT_CONFIG.md   recruiter system prompt ([SYSTEM_PROMPT] marker)
├── questions.json    log of incoming application questions (gitignored)
└── HOW_TO_RUN.md     full run instructions
```

## Quick start

```bash
cd backend
bash backend-start.sh
# Job search -> writes JobSeeker/job_search_report.html
curl -s -X POST http://localhost:8000/api/jobseeker/run -H "Content-Type: application/json" -d '{}'
open ../JobSeeker/job_search_report.html
```

See **[HOW_TO_RUN.md](HOW_TO_RUN.md)** for full setup, endpoints, the browser
extension, environment variables, and troubleshooting.

## Security

`backend/.env` holds live API keys and is gitignored — never commit it, and
rotate keys that have been exposed. Always review generated content before
submitting any application.
