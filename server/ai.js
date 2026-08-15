const GEMINI_MODEL = process.env.GEMINI_MODEL || "gemini-1.5-flash";

function countWords(text = "") {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function stripHtml(html = "") {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

async function maybeFetchJobOfferText(job = {}) {
  if (job.description && job.description.trim().length > 120) {
    return job.description.trim();
  }

  if (!job.url) {
    return "";
  }

  try {
    const response = await fetch(job.url, {
      method: "GET",
      headers: { "User-Agent": "job-application-pilot/0.2" }
    });
    if (!response.ok) return "";
    const html = await response.text();
    const text = stripHtml(html);
    return text.slice(0, 9000);
  } catch (_error) {
    return "";
  }
}

function buildPrompt(profile, job, responseType) {
  const isMotivation = responseType === "motivation";
  const tone = isMotivation ? "plain, friendly, concise, and specific" : "plain, friendly, professional, and compelling";
  const lengthRule = isMotivation
    ? "Write 120-180 words in one or two short paragraphs."
    : "Write 220-320 words in three or four short paragraphs.";

  return `You are an expert job application writer.
Return only plain text without markdown.

Task: Generate a ${responseType} for this candidate and job.
Tone: ${tone}
Language: English
Constraints:
- Avoid generic filler.
- Keep facts aligned with provided profile.
- Mention relevant Android/mobile strengths when applicable.
- Do not invent companies or achievements.
- Read the full job offer text provided below and focus on the most relevant requirements.
- Use plain and friendly language, without sounding robotic.
- ${lengthRule}
- End with a complete sentence.
- Do not include name/email/phone/address headers.
- Do not include sender or recipient address blocks.
- Do not include a formal email subject line.

Candidate profile (JSON):
${JSON.stringify(profile, null, 2)}

Job context (JSON):
${JSON.stringify(job, null, 2)}

Job offer full text (extracted):
${job.offerText || ""}
`;
}

function extractCandidateText(data) {
  const parts = data?.candidates?.[0]?.content?.parts || [];
  const text = parts
    .map((part) => (typeof part?.text === "string" ? part.text : ""))
    .join("")
    .trim();
  return text;
}

function sanitizeCoverLetter(text, profile) {
  const blockedLiterals = [
    profile?.fullName || "",
    profile?.email || "",
    profile?.phone || "",
    profile?.location || ""
  ]
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);

  const lines = text.split("\n");
  const cleaned = lines.filter((line, index) => {
    const current = line.trim().toLowerCase();
    if (!current) return true;

    if (index < 6) {
      if (blockedLiterals.includes(current)) return false;
      if (current.includes("@")) return false;
      if (/^\+?[0-9][0-9\s().-]{6,}$/.test(current)) return false;
    }

    return true;
  });

  return cleaned.join("\n").trim();
}

async function callGemini(prompt, maxOutputTokens) {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    throw new Error("Missing GEMINI_API_KEY");
  }

  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(GEMINI_MODEL)}:generateContent?key=${encodeURIComponent(apiKey)}`;

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [
        {
          role: "user",
          parts: [{ text: prompt }]
        }
      ],
      generationConfig: {
        temperature: 0.5,
        maxOutputTokens
      }
    })
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Gemini request failed: ${response.status} ${errText}`);
  }

  const data = await response.json();
  const text = extractCandidateText(data);
  if (!text) {
    throw new Error("Gemini returned an empty response");
  }
  return text;
}

async function generateWithRetry(prompt, maxOutputTokens, minWords, responseType) {
  let answer = await callGemini(prompt, maxOutputTokens);
  if (countWords(answer) >= minWords) {
    return answer;
  }

  const retryPrompt = `${prompt}

The previous ${responseType} was too short.
Rewrite it fully from scratch with complete content and at least ${minWords} words.`;

  answer = await callGemini(retryPrompt, maxOutputTokens);
  return answer;
}

async function generateMotivationAndCoverLetter(profile, job) {
  const offerText = await maybeFetchJobOfferText(job);
  const enrichedJob = { ...job, offerText };

  const motivationPrompt = buildPrompt(profile, enrichedJob, "motivation");
  const coverLetterPrompt = buildPrompt(profile, enrichedJob, "cover letter");

  const [motivation, coverLetter] = await Promise.all([
    generateWithRetry(motivationPrompt, 1200, 100, "motivation"),
    generateWithRetry(coverLetterPrompt, 1800, 180, "cover letter")
  ]);

  return {
    motivation,
    coverLetter: sanitizeCoverLetter(coverLetter, profile),
    model: GEMINI_MODEL
  };
}

module.exports = {
  generateMotivationAndCoverLetter,
  GEMINI_MODEL
};
