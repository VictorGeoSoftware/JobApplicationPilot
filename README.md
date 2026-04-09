# Job Application Pilot

Single-pane helper for job applications:

- Profile is prefilled from your CV/history source data.
- You only set job context (URL + optional details) on the UI.
- Motivation and cover letter are generated with Gemini.
- Reusable custom responses are saved as key + description + answer.
- New incoming form fields can be matched to saved responses (heuristic + optional Gemini assist).

## Files

- `server/index.js` API endpoints and app runtime
- `server/ai.js` Gemini generation integration
- `server/matcher.js` field-to-key matching logic
- `server/data/profile.json` prefilled candidate profile
- `server/data/customResponses.json` reusable response library
- `web/` single-pane UI

## Setup

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

## Gemini model recommendation

Default in this project:

- `gemini-1.5-flash` (good quality / low latency / lower cost)

Lighter fallback:

- `gemini-1.5-flash-8b` (cheaper and faster, but typically less nuanced output)

You can change model in `.env`:

- `GEMINI_MODEL=gemini-1.5-flash`

## API overview

- `GET /api/profile`
- `POST /api/generate-pack`
  - Body: `{ jobUrl, jobTitle?, company?, jobDescription? }`
- `GET /api/custom-responses`
- `POST /api/custom-responses`
  - Body: `{ key, description, response }`
- `DELETE /api/custom-responses/:key`
- `POST /api/match-field`
  - Body: `{ fieldName, fieldDescription? }`

## Security note

- Never commit `.env` with your API key.
- Keep generated content reviewed by you before submission.
