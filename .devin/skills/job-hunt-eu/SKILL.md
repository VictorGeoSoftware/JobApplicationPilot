---
name: job-hunt-eu
description: Find EU-remote-friendly senior engineering job offers (LinkedIn + open job boards) via Tavily, matched against the candidate profile. Maintains docs/job-shortlist.md.
argument-hint: "[role focus, e.g. \"Senior AI Engineer\"]"
allowed-tools:
  - read
  - exec
  - edit
  - grep
---

# Job Hunt EU

Find job offers that Victor can apply to **while living in Sweden** — i.e. companies (ideally UK, Germany, or Nordics-based) that explicitly hire remotely from anywhere in the EU/Europe/EMEA.

## Setup

1. Read `TAVILY_API_KEY` from the project `.env`. **Never print or commit the key** — pass it via shell env (`source .env`).
2. Read the candidate profile at `server/data/profile.json` and use it to judge fit (10+ yrs, Android/Kotlin, Node.js/TypeScript, Solidity, AI-augmented engineering; EU work authorization).
3. Read the existing shortlist at `docs/job-shortlist.md` (if present) to dedupe and to see which roles were already evaluated.

## Search strategy

Default role focus: "Senior AI Software Engineer" / "Senior AI Engineer" — unless the user provides a different one via the skill argument.

Call the Tavily Search API with `curl -s -X POST https://api.tavily.com/search` (JSON body: `api_key`, `query`, `max_results: 8`, optionally `include_domains`).

**Phrases that surface EU-remote roles (learned from experimentation):**
- `remote in Europe`, `anywhere in Europe`, `remote EMEA`, `EU remote`, `fully remote Europe`
- ⚠️ Plain `remote UK` usually means UK residency required — treat those as low-probability unless the description says otherwise.

**Proven query set (run several, in parallel):**
- `"Senior AI Software Engineer" OR "Senior AI Engineer" remote United Kingdom job` (include_domains: linkedin.com)
- `"Senior AI Engineer" remote anywhere in Europe apply linkedin jobs view`
- `"Senior AI Engineer" remote Germany full remote job LinkedIn`
- `senior AI software engineer remote EMEA Europe job board hiring` (no domain filter — catches boards)

**Widen the net beyond LinkedIn (open/scrape-friendly sources):**
- **Ashby job boards (public API, no auth):** `GET https://api.ashbyhq.com/posting-api/job-board/{company}` — send a browser User-Agent (`-A "Mozilla/5.0"`) or you get an empty/401 response. Returns all open jobs as JSON, including `location` and `secondaryLocations` — i.e. the **exact list of eligible countries** for remote roles. Many AI companies host on Ashby (n8n, elevenlabs, ...). When you know a target company, enumerate its board; when you don't, find Ashby URLs via Tavily search (`site:jobs.ashbyhq.com "senior" "AI" "Remote - Europe"`).
  - ⚠️ The per-job endpoint (`/job-board/{company}/{jobId}`, which contains the application form fields) returns **401 anonymously** — form structure is only visible in a real browser.
  - ⚠️ Ashby application pages are JS SPAs — **Tavily Extract cannot read them** (verified). Use Ashby for discovery + eligibility checks, not description scraping.
- Curated EU-remote boards: nextleveljobs.eu, euremotejobs.com, remoteineurope.com, 4dayweek.io
- Free public job APIs: Remotive (`remotive.com/api/remote-jobs`), RemoteOK (`remoteok.com/api`), Arbeitnow (`arbeitnow.com/api/job-board-api`)

## Extraction (details for promising postings)

- Use Tavily Extract (`https://api.tavily.com/extract`, body: `api_key`, `urls: [...]`) on individual `linkedin.com/jobs/view/...` URLs, **max 3 URLs per call**.
- LinkedIn rate-limits intermittently: if a call returns `failed_results`, wait a few seconds and retry.
- Even when the full description is behind the login wall, the **"Similar jobs" section of an extracted posting is a goldmine** — collect those company + title pairs as new leads.
- What is usually visible without login: title, company, location, posting date, applicant count, and often the full description.

## Evaluation criteria

