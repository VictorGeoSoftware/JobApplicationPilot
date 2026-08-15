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

---

## Legacy: Node server + web UI (`server/`, `web/`)

Merged in from `feature/skills-for-hunting-jobs`: a single-pane helper for job
applications, superseded by the FastAPI backend above but kept for reference.

- Profile is prefilled from your CV/history source data.
- You only set job context (URL + optional details) on the UI.
- Motivation and cover letter are generated with Gemini.
- Reusable custom responses are saved as key + description + answer.
- New incoming form fields can be matched to saved responses (heuristic + optional Gemini assist).

### Files

- `server/index.js` API endpoints and app runtime
- `server/ai.js` Gemini generation integration
- `server/matcher.js` field-to-key matching logic
- `server/data/profile.json` prefilled candidate profile
- `server/data/customResponses.json` reusable response library
- `web/` single-pane UI

### Setup

1. Install dependencies:
   - `npm install`
2. Copy env template and configure:
   - `cp .env.example .env`
3. Set your Gemini API key in `.env`:
   - `GEMINI_API_KEY=YOUR_KEY`
4. Start app:
   - `npm run dev`
5. Open:
   - `http://localhost:8787`

### Gemini model recommendation

Default in this project:

- `gemini-1.5-flash` (good quality / low latency / lower cost)

Lighter fallback:

- `gemini-1.5-flash-8b` (cheaper and faster, but typically less nuanced output)

You can change model in `.env`:

- `GEMINI_MODEL=gemini-1.5-flash`

### API overview

- `GET /api/profile`
- `POST /api/generate-pack`
  - Body: `{ jobUrl, jobTitle?, company?, jobDescription? }`
- `GET /api/custom-responses`
- `POST /api/custom-responses`
  - Body: `{ key, description, response }`
- `DELETE /api/custom-responses/:key`
- `POST /api/match-field`
  - Body: `{ fieldName, fieldDescription? }`

### Security note

- Never commit `.env` with your API key.
- Keep generated content reviewed by you before submission.
