const csvInput = document.getElementById("csv-input");
const uploadBtn = document.getElementById("upload-btn");
const defaultBtn = document.getElementById("default-btn");
const stepBtn = document.getElementById("step-btn");
const resetBtn = document.getElementById("reset-btn");
const weekCounter = document.getElementById("week-counter");
const errorBanner = document.getElementById("error-banner");
const doneBanner = document.getElementById("done-banner");

function formatMoney(n) {
  return `$${n.toFixed(2)}`;
}

function showError(message) {
  errorBanner.textContent = message;
  errorBanner.classList.remove("hidden");
}

function clearError() {
  errorBanner.classList.add("hidden");
  errorBanner.textContent = "";
}

function renderState(data) {
  weekCounter.textContent = `Week ${data.week} / ${data.total_weeks}`;
  stepBtn.disabled = data.done;
  resetBtn.disabled = false;
  doneBanner.classList.toggle("hidden", !data.done);

  for (const [role, snapshot] of Object.entries(data.stages)) {
    const card = document.querySelector(`.stage-card[data-role="${role}"]`);
    if (!card) continue;
    card.querySelector(".stat-stock").textContent = snapshot.stock;
    card.querySelector(".stat-order").textContent =
      snapshot.order_placed === null ? "--" : snapshot.order_placed;
    card.querySelector(".stat-cost").textContent = formatMoney(snapshot.cumulative_cost);
    card.querySelector(".reasoning").textContent = snapshot.reasoning || "--";
  }
}

async function handleResponse(resp) {
  if (!resp.ok) {
    let detail = `Request failed (${resp.status})`;
    try {
      const body = await resp.json();
      if (body.detail) detail = body.detail;
    } catch (_) {
      /* ignore parse failure, use default detail */
    }
    throw new Error(detail);
  }
  return resp.json();
}

async function uploadCsv() {
  const file = csvInput.files[0];
  if (!file) {
    showError("Choose a CSV file first.");
    return;
  }
  clearError();
  uploadBtn.disabled = true;
  uploadBtn.textContent = "Uploading...";
  try {
    const formData = new FormData();
    formData.append("file", file);
    const resp = await fetch("/api/upload-csv", { method: "POST", body: formData });
    const data = await handleResponse(resp);
    renderState(data);
  } catch (e) {
    showError(e.message);
  } finally {
    uploadBtn.disabled = false;
    uploadBtn.textContent = "Upload & Start";
  }
}

async function useDefaultData() {
  clearError();
  defaultBtn.disabled = true;
  const originalLabel = defaultBtn.textContent;
  defaultBtn.textContent = "Loading...";
  try {
    const resp = await fetch("/api/use-default-data", { method: "POST" });
    const data = await handleResponse(resp);
    renderState(data);
  } catch (e) {
    showError(e.message);
  } finally {
    defaultBtn.disabled = false;
    defaultBtn.textContent = originalLabel;
  }
}

async function stepWeek() {
  clearError();
  stepBtn.disabled = true;
  const originalLabel = stepBtn.textContent;
  stepBtn.textContent = "Agents thinking...";
  try {
    const resp = await fetch("/api/step", { method: "POST" });
    const data = await handleResponse(resp);
    renderState(data);
  } catch (e) {
    showError(e.message);
  } finally {
    stepBtn.textContent = originalLabel;
  }
}

async function resetSim() {
  clearError();
  resetBtn.disabled = true;
  try {
    const resp = await fetch("/api/reset", { method: "POST" });
    const data = await handleResponse(resp);
    renderState(data);
  } catch (e) {
    showError(e.message);
  } finally {
    resetBtn.disabled = false;
  }
}

async function tryRestoreState() {
  try {
    const resp = await fetch("/api/state");
    if (!resp.ok) return;
    const data = await resp.json();
    renderState(data);
  } catch (_) {
    /* no simulation loaded yet -- leave initial UI as-is */
  }
}

uploadBtn.addEventListener("click", uploadCsv);
defaultBtn.addEventListener("click", useDefaultData);
stepBtn.addEventListener("click", stepWeek);
resetBtn.addEventListener("click", resetSim);

tryRestoreState();
