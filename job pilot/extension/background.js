const API_URL = "http://localhost:8000/api/recruiter/answer";
const JOBSEEKER_API_URL = "http://localhost:8000/api/jobseeker/run";
const JOB_STORAGE_KEY = "jobPilotPendingJobs";

async function getJobs() {
  const data = await chrome.storage.local.get(JOB_STORAGE_KEY);
  return data?.[JOB_STORAGE_KEY] || {};
}

async function setJobs(jobs) {
  await chrome.storage.local.set({ [JOB_STORAGE_KEY]: jobs });
}

function createId() {
  return `job_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

async function runRequest(jobId, payload) {
  const jobs = await getJobs();
  jobs[jobId] = { status: "running", createdAt: Date.now() };
  await setJobs(jobs);

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    let data = {};
    try {
      data = await response.json();
    } catch (_error) {
    }

    if (!response.ok) {
      throw new Error(data.detail || "Failed to get answer");
    }

    jobs[jobId] = {
      status: "done",
      result: data,
      completedAt: Date.now(),
    };
    await setJobs(jobs);
  } catch (error) {
    jobs[jobId] = {
      status: "error",
      error: error.message || "Unknown error",
      completedAt: Date.now(),
    };
    await setJobs(jobs);
  }
}

async function runJobSeeker(jobId) {
  const jobs = await getJobs();
  jobs[jobId] = { status: "running", kind: "jobseeker", createdAt: Date.now() };
  await setJobs(jobs);

  try {
    const response = await fetch(JOBSEEKER_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });

    let data = {};
    try {
      data = await response.json();
    } catch (_error) {
    }

    if (!response.ok) {
      throw new Error(data.detail || "Failed to run JobSeeker");
    }

    jobs[jobId] = {
      status: "done",
      kind: "jobseeker",
      result: data,
      completedAt: Date.now(),
    };
    await setJobs(jobs);
  } catch (error) {
    jobs[jobId] = {
      status: "error",
      kind: "jobseeker",
      error: error.message || "Unknown error",
      completedAt: Date.now(),
    };
    await setJobs(jobs);
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "jobpilot:start-request") {
    const jobId = createId();
    void runRequest(jobId, message.payload);
    sendResponse({ ok: true, jobId });
    return true;
  }

  if (message?.type === "jobpilot:start-jobseeker") {
    const jobId = createId();
    void runJobSeeker(jobId);
    sendResponse({ ok: true, jobId });
    return true;
  }

  if (message?.type === "jobpilot:get-job") {
    void getJobs().then((jobs) => {
      sendResponse({ ok: true, job: jobs[message.jobId] || null });
    });
    return true;
  }

  if (message?.type === "jobpilot:clear-job") {
    void getJobs().then(async (jobs) => {
      delete jobs[message.jobId];
      await setJobs(jobs);
      sendResponse({ ok: true });
    });
    return true;
  }

  if (message?.type === "jobpilot:open-report") {
    const reportPath = typeof message.reportPath === "string" ? message.reportPath.trim() : "";
    if (!reportPath) {
      sendResponse({ ok: false, error: "Missing report path" });
      return true;
    }

    const targetUrl = reportPath.startsWith("file://") ? reportPath : `file://${reportPath}`;

    chrome.tabs.create({ url: targetUrl }, () => {
      if (chrome.runtime.lastError) {
        sendResponse({ ok: false, error: chrome.runtime.lastError.message });
        return;
      }
      sendResponse({ ok: true });
    });

    return true;
  }

  return false;
});
