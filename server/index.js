require("dotenv").config();

const express = require("express");
const cors = require("cors");
const fs = require("fs/promises");
const path = require("path");
const { generateMotivationAndCoverLetter, GEMINI_MODEL } = require("./ai");
const { bestHeuristicMatch, bestGeminiMatch } = require("./matcher");

const app = express();
const PORT = process.env.PORT || 8787;

const PROFILE_PATH = path.join(__dirname, "data", "profile.json");
const RESPONSES_PATH = path.join(__dirname, "data", "customResponses.json");

app.use(cors());
app.use(express.json({ limit: "1mb" }));
app.use(express.static(path.join(__dirname, "..", "web")));

async function readJson(filePath, fallback) {
  try {
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch (_error) {
    return fallback;
  }
}

async function writeJson(filePath, value) {
  await fs.writeFile(filePath, JSON.stringify(value, null, 2));
}

function inferCompanyFromUrl(url = "") {
  try {
    const parsed = new URL(url);
    const parts = parsed.pathname.split("/").filter(Boolean);
    return parts[0] || "the company";
  } catch (_error) {
    return "the company";
  }
}

app.get("/api/health", (_req, res) => {
  res.json({ ok: true, model: GEMINI_MODEL });
});

app.get("/api/profile", async (_req, res) => {
  const profile = await readJson(PROFILE_PATH, {});
  res.json(profile);
});

app.get("/api/custom-responses", async (_req, res) => {
  const responses = await readJson(RESPONSES_PATH, []);
  res.json(responses);
});

app.post("/api/custom-responses", async (req, res) => {
  const { key, description, response } = req.body || {};
  if (!key || !description || !response) {
    return res.status(400).json({ error: "key, description and response are required" });
  }

  const responses = await readJson(RESPONSES_PATH, []);
  const normalizedKey = String(key).trim().toLowerCase().replace(/\s+/g, "_");

  const next = responses.filter((item) => item.key !== normalizedKey);
  next.push({ key: normalizedKey, description: String(description).trim(), response: String(response).trim() });
  await writeJson(RESPONSES_PATH, next);

  return res.json({ ok: true, key: normalizedKey });
});

app.delete("/api/custom-responses/:key", async (req, res) => {
  const key = String(req.params.key || "").trim();
  const responses = await readJson(RESPONSES_PATH, []);
  const next = responses.filter((item) => item.key !== key);
  await writeJson(RESPONSES_PATH, next);
  return res.json({ ok: true });
});

app.post("/api/match-field", async (req, res) => {
  const fieldName = String(req.body?.fieldName || "").trim();
  const fieldDescription = String(req.body?.fieldDescription || "").trim();

  if (!fieldName && !fieldDescription) {
    return res.status(400).json({ error: "fieldName or fieldDescription is required" });
  }

  const entries = await readJson(RESPONSES_PATH, []);
  const heuristic = bestHeuristicMatch(fieldName, fieldDescription, entries);
  const gemini = await bestGeminiMatch(fieldName, fieldDescription, entries);

  const chosen = gemini || heuristic || null;

  return res.json({
    match: chosen,
    fallback: heuristic,
    hasGemini: Boolean(process.env.GEMINI_API_KEY)
  });
});

app.post("/api/generate-pack", async (req, res) => {
  const profile = await readJson(PROFILE_PATH, {});
  const job = {
    url: String(req.body?.jobUrl || "").trim(),
    title: String(req.body?.jobTitle || "").trim(),
    company: String(req.body?.company || "").trim(),
    description: String(req.body?.jobDescription || "").trim()
  };

  if (!job.company && job.url) {
    job.company = inferCompanyFromUrl(job.url);
  }

  try {
    const generated = await generateMotivationAndCoverLetter(profile, job);
    return res.json({
      job,
      fields: {
        fullName: profile.fullName || "",
        email: profile.email || "",
        phone: profile.phone || "",
        location: profile.location || "",
        linkedin: profile.linkedin || "",
        github: profile.github || "",
        website: profile.website || profile.portfolio || "",
        workAuthorization: profile.workAuthorization || "",
        motivation: generated.motivation,
        coverLetter: generated.coverLetter
      },
      ai: {
        provider: "gemini",
        model: generated.model
      },
      generatedAt: new Date().toISOString()
    });
  } catch (error) {
    return res.status(500).json({
      error: "Failed to generate content",
      details: error.message,
      hint: "Set GEMINI_API_KEY in your .env file"
    });
  }
});

app.get("*", (_req, res) => {
  res.sendFile(path.join(__dirname, "..", "web", "index.html"));
});

app.listen(PORT, () => {
  console.log(`Job application pilot listening at http://localhost:${PORT}`);
});
