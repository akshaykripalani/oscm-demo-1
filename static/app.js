const csvInput = document.getElementById("csv-input");
const uploadBtn = document.getElementById("upload-btn");
const defaultBtn = document.getElementById("default-btn");
const stepBtn = document.getElementById("step-btn");
const simulateAllBtn = document.getElementById("simulate-all-btn");
const resetBtn = document.getElementById("reset-btn");
const weekCounter = document.getElementById("week-counter");
const errorBanner = document.getElementById("error-banner");
const doneBanner = document.getElementById("done-banner");

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function formatMoney(n) {
  return `$${n.toFixed(2)}`;
}

const STAGE_ACCENT = {
  supplier: "#2a78d6",
  manufacturer: "#1baf7a",
  distributor: "#4a3aa7",
  retailer: "#eb6834",
};

// Fixed pair for the cost chart's two series -- consistent across every
// agent's cost chart, distinct from the per-stage accent colors above.
const COST_COLORS = ["#2a78d6", "#eb6834"];

const SVG_NS = "http://www.w3.org/2000/svg";

function svgEl(name, attrs = {}) {
  const e = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}

function niceTicks(min, max, count = 3) {
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const rawStep = (max - min) / count;
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const residual = rawStep / magnitude;
  let step;
  if (residual > 5) step = 10 * magnitude;
  else if (residual > 2) step = 5 * magnitude;
  else if (residual > 1) step = 2 * magnitude;
  else step = magnitude;

  const niceMin = Math.floor(min / step) * step;
  const niceMax = Math.ceil(max / step) * step;
  const ticks = [];
  for (let v = niceMin; v <= niceMax + step / 1000; v += step) {
    ticks.push(Math.round(v * 1000) / 1000);
  }
  return ticks;
}

function defaultFormat(v) {
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}

// Draws a small multi-series line chart into `container` from `weeks` (an
// array of week numbers) and `series` (array of {name, color, values}, each
// values array the same length as weeks). Ships with gridlines, end-dot
// markers, a legend when there's more than one series, and a hover
// crosshair + tooltip (values lead, series name follows, per-series line-key
// instead of a filled box).
function renderLineChart(container, weeks, series, opts = {}) {
  const width = 260;
  const height = 108;
  const padLeft = 30;
  const padRight = 8;
  const padTop = 8;
  const padBottom = 16;
  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;
  const format = opts.format || defaultFormat;

  container.innerHTML = "";
  container.style.position = "relative";

  const allValues = series.flatMap((s) => s.values);
  const dataMin = Math.min(0, ...allValues);
  const dataMax = Math.max(1, ...allValues);
  const ticks = niceTicks(dataMin, dataMax, 3);
  const yMin = ticks[0];
  const yMax = ticks[ticks.length - 1];

  const xFor = (i) =>
    padLeft + (weeks.length <= 1 ? 0 : (i / (weeks.length - 1)) * plotW);
  const yFor = (v) =>
    padTop + plotH - ((v - yMin) / (yMax - yMin || 1)) * plotH;

  const svg = svgEl("svg", {
    viewBox: `0 0 ${width} ${height}`,
    width: "100%",
    height,
    class: "mini-chart",
  });

  ticks.forEach((t) => {
    const y = yFor(t);
    svg.appendChild(
      svgEl("line", { x1: padLeft, x2: width - padRight, y1: y, y2: y, class: "chart-gridline" })
    );
    const label = svgEl("text", { x: padLeft - 5, y: y + 3, class: "chart-axis-label chart-axis-label-y" });
    label.textContent = format(t);
    svg.appendChild(label);
  });

  const xTickIdxs = new Set([0, weeks.length - 1]);
  const step = Math.max(1, Math.round(weeks.length / 4));
  for (let i = 0; i < weeks.length; i += step) xTickIdxs.add(i);
  xTickIdxs.forEach((i) => {
    const label = svgEl("text", { x: xFor(i), y: height - 3, class: "chart-axis-label chart-axis-label-x" });
    label.textContent = "w" + weeks[i];
    svg.appendChild(label);
  });

  series.forEach((s) => {
    const points = s.values.map((v, i) => `${xFor(i)},${yFor(v)}`).join(" ");
    svg.appendChild(svgEl("polyline", { points, class: "chart-line", style: `stroke:${s.color}` }));
    const lastI = s.values.length - 1;
    svg.appendChild(
      svgEl("circle", {
        cx: xFor(lastI),
        cy: yFor(s.values[lastI]),
        r: 4,
        class: "chart-enddot",
        style: `fill:${s.color}`,
      })
    );
  });

  const crosshair = svgEl("line", {
    x1: padLeft,
    x2: padLeft,
    y1: padTop,
    y2: padTop + plotH,
    class: "chart-crosshair",
  });
  crosshair.style.display = "none";
  svg.appendChild(crosshair);

  const hit = svgEl("rect", { x: padLeft, y: padTop, width: plotW, height: plotH, fill: "transparent" });
  svg.appendChild(hit);
  container.appendChild(svg);

  if (series.length > 1) {
    const legend = document.createElement("div");
    legend.className = "chart-legend";
    series.forEach((s) => {
      const item = document.createElement("span");
      item.className = "chart-legend-item";
      const swatch = document.createElement("span");
      swatch.className = "chart-legend-swatch";
      swatch.style.background = s.color;
      item.appendChild(swatch);
      item.appendChild(document.createTextNode(s.name));
      legend.appendChild(item);
    });
    container.appendChild(legend);
  }

  const tooltip = document.createElement("div");
  tooltip.className = "chart-tooltip hidden";
  container.appendChild(tooltip);

  function showTooltipAt(clientX) {
    const rect = svg.getBoundingClientRect();
    const mouseX = ((clientX - rect.left) / rect.width) * width;
    let idx = Math.round(((mouseX - padLeft) / plotW) * (weeks.length - 1));
    idx = Math.max(0, Math.min(weeks.length - 1, idx));

    const cx = xFor(idx);
    crosshair.setAttribute("x1", cx);
    crosshair.setAttribute("x2", cx);
    crosshair.style.display = "block";

    tooltip.innerHTML = "";
    const title = document.createElement("div");
    title.className = "chart-tooltip-title";
    title.textContent = "Week " + weeks[idx];
    tooltip.appendChild(title);
    series.forEach((s) => {
      const row = document.createElement("div");
      row.className = "chart-tooltip-row";
      const key = document.createElement("span");
      key.className = "chart-tooltip-key";
      key.style.background = s.color;
      const val = document.createElement("span");
      val.className = "chart-tooltip-value";
      val.textContent = format(s.values[idx]);
      const name = document.createElement("span");
      name.className = "chart-tooltip-name";
      name.textContent = s.name;
      row.append(key, val, name);
      tooltip.appendChild(row);
    });
    tooltip.classList.remove("hidden");

    const leftPx = (cx / width) * rect.width;
    tooltip.style.left = Math.min(leftPx, Math.max(0, rect.width - 130)) + "px";
  }

  hit.addEventListener("pointermove", (evt) => showTooltipAt(evt.clientX));
  hit.addEventListener("pointerleave", () => {
    crosshair.style.display = "none";
    tooltip.classList.add("hidden");
  });
}

