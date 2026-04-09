# Job Pilot - Elite Technical Recruiter

This module adds a complete AI-powered job-application copilot with:

- **Backend**: Python REST agent server (`job pilot/backend`)
- **Frontend**: Chrome/Brave browser extension (`job pilot/extension`)
- **Agent prompt config**: `job pilot/AGENT_CONFIG.md`

## 1) Backend Setup (Volvo GenAI + RAG + Vision + Persistence)

```bash
cd "/Users/victor/Documents/Personal/Projects/JobApplicationPilot/job pilot/backend"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

Backend endpoint:
- `POST http://localhost:8000/api/recruiter/answer`
- `GET http://localhost:8000/api/health`

### Environment Variables
Set in `job pilot/backend/.env`:

- `LLM_PROVIDER` (`openai` or `claude`)
- `AI_BASE_URL`
- `AI_API_KEY`
- `AI_DEPLOYMENT` (used when `LLM_PROVIDER=openai`)
- `AI_API_VERSION`
- `CLAUDE_MODEL` (used when `LLM_PROVIDER=claude`, default `claude-sonnet-4-5_gb_20250929`)
- `CLAUDE_MAX_TOKENS`
- `CLAUDE_TEMPERATURE`

Provider behavior:
- `openai`: calls `/azure-openai-data-inference/openai/deployments/{deployment}/chat/completions`
- `claude`: calls Anthropic-compatible `/anthropic/v1/messages`

### RAG Local Context
Put your candidate context files in:
- `job pilot/docs/`

### Agent Prompt File
The backend loads the system prompt from:
- `job pilot/AGENT_CONFIG.md`

It reads everything after the `[SYSTEM_PROMPT]` marker and sends that as the model's system prompt.
If the file or marker is missing, it falls back to an internal default prompt.

Supported: `.txt`, `.md`, `.json`, `.pdf`

### Question Persistence
Every incoming question is appended to:
- `job pilot/questions.json`

## 2) Extension Setup (Chrome/Brave)

1. Open browser extensions page (`chrome://extensions` or `brave://extensions`)
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select folder: `job pilot/extension`

The popup includes:
- Chat history window
- Question input
- Company + Job URL optional fields
- Upload Screenshot button

## API Request Example

```json
{
  "question": "Tell us about a difficult technical challenge.",
  "company_name": "Stripe",
  "job_url": "https://jobs.stripe.com/...",
  "screenshot_base64": "data:image/png;base64,...",
  "chat_history": [
    {"role": "user", "content": "Previous question"},
    {"role": "assistant", "content": "Previous answer"}
  ]
}
```
