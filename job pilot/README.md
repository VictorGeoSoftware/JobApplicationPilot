# Job Pilot - Elite Technical Recruiter

This module adds a complete AI-powered job-application copilot with:

- **Backend**: Python REST agent server (`job pilot/backend`)
- **Frontend**: Chrome/Brave browser extension (`job pilot/extension`)

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

- `VOLVO_GENAI_BASE_URL`
- `VOLVO_GENAI_API_KEY`
- `VOLVO_GENAI_DEPLOYMENT` (set to your Claude 4.6 Sonnet deployment name)
- `VOLVO_GENAI_API_VERSION`

### RAG Local Context
Put your candidate context files in:
- `job pilot/docs/`

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