function renderCharts(role, history) {
  const card = document.querySelector(`.chart-card[data-role="${role}"]`);
  if (!card || !history || history.length === 0) return;
  const weeks = history.map((h) => h.week);
  const accent = STAGE_ACCENT[role];

  renderLineChart(card.querySelector(".chart-inventory"), weeks, [
    { name: "Stock", color: accent, values: history.map((h) => h.stock) },
  ]);
  renderLineChart(
    card.querySelector(".chart-cost"),
    weeks,
    [
      { name: "Holding cost", color: COST_COLORS[0], values: history.map((h) => h.holding_cost) },
      { name: "Stockout cost", color: COST_COLORS[1], values: history.map((h) => h.stockout_cost) },
    ],
    { format: (v) => "$" + Math.round(v) }
  );
  renderLineChart(card.querySelector(".chart-orders"), weeks, [
    { name: "Order placed", color: accent, values: history.map((h) => h.order_placed) },
  ]);
  renderLineChart(card.querySelector(".chart-backlog"), weeks, [
    { name: "Backlog", color: accent, values: history.map((h) => h.backlog) },
  ]);
}

function showError(message) {
  errorBanner.textContent = message;
  errorBanner.classList.remove("hidden");
}

function clearError() {
  errorBanner.classList.add("hidden");
  errorBanner.textContent = "";
}

// -- Client-side rate limiter for "Simulate all" --------------------------
// gemini-3.1-flash-lite's free tier caps at 15 requests/minute; each step
// fires one Gemini call per agent (4 total). Tracked here as a sliding
// window so the auto-run can fire steps back-to-back and only pause when
// actually about to exceed the limit, rather than a fixed delay per step.
const RPM_LIMIT = 15;
const REQUESTS_PER_STEP = 4;
const RATE_WINDOW_MS = 60_000;
const RPM_SAFETY_MARGIN = 1; // small headroom for request round-trip jitter

let requestTimestamps = [];

