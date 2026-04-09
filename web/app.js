const statusEl = document.getElementById("status");
const generateBtn = document.getElementById("generate-btn");
const motivationEl = document.getElementById("motivation");
const coverLetterEl = document.getElementById("cover-letter");

const customKeyEl = document.getElementById("custom-key");
const customDescriptionEl = document.getElementById("custom-description");
const customResponseEl = document.getElementById("custom-response");
const saveCustomBtn = document.getElementById("save-custom-btn");
const customListEl = document.getElementById("custom-list");

const fieldNameEl = document.getElementById("field-name");
const fieldDescriptionEl = document.getElementById("field-description");
const matchBtn = document.getElementById("match-btn");
const matchOutput = document.getElementById("match-output");

function setStatus(message) {
  statusEl.textContent = message;
}

async function loadCustomResponses() {
  const res = await fetch("/api/custom-responses");
  const items = await res.json();

  customListEl.innerHTML = "";
  if (!items.length) {
    customListEl.innerHTML = '<div class="muted">No saved responses yet.</div>';
    return;
  }

  for (const item of items) {
    const div = document.createElement("div");
    div.className = "custom-item";
    div.innerHTML = `
      <strong>${item.key}</strong>
      <div>${item.description}</div>
      <div class="muted">${item.response.slice(0, 240)}${item.response.length > 240 ? "..." : ""}</div>
      <button data-delete="${item.key}">Delete</button>
    `;
    customListEl.appendChild(div);
  }
}

generateBtn.addEventListener("click", async () => {
  setStatus("Generating with Gemini...");
  try {
    const payload = {
      jobUrl: document.getElementById("job-url").value.trim(),
      jobTitle: document.getElementById("job-title").value.trim(),
      company: document.getElementById("job-company").value.trim(),
      jobDescription: document.getElementById("job-description").value.trim()
    };

    const res = await fetch("/api/generate-pack", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data?.details || data?.error || "Generation failed");
    }

    motivationEl.value = data.fields.motivation || "";
    coverLetterEl.value = data.fields.coverLetter || "";
    setStatus(`Generated with ${data.ai.model}`);
  } catch (error) {
    setStatus(`Error: ${error.message}`);
  }
});

saveCustomBtn.addEventListener("click", async () => {
  const key = customKeyEl.value.trim();
  const description = customDescriptionEl.value.trim();
  const response = customResponseEl.value.trim();

  if (!key || !description || !response) {
    setStatus("Fill key, description and response.");
    return;
  }

  await fetch("/api/custom-responses", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key, description, response })
  });

  customKeyEl.value = "";
  customDescriptionEl.value = "";
  customResponseEl.value = "";
  setStatus("Custom response saved.");
  await loadCustomResponses();
});

customListEl.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-delete]");
  if (!button) return;

  const key = button.getAttribute("data-delete");
  await fetch(`/api/custom-responses/${encodeURIComponent(key)}`, { method: "DELETE" });
  setStatus(`Deleted ${key}`);
  await loadCustomResponses();
});

matchBtn.addEventListener("click", async () => {
  const fieldName = fieldNameEl.value.trim();
  const fieldDescription = fieldDescriptionEl.value.trim();
  const res = await fetch("/api/match-field", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fieldName, fieldDescription })
  });

  const data = await res.json();
  matchOutput.textContent = JSON.stringify(data, null, 2);
});

document.querySelectorAll("button[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    const id = button.getAttribute("data-copy");
    const target = document.getElementById(id);
    if (!target) return;

    await navigator.clipboard.writeText(target.value || "");
    setStatus(`Copied ${id}.`);
  });
});

loadCustomResponses();
