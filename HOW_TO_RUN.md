# How To Run — Job Application Pilot

This repository is a single **Tavily-powered FastAPI backend** plus an optional
browser extension. This document explains exactly how to run it. The most
important workflow — **the autonomous job search** — is covered first.

> TL;DR — to run a job search:
> ```bash
> cd backend
> bash backend-start.sh
> curl -s -X POST http://localhost:8000/api/jobseeker/run -H "Content-Type: application/json" -d '{}'
> open ../JobSeeker/job_search_report.html
> ```

---

## 1. What's in this repo

| Component | Path | Purpose | Runtime |
| --- | --- | --- | --- |
| **Backend** | `backend/` | FastAPI server. Powers the autonomous **JobSeeker** search and the **recruiter-answer** assistant. | Python 3.12+ |
| **Browser extension** | `extension/` | Chrome/Brave popup. Talks to the backend to answer application questions and to trigger the job search. | Chrome/Brave |
| **JobSeeker config + output** | `JobSeeker/` | Prompt + instructions for the autonomous search, and where the generated HTML report is written. | (data only) |
| **Candidate context (RAG)** | `docs/` | CV, history, cover letters. Read by the backend to ground recruiter answers. | (data only) |
| **Recruiter system prompt** | `AGENT_CONFIG.md` | Loaded by the recruiter agent (everything after the `[SYSTEM_PROMPT]` marker). | (data only) |

Everything is driven by the one backend in `backend/`. The browser extension is
optional — every feature is reachable via the HTTP API.

---

## 2. Prerequisites

- **Python 3.12+** (validated on 3.12–3.14).
- A configured `backend/.env` (already present in this checkout). It needs:
  - An LLM provider: `LLM_PROVIDER=openai` (or `claude`) plus the matching
    `AI_*` / `CLAUDE_*` credentials.
  - `TAVILY_API_KEY` — used for live web search during the job search. Without it
    the agent falls back to scraping DuckDuckGo (lower quality, may be rate-limited).

Confirm the current configuration any time with:
```bash
curl -s http://localhost:8000/api/health
# {"ok":true,"provider":"openai","model":"...","docs_dir":".../docs"}
```

---

## 3. Run a job search (primary workflow)

The JobSeeker agent runs three search tracks — **AI / Forward Deployed Engineer**,
**Defense & Military Tech**, and **Android / Kotlin Core (fallback)** — filters for
remote + Sweden/EU eligibility + permanent roles, and writes a standalone HTML
report.

### Step 1 — Start the backend

```bash
cd backend
bash backend-start.sh
```

This creates `.venv` (first run only), installs `requirements.txt`, starts the
server in the background, writes its PID to `.backend.pid`, and logs to
`.backend.log`. The server listens on `http://localhost:8000`.

### Step 2 — Trigger the search

```bash
curl -s -X POST http://localhost:8000/api/jobseeker/run \
  -H "Content-Type: application/json" -d '{}'
```

The request body is empty by design — the agent is fully autonomous and reads its
own configuration from `JobSeeker/KOOG_AGENT_PROMPT.md` and
`JobSeeker/AGENT_INSTRUCTIONS.md`. A run typically takes ~1–3 minutes (it performs
13 web-search queries, extracts full job pages, classifies them, then calls the
LLM). The JSON response includes `report_path`, `audit_path`, `generated_at`, and
`fallback_used`.

> Alternatively, click **Run Job Search** in the browser extension popup (see §5).

### Step 3 — Read the report

```bash
open JobSeeker/job_search_report.html
```

### Output artifacts (all in `JobSeeker/`)

| File | What it is |
| --- | --- |
| `job_search_report.html` | The human-readable report (open in a browser). |
| `job_search_audit.json` | Per-URL evidence: what was kept/dropped and why. |
| `job_search_last_response_raw.txt` | Raw LLM JSON for the last run. |
| `job_search_run.log` | One line per run (timestamp, fallback used, sizes). |

> `fallback_used=true` means the LLM did not return valid JSON, so the report was
> built directly from the raw search evidence. Re-run to get the full coaching
> section. Check `job_search_run.log` to confirm `fallback_used=False`.

### Stop the backend

```bash
cd backend
bash backend-stop.sh
```

This stops the process and clears `__pycache__` folders.

---

## 4. Run the recruiter-answer assistant (optional)

Same backend; a different endpoint. Given an application question (and optional
company / job URL / screenshot), it returns a strategic, STAR-structured answer
grounded in `docs/` and live web research about the company.

```bash
curl -s -X POST http://localhost:8000/api/recruiter/answer \
  -H "Content-Type: application/json" \
  -d '{
        "question": "Why do you want to work here?",
        "company_name": "Stripe",
        "job_url": "https://stripe.com/jobs/..."
      }'
```

The system prompt is loaded from `AGENT_CONFIG.md` (the text after the
`[SYSTEM_PROMPT]` marker). Every incoming question is appended to `questions.json`
to build a reusable question bank.

---

## 5. Run the browser extension (optional)

1. Make sure the backend is running (§3, Step 1).
2. Open `chrome://extensions` (or `brave://extensions`).
3. Enable **Developer mode**.
4. Click **Load unpacked** and select `extension/`.

The popup provides a chat window, question input, optional company + job URL
fields, an **Upload Screenshot** button, and a **Run Job Search** button that
triggers the workflow in §3.

---

## 6. Manual backend setup (fallback if the script fails)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # then fill in credentials
python run.py                  # runs in the foreground with auto-reload
```

Backend endpoints:
- `GET  /api/health`
- `POST /api/jobseeker/run`
- `POST /api/recruiter/answer`

---

## 7. Key environment variables (`backend/.env`)

| Variable | Purpose |
| --- | --- |
| `LLM_PROVIDER` | `openai` or `claude`. |
| `AI_BASE_URL`, `AI_API_KEY`, `AI_DEPLOYMENT`, `AI_API_VERSION` | OpenAI-compatible endpoint (used when `LLM_PROVIDER=openai`). |
| `CLAUDE_MODEL`, `CLAUDE_MAX_TOKENS`, `CLAUDE_TEMPERATURE` | Anthropic-compatible settings (used when `LLM_PROVIDER=claude`). |
| `TAVILY_API_KEY` | Live web search for the job search. |
| `WEB_SEARCH_VERIFY_SSL` | Set `false` behind TLS-inspecting proxies. |
| `SERVER_HOST`, `SERVER_PORT` | Bind address (default `0.0.0.0:8000`). |

The JobSeeker eligibility filters (exclude contract roles, require Sweden/EU
eligibility, extract caps) are configured in `backend/app/config.py`.

---

## 8. Troubleshooting

- **`port 8000 already in use`** → a backend is already running. Use the existing
  one, or `bash backend-stop.sh` then start again.
- **Search returns thin results / `fallback_used=true`** → verify `TAVILY_API_KEY`
  is set and valid; inspect `JobSeeker/job_search_audit.json` for drop reasons.
- **TLS / certificate errors on web search** → set `WEB_SEARCH_VERIFY_SSL=false`.
- **Backend won't start** → check `backend/.backend.log`.
- **Never commit secrets.** Keep real keys out of version control.
