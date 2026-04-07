const API_URL = "http://localhost:8000/api/recruiter/answer";

const chatEl = document.getElementById("chat");
const statusEl = document.getElementById("status");
const questionInput = document.getElementById("questionInput");
const companyName = document.getElementById("companyName");
const jobUrl = document.getElementById("jobUrl");
const sendBtn = document.getElementById("sendBtn");
const screenshotInput = document.getElementById("screenshotInput");

let chatHistory = [];
let screenshotBase64 = null;

function renderChat() {
  chatEl.innerHTML = "";
  for (const item of chatHistory) {
    const bubble = document.createElement("div");
    bubble.className = `msg ${item.role}`;
    bubble.textContent = item.content;
    chatEl.appendChild(bubble);
  }
  chatEl.scrollTop = chatEl.scrollHeight;
}

function addMessage(role, content) {
  chatHistory.push({ role, content });
  if (chatHistory.length > 20) {
    chatHistory = chatHistory.slice(-20);
  }
  renderChat();
}

function setStatus(text) {
  statusEl.textContent = text;
}

async function toBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

screenshotInput.addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) {
    screenshotBase64 = null;
    return;
  }
  screenshotBase64 = await toBase64(file);
  setStatus(`Screenshot ready: ${file.name}`);
});

sendBtn.addEventListener("click", async () => {
  const question = questionInput.value.trim();
  if (!question) {
    setStatus("Please add a question first.");
    return;
  }

  addMessage("user", question);
  setStatus("Thinking...");
  sendBtn.disabled = true;

  const payload = {
    question,
    company_name: companyName.value.trim() || null,
    job_url: jobUrl.value.trim() || null,
    screenshot_base64: screenshotBase64,
    chat_history: chatHistory.slice(-8),
  };

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Failed to get answer");
    }

    addMessage("assistant", data.answer);
    setStatus(`Used docs: ${data.used_context_files.join(", ") || "none"}`);
    questionInput.value = "";
  } catch (error) {
    addMessage("assistant", `Error: ${error.message}`);
    setStatus("Request failed.");
  } finally {
    sendBtn.disabled = false;
  }
});

renderChat();
