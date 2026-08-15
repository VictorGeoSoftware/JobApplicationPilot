const GEMINI_MODEL = process.env.GEMINI_MODEL || "gemini-1.5-flash";

function tokenize(text = "") {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter(Boolean);
}

function jaccardScore(aText, bText) {
  const a = new Set(tokenize(aText));
  const b = new Set(tokenize(bText));
  if (!a.size || !b.size) return 0;

  let intersection = 0;
  for (const token of a) {
    if (b.has(token)) {
      intersection += 1;
    }
  }
  return intersection / (a.size + b.size - intersection);
}

function bestHeuristicMatch(fieldName, fieldDescription, entries) {
  const source = `${fieldName || ""} ${fieldDescription || ""}`.trim();
  let best = null;

  for (const entry of entries) {
    const score = jaccardScore(source, `${entry.key} ${entry.description}`);
    if (!best || score > best.score) {
      best = { entry, score };
    }
  }

  if (!best || best.score < 0.12) {
    return null;
  }

  return {
    matchedBy: "heuristic",
    confidence: Number(best.score.toFixed(2)),
    key: best.entry.key,
    description: best.entry.description,
    response: best.entry.response
  };
}

async function bestGeminiMatch(fieldName, fieldDescription, entries) {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey || !entries.length) {
    return null;
  }

  const prompt = `Task: Choose the best matching key for a job application field.
Return strict JSON only with this shape: {"key":"...","confidence":0.0,"reason":"..."}
If no match is good, return {"key":"","confidence":0.0,"reason":"..."}

Field name: ${fieldName || ""}
Field description: ${fieldDescription || ""}

Available keys:
${JSON.stringify(entries.map((item) => ({ key: item.key, description: item.description })), null, 2)}
`;

  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(GEMINI_MODEL)}:generateContent?key=${encodeURIComponent(apiKey)}`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ role: "user", parts: [{ text: prompt }] }],
      generationConfig: { temperature: 0.2, maxOutputTokens: 200 }
    })
  });

  if (!response.ok) {
    return null;
  }

  const data = await response.json();
  const text = data?.candidates?.[0]?.content?.parts?.[0]?.text?.trim();
  if (!text) {
    return null;
  }

  try {
    const parsed = JSON.parse(text);
    if (!parsed.key) return null;
    const found = entries.find((entry) => entry.key === parsed.key);
    if (!found) return null;

    return {
      matchedBy: "gemini",
      confidence: typeof parsed.confidence === "number" ? parsed.confidence : 0.5,
      key: found.key,
      description: found.description,
      response: found.response,
      reason: parsed.reason || ""
    };
  } catch (_error) {
    return null;
  }
}

module.exports = {
  bestHeuristicMatch,
  bestGeminiMatch
};
