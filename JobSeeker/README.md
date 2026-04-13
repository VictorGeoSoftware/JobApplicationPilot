# JobSeeker

`JobSeeker` is a trigger-driven autonomous job-search agent specification intended for a Koog implementation.

## Purpose

When triggered from the `job pilot` browser extension, the agent should:

- run a live job search,
- apply the candidate-fit and geography constraints,
- combine the commercial mobile and defense/aerospace search tracks,
- and generate a standalone HTML report in this folder.

## Primary Files

- `KOOG_AGENT_PROMPT.md` - master prompt for the Koog agent
- `AGENT_INSTRUCTIONS.md` - appended instruction set including both recruiter briefs
- `job_search_report.html` - expected generated output file

## Trigger Contract

The current `job pilot` extension/backend integration triggers the workflow via a backend endpoint.

Expected behavior when the trigger is pressed:

- backend performs autonomous search workflow
- backend writes `JobSeeker/job_search_report.html`
- backend returns metadata including file path and summary

## Output Artifact

Open this file in a browser after generation:

- `JobSeeker/job_search_report.html`
