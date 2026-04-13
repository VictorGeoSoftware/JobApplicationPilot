const API_URL = "http://localhost:8000/api/recruiter/answer";
const HEALTH_URL = "http://localhost:8000/api/health";

const chatEl = document.getElementById("chat");
const statusEl = document.getElementById("status");
const questionInput = document.getElementById("questionInput");
const companyName = document.getElementById("companyName");
const jobUrl = document.getElementById("jobUrl");
const sendBtn = document.getElementById("sendBtn");
const runJobSeekerBtn = document.getElementById("runJobSeekerBtn");
const clearBtn = document.getElementById("clearBtn");
const screenshotInput = document.getElementById("screenshotInput");
const socialButtons = document.querySelectorAll(".social-btn");
const llmLabel = document.getElementById("llmLabel");
const STORAGE_KEY = "jobPilotPopupState";
const PENDING_JOB_KEY = "jobPilotPendingJobId";

let chatHistory = [];
let screenshotBase64 = null;

function renderChat() {
  chatEl.innerHTML = "";
  for (const item of chatHistory) {
    const bubble = document.createElement("div");
    bubble.className = `msg ${item.role}`;
    if (item.role === "assistant") {
      const reportMatch = item.content.match(/^Job search report generated:\n(.+)$/s);
      if (reportMatch) {
        const label = document.createElement("div");
        label.textContent = "Job search report generated:";

        const pathLink = document.createElement("a");
        pathLink.href = "#";
        pathLink.textContent = reportMatch[1];
        pathLink.addEventListener("click", async (event) => {
          event.preventDefault();
          const result = await sendRuntimeMessage({
            type: "jobpilot:open-report",
            reportPath: reportMatch[1],
          });
          if (!result?.ok) {
            setStatus(`Could not open report: ${result?.error || "unknown error"}`);
          }
        });

        bubble.append(label, pathLink);
      } else {
        bubble.textContent = item.content;
      }
    } else {
      bubble.textContent = item.content;
    }
    chatEl.appendChild(bubble);
  }
  chatEl.scrollTop = chatEl.scrollHeight;
}

function sendRuntimeMessage(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      resolve(response || {});
    });
  });
}

async function pollJob(jobId) {
  setStatus("Thinking...");
  sendBtn.disabled = true;
  if (runJobSeekerBtn) runJobSeekerBtn.disabled = true;

  while (true) {
    const response = await sendRuntimeMessage({ type: "jobpilot:get-job", jobId });
    const job = response?.job;

    if (!job || job.status === "running") {
      await new Promise((resolve) => setTimeout(resolve, 1200));
      continue;
    }

    await chrome.storage.local.remove(PENDING_JOB_KEY);
    await sendRuntimeMessage({ type: "jobpilot:clear-job", jobId });

    if (job.status === "done") {
      if (job.kind === "jobseeker") {
        const reportPath = job.result?.report_path || "Unknown path";
        const fallbackUsed = Boolean(job.result?.fallback_used);
        const preview = (job.result?.agent_response_preview || "").trim();
        addMessage("assistant", `Job search report generated:\n${reportPath}`);
        addMessage(
          "assistant",
          fallbackUsed
            ? "Report note: fallback wrapper was used because the agent response was not detected as full HTML."
            : "Report note: full HTML response detected and saved."
        );
        if (preview) {
          addMessage("assistant", `Agent response preview:\n${preview}`);
        }
        setStatus(`JobSeeker report ready: ${reportPath}`);
      } else {
        addMessage("assistant", job.result.answer);
        setStatus(`Used docs: ${job.result.used_context_files.join(", ") || "none"}`);
        questionInput.value = "";
        await saveState();
      }
    } else {
      addMessage("assistant", `Error: ${job.error || "Request failed"}`);
      setStatus("Request failed.");
    }

    sendBtn.disabled = false;
    if (runJobSeekerBtn) runJobSeekerBtn.disabled = false;
    break;
  }
}

function addMessage(role, content) {
  chatHistory.push({ role, content });
  if (chatHistory.length > 20) {
    chatHistory = chatHistory.slice(-20);
  }
  renderChat();
  void saveState();
}

function setStatus(text) {
  statusEl.textContent = text;
}

async function loadActiveLlmLabel() {
  if (!llmLabel) return;

  try {
    const response = await fetch(HEALTH_URL);
    if (!response.ok) {
      llmLabel.textContent = "LLM: offline";
      return;
    }

    const data = await response.json();
    const model = typeof data?.model === "string" ? data.model.trim() : "";
    const deployment = typeof data?.deployment === "string" ? data.deployment.trim() : "";
    const provider = typeof data?.provider === "string" ? data.provider.trim() : "";
    const activeLabel = model || deployment;

    if (!activeLabel) {
      llmLabel.textContent = "LLM: unknown";
      return;
    }

    llmLabel.textContent = provider ? `LLM: ${activeLabel} (${provider})` : `LLM: ${activeLabel}`;
  } catch (_error) {
    llmLabel.textContent = "LLM: offline";
  }
}

