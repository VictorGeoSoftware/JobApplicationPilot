---
name: answer-pack
description: Generate ready-to-paste answers for every field of a job application form, grounded in the candidate's full professional profile gathered across all workspace folders.
argument-hint: "<job link> + form fields (pasted text or screenshots)"
allowed-tools:
  - read
  - exec
  - edit
  - grep
---

# Answer Pack

Given a job application link and its form fields, produce a **fill sheet**: every field mapped to a ready-to-paste answer, grounded in Victor's real experience. Human reviews and submits — nothing is auto-submitted.

## Step 1 — Build the candidate context (generic, structure-agnostic)

The workspace layout varies between machines — **never assume folder names or paths**. Instead:

1. **Enumerate every workspace root folder** currently open (there may be several: the job-application-pilot project, client/product projects, work projects, learning projects...). Treat all of them as candidate material.
2. **Find the canonical profile and response library** by pattern, not by path:
   - glob for `**/profile.json` → canonical candidate profile (name, contact, skills, experience)
   - glob for `**/customResponses.json` → saved reusable answers (key + description + response)
   - glob for `**/{cv,resume,history,cover_letter}*` (html, md, txt, pdf) → CV variants and career history
3. **Scan the other project folders for evidence of shipped work** — read `README.md`, `package.json` (name/description), and `docs/` at shallow depth. These ground answers about concrete projects (e.g. mobile apps, backends, AI agents, blockchain/Solidity work). Note 2-4 projects with: what it is, stack, Victor's likely role.
4. Synthesize a short **working profile** in chat (5-8 bullets) before answering, so the user can correct anything wrong. If a richer profile already exists in the conversation, reuse it instead of rescanning.

## Step 2 — Get job context

- Read `TAVILY_API_KEY` from any `.env` in the workspace (never print it) and use Tavily to research the role/company.
- LinkedIn public job pages extract well. **Ashby pages are JS SPAs — Tavily Extract fails on them**; for `jobs.ashbyhq.com/{company}/{id}` links, use the public board API instead: `curl -s -A "Mozilla/5.0" https://api.ashbyhq.com/posting-api/job-board/{company}` for metadata.
- If the user pasted the job description, prefer that over fetching.

## Step 3 — Get the form fields

The form fields **cannot be read from the link alone** (JS-rendered, auth-walled APIs — verified). They must come from the user: pasted text or **screenshots** (readable as images). If the user only gave a link, ask for the fields before generating answers.

## Step 4 — Produce the fill sheet

Output a table: **Field | Answer to paste | Notes**.

Rules:
1. **Reuse first**: if a field matches a saved custom response, use it (adapted to the role).
2. **Generate** free-text answers (motivation, "why us?", screening questions) grounded in the working profile + job research. No invented employers, titles, or metrics.
3. Match the form's language (usually English) and calibrate length to the field (short text ≠ essay).
4. **Flag for user decision (⚠️ REVIEW)** — propose a default but never silently decide: salary expectations, notice period, work-authorization/relocation yes-no questions, EEO/demographic fields, "are you eligible to work in X" (cross-check the eligible-country list — see `/job-hunt-eu` for the Sweden-verification rule).
5. **File uploads stay manual**: for CV fields, recommend which resume variant to upload (from the CV files found in Step 1) based on the role type.
6. If the user approves an answer to a reusable question, offer to save it to the `customResponses.json` library so the next application is faster.

## Iteration log (keep current)

- 2026-08-15: Skill created. Design decision: chat-based fill sheet instead of browser autofill (Tavily can't interact with or even read JS-rendered forms; human-in-the-loop preferred). Workspace scan made structure-agnostic so it works on any machine.