For each candidate role, assess:
1. **Remote-from-Sweden eligibility** — explicit "Europe / EU / EMEA / anywhere in Europe remote" = ✅; "Remote – UK" only = ⚠️ flag as unlikely; location-only listing (e.g. "United Kingdom") = ❓ needs manual check while logged in.
   - ⚠️ **"Remote Europe" ≠ Sweden-eligible.** Companies often publish a fixed country list, and Sweden is sometimes excluded even when Norway/Denmark/Finland are included (verified on n8n's "Remote - Europe" role: 26 countries, no Sweden). **Before rating any role ✅, verify Sweden is in the eligible-country list** — for Ashby-hosted roles use the board API above (`location` + `secondaryLocations`); otherwise check the full description or ask the user to confirm while logged in.
2. **Tech fit** with the profile (Node.js/TS and Java are strong matches; Python/ML-heavy = medium; native mobile = strong if AI-adjacent).
3. **Seniority** — senior/staff/lead level.
4. **Freshness (LinkedIn signals)** — extracted public pages contain posting age, applicant counts, and closure banners. Rules (strict only on clear signals):
   - **Discard immediately** if the text contains "No longer accepting applications" (or equivalent closure banner).
   - **Discard** if "Reposted" or "Posted" **more than ~6 months ago** (e.g. "Reposted 1 year ago") — especially combined with "0 applicants"; these are almost always dead listings.
   - **Prefer** postings from the last 30 days; between 1-6 months is fine, no penalty.
   - When a role is discarded for staleness, mark it **❌ closed/stale** on the shortlist (don't delete the row — avoids re-adding it next run).

## Output

1. Present a shortlist table: Role (link) | Company | Location policy | Fit + one-line rationale.
2. Append **new, unique** findings to `docs/job-shortlist.md` (dedupe by job URL, fallback: company+title). Keep the table sorted: strong matches first, then medium, then ❓.
3. Note any search phrases or sources that worked unusually well, and suggest updating this skill's "Phrases" section with them.

## Iteration log (keep this section current)

- 2026-08-15: First run. Tavily + LinkedIn public pages confirmed viable for discovery without login. Extraction intermittently rate-limited (retry works). "Similar jobs" mining discovered. n8n Sr AI Engineer (Remote Europe, TS/Node) flagged as best technical fit so far; Zartis "Senior AI Software Engineer" (EU) has the exact reference title.
- 2026-08-15 (autofill analysis): Ashby added as a source. Board listing API is public and exposes eligible-country lists — used it to discover n8n's "Remote - Europe" role **excludes Sweden** (downgraded on shortlist) and ElevenLabs Full-Stack also excludes Sweden. Learned: never trust "Remote Europe" at face value; always verify the country list. Also confirmed Tavily cannot read/fill Ashby application forms (JS SPA) — autofill, if built, must be browser-side (extension/userscript), which is out of scope for this skill.
- 2026-08-15 (staleness filter): TalentCo "Senior Full Stack Engineer (Agentic AI)" turned out stale — "Reposted 1 year ago" + "No longer accepting applications" (user spotted it on the live page). Added freshness rules: discard on closure banners or reposts older than ~6 months, keep discarded rows marked ❌ closed/stale to prevent re-adding.
- 2026-08-15 (run 2): **Greenhouse has an equivalent public API**: `GET https://boards-api.greenhouse.io/v1/boards/{company}/jobs` (no auth, no special UA) — use it for country-list eligibility checks on Greenhouse-hosted companies (verified on GitLab: all AI roles UK/CA/US/IN → Sweden ineligible). Also learned: **Sweden-local searches** (`AI engineer Stockholm` / `remote Sweden`) surface zero-eligibility-risk roles directly on company career sites (Nordea, BCG X, Adavo) — add local-Sweden queries to the proven query set. SoSafe's AI Platform role (perfect TS/Node/LLM fit) is UK/PT/IE only; EverAI's generic Senior SWE Europe role was delisted between search and verification — roles churn fast, verify against the live board API before rating. Smartcat AI First Developer closed/Serbia-Armenia-Bulgaria-Georgia focus; Thoth AI closed. New strong adds: Nordea GenAI (Stockholm), BCG X FDE (Sweden).