async function copyToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const tempInput = document.createElement("textarea");
  tempInput.value = text;
  tempInput.style.position = "fixed";
  tempInput.style.opacity = "0";
  document.body.appendChild(tempInput);
  tempInput.focus();
  tempInput.select();
  document.execCommand("copy");
  document.body.removeChild(tempInput);
}

async function saveState() {
  try {
    await chrome.storage.local.set({
      [STORAGE_KEY]: {
        chatHistory,
        companyName: companyName.value,
        jobUrl: jobUrl.value,
        questionDraft: questionInput.value,
      },
    });
  } catch (_error) {
  }
}

async function loadState() {
  try {
    const data = await chrome.storage.local.get(STORAGE_KEY);
    const state = data?.[STORAGE_KEY];
    if (!state) return;

    if (Array.isArray(state.chatHistory)) {
      chatHistory = state.chatHistory
        .filter((entry) => entry && (entry.role === "user" || entry.role === "assistant") && typeof entry.content === "string")
        .slice(-20);
    }
    companyName.value = typeof state.companyName === "string" ? state.companyName : "";
    jobUrl.value = typeof state.jobUrl === "string" ? state.jobUrl : "";
    questionInput.value = typeof state.questionDraft === "string" ? state.questionDraft : "";
    renderChat();
  } catch (_error) {
  }
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

companyName.addEventListener("input", () => {
  void saveState();
});

jobUrl.addEventListener("input", () => {
  void saveState();
});

questionInput.addEventListener("input", () => {
  void saveState();
});

socialButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    const name = button.dataset.name;
    const link = button.dataset.link;

    if (!name || !link) {
      setStatus("Social link not available.");
      return;
    }

    try {
      await copyToClipboard(link);
      setStatus(`${name} link copied to clipboard.`);
    } catch (_error) {
      setStatus(`Could not copy ${name} link.`);
    }
  });
});

clearBtn.addEventListener("click", async () => {
  chatHistory = [];
  screenshotBase64 = null;
  questionInput.value = "";
  companyName.value = "";
  jobUrl.value = "";
  screenshotInput.value = "";
  renderChat();
  setStatus("Conversation cleared.");
  const pending = await chrome.storage.local.get(PENDING_JOB_KEY);
  const pendingJobId = pending?.[PENDING_JOB_KEY];
  if (pendingJobId) {
    await sendRuntimeMessage({ type: "jobpilot:clear-job", jobId: pendingJobId });
    await chrome.storage.local.remove(PENDING_JOB_KEY);
  }
  await saveState();
});

runJobSeekerBtn.addEventListener("click", async () => {
  const companyNameValue = companyName.value.trim();
  const jobUrlValue = jobUrl.value.trim();

  const seedSummary = [
    companyNameValue ? `company: ${companyNameValue}` : null,
    jobUrlValue ? `job url: ${jobUrlValue}` : null,
  ]
    .filter(Boolean)
    .join(" | ");

  addMessage(
    "user",
    seedSummary
      ? `Starting autonomous job search (${seedSummary})`
      : "Starting autonomous job search"
  );
  setStatus("Thinking...");
  runJobSeekerBtn.disabled = true;

  try {
    const started = await sendRuntimeMessage({ type: "jobpilot:start-jobseeker" });
    if (!started?.ok || !started?.jobId) {
      throw new Error("Unable to start jobseeker job");
    }
    await chrome.storage.local.set({ [PENDING_JOB_KEY]: started.jobId });
    await pollJob(started.jobId);
  } catch (error) {
    addMessage("assistant", `Error: ${error.message}`);
    setStatus("Request failed.");
    runJobSeekerBtn.disabled = false;
  }
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
    const started = await sendRuntimeMessage({ type: "jobpilot:start-request", payload });
    if (!started?.ok || !started?.jobId) {
      throw new Error("Unable to start request job");
    }
    await chrome.storage.local.set({ [PENDING_JOB_KEY]: started.jobId });
    await pollJob(started.jobId);
  } catch (error) {
    addMessage("assistant", `Error: ${error.message}`);
    setStatus("Request failed.");
    sendBtn.disabled = false;
  }
});

void loadState().then(async () => {
  const data = await chrome.storage.local.get(PENDING_JOB_KEY);
  const pendingJobId = data?.[PENDING_JOB_KEY];
  if (pendingJobId) {
    await pollJob(pendingJobId);
  }
});

void loadActiveLlmLabel();