function pruneRequestTimestamps() {
  const cutoff = Date.now() - RATE_WINDOW_MS;
  requestTimestamps = requestTimestamps.filter((t) => t > cutoff);
}

function recordStepRequests() {
  const now = Date.now();
  for (let i = 0; i < REQUESTS_PER_STEP; i++) requestTimestamps.push(now);
}

function msUntilStepCapacity() {
  pruneRequestTimestamps();
  const allowance = RPM_LIMIT - RPM_SAFETY_MARGIN;
  if (requestTimestamps.length + REQUESTS_PER_STEP <= allowance) return 0;
  const excess = requestTimestamps.length + REQUESTS_PER_STEP - allowance;
  const target = requestTimestamps[excess - 1];
  return Math.max(0, target + RATE_WINDOW_MS - Date.now());
}

// -- Shared simulation/UI state --------------------------------------------
let simulationLoaded = false;
let latestWeek = 0;
let latestTotalWeeks = 0;
let latestDone = false;
let autoRunning = false;
let autoCancelRequested = false;

function updateControlsForState() {
  uploadBtn.disabled = autoRunning;
  defaultBtn.disabled = autoRunning;
  stepBtn.disabled = autoRunning || !simulationLoaded || latestDone;
  resetBtn.disabled = autoRunning || !simulationLoaded;
  if (!autoRunning) {
    simulateAllBtn.disabled = !simulationLoaded || latestDone;
    simulateAllBtn.classList.remove("running");
    simulateAllBtn.textContent = `Simulate all ${latestTotalWeeks || 35} weeks`;
  }
}

function renderState(data) {
  simulationLoaded = true;
  latestWeek = data.week;
  latestTotalWeeks = data.total_weeks;
  latestDone = data.done;

  weekCounter.textContent = `Week ${data.week} / ${data.total_weeks}`;
  doneBanner.classList.toggle("hidden", !data.done);

  for (const [role, snapshot] of Object.entries(data.stages)) {
    const card = document.querySelector(`.stage-card[data-role="${role}"]`);
    if (!card) continue;
    card.querySelector(".stat-stock").textContent = snapshot.stock;
    card.querySelector(".stat-order").textContent =
      snapshot.order_placed === null ? "--" : snapshot.order_placed;
    card.querySelector(".stat-cost").textContent = formatMoney(snapshot.cumulative_cost);
    card.querySelector(".reasoning").textContent = snapshot.reasoning || "--";
    renderCharts(role, data.history && data.history[role]);
  }

  updateControlsForState();
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
    uploadBtn.textContent = "Upload & Start";
    updateControlsForState();
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
    defaultBtn.textContent = originalLabel;
    updateControlsForState();
  }
}

async function stepWeek() {
  clearError();
  stepBtn.disabled = true;
  const originalLabel = stepBtn.textContent;
  stepBtn.textContent = "Agents thinking...";
  try {
    recordStepRequests();
    const resp = await fetch("/api/step", { method: "POST" });
    const data = await handleResponse(resp);
    renderState(data);
  } catch (e) {
    showError(e.message);
  } finally {
    stepBtn.textContent = originalLabel;
    updateControlsForState();
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
    updateControlsForState();
  }
}

async function simulateAll() {
  if (autoRunning) {
    // Acts as the "Stop simulating" button while a run is in progress.
    autoCancelRequested = true;
    simulateAllBtn.textContent = "Stopping...";
    simulateAllBtn.disabled = true;
    return;
  }

  clearError();
  autoRunning = true;
  autoCancelRequested = false;
  updateControlsForState();
  simulateAllBtn.disabled = false;
  simulateAllBtn.classList.add("running");
  simulateAllBtn.textContent = "Stop simulating";

  try {
    while (!autoCancelRequested && !latestDone) {
      const wait = msUntilStepCapacity();
      if (wait > 0) {
        const until = Date.now() + wait;
        while (Date.now() < until && !autoCancelRequested) {
          const remaining = Math.ceil((until - Date.now()) / 1000);
          simulateAllBtn.textContent = `Stop simulating (rate limit, ${remaining}s)`;
          await sleep(250);
        }
        if (autoCancelRequested) break;
      }

      simulateAllBtn.textContent = `Stop simulating (week ${latestWeek + 1} of ${latestTotalWeeks}...)`;
      recordStepRequests();
      const resp = await fetch("/api/step", { method: "POST" });
      const data = await handleResponse(resp);
      renderState(data);
    }
  } catch (e) {
    showError(e.message);
  } finally {
    autoRunning = false;
    autoCancelRequested = false;
    updateControlsForState();
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
simulateAllBtn.addEventListener("click", simulateAll);
resetBtn.addEventListener("click", resetSim);

tryRestoreState();
