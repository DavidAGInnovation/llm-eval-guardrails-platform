const state = {
  runs: [],
  selectedRunId: null,
  results: [],
};

const el = {
  refreshBtn: document.getElementById("refreshBtn"),
  runsTableBody: document.getElementById("runsTableBody"),
  selectedRunLabel: document.getElementById("selectedRunLabel"),
  passBar: document.getElementById("passBar"),
  qualityBar: document.getElementById("qualityBar"),
  hallucinationBar: document.getElementById("hallucinationBar"),
  toxicityBar: document.getElementById("toxicityBar"),
  passValue: document.getElementById("passValue"),
  qualityValue: document.getElementById("qualityValue"),
  hallucinationValue: document.getElementById("hallucinationValue"),
  toxicityValue: document.getElementById("toxicityValue"),
  resultChips: document.getElementById("resultChips"),
  totalRuns: document.getElementById("totalRuns"),
  avgPassRate: document.getElementById("avgPassRate"),
  blockedSamples: document.getElementById("blockedSamples"),
  datasetPolicyCount: document.getElementById("datasetPolicyCount"),
};

const fmtPct = (value) => {
  if (value === null || value === undefined) return "-";
  return `${(Number(value) * 100).toFixed(1)}%`;
};

const clampPct = (value) => `${Math.max(0, Math.min(100, value * 100)).toFixed(1)}%`;

const escapeHtml = (value) =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

function displayProvider(run) {
  if (run.model_name && run.model_name.includes("/")) {
    return run.model_name.split("/")[0];
  }
  return run.provider;
}

async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path} -> ${response.status}`);
  return response.json();
}

function renderRunTable() {
  if (!state.runs.length) {
    el.runsTableBody.innerHTML = '<tr><td class="empty" colspan="5">No runs yet.</td></tr>';
    return;
  }

  el.runsTableBody.innerHTML = state.runs
    .slice(0, 10)
    .map((run) => {
      const statusClass = `status-${run.status}`;
      const activeClass = run.id === state.selectedRunId ? "active" : "";

      return `
      <tr data-run-id="${run.id}" class="${activeClass}">
        <td><span class="status-pill ${statusClass}">${escapeHtml(run.status)}</span></td>
        <td>${escapeHtml(displayProvider(run))}</td>
        <td>${escapeHtml(run.model_name)}</td>
        <td>${fmtPct(run.pass_rate)}</td>
        <td>${run.blocked_count}</td>
      </tr>`;
    })
    .join("");

  for (const row of el.runsTableBody.querySelectorAll("tr[data-run-id]")) {
    row.addEventListener("click", async () => {
      state.selectedRunId = row.dataset.runId;
      renderRunTable();
      await loadSelectedRunDetails();
    });
  }
}

function renderSummary(run) {
  if (!run) {
    el.selectedRunLabel.textContent = "No run selected";
    el.passBar.style.width = "0%";
    el.qualityBar.style.width = "0%";
    el.hallucinationBar.style.width = "0%";
    el.toxicityBar.style.width = "0%";
    el.passValue.textContent = "-";
    el.qualityValue.textContent = "-";
    el.hallucinationValue.textContent = "-";
    el.toxicityValue.textContent = "-";
    return;
  }

  el.selectedRunLabel.textContent = `${displayProvider(run)} / ${run.model_name}`;

  const pass = Number(run.pass_rate ?? 0);
  const quality = Number(run.avg_quality_score ?? 0);
  const hallucination = Number(run.avg_hallucination_score ?? 0);
  const toxicity = Number(run.avg_toxicity_score ?? 0);

  el.passBar.style.width = clampPct(pass);
  el.qualityBar.style.width = clampPct(quality);
  el.hallucinationBar.style.width = clampPct(hallucination);
  el.toxicityBar.style.width = clampPct(toxicity);

  el.passValue.textContent = fmtPct(pass);
  el.qualityValue.textContent = quality.toFixed(2);
  el.hallucinationValue.textContent = hallucination.toFixed(2);
  el.toxicityValue.textContent = toxicity.toFixed(2);
}

function renderResultChips() {
  if (!state.results.length) {
    el.resultChips.innerHTML = '<p class="empty">No samples available for this run.</p>';
    return;
  }

  el.resultChips.innerHTML = state.results
    .slice(0, 6)
    .map((result) => {
      const status = result.blocked ? "Blocked" : "Pass";
      const challenge = escapeHtml(result.prompt_text || "");
      const snippet = escapeHtml(result.response_text).slice(0, 180);
      return `
      <article class="chip">
        <div class="chip-head">
          <small>${status}</small>
          <small>Latency ${result.latency_ms}ms</small>
        </div>
        <p class="chip-label">Challenge</p>
        <p class="chip-question">${challenge}</p>
        <p class="chip-label">Response</p>
        <p>${snippet}${result.response_text.length > 180 ? "..." : ""}</p>
      </article>`;
    })
    .join("");
}

async function loadSelectedRunDetails() {
  const run = state.runs.find((item) => item.id === state.selectedRunId);
  renderSummary(run);

  if (!run) {
    state.results = [];
    renderResultChips();
    return;
  }

  try {
    state.results = await getJson(`/runs/${run.id}/results`);
  } catch {
    state.results = [];
  }

  renderResultChips();
}

function renderStats(runs, datasets, policies) {
  const totalRuns = runs.length;
  const avgPassRate = totalRuns
    ? runs.reduce((sum, run) => sum + Number(run.pass_rate ?? 0), 0) / totalRuns
    : 0;
  const blockedSamples = runs.reduce((sum, run) => sum + Number(run.blocked_count ?? 0), 0);

  el.totalRuns.textContent = String(totalRuns);
  el.avgPassRate.textContent = fmtPct(avgPassRate);
  el.blockedSamples.textContent = String(blockedSamples);
  el.datasetPolicyCount.textContent = `${datasets.length} / ${policies.length}`;
}

async function loadDashboard() {
  el.refreshBtn.disabled = true;
  el.refreshBtn.textContent = "Refreshing...";

  try {
    const [runs, datasets, policies] = await Promise.all([
      getJson("/runs"),
      getJson("/datasets"),
      getJson("/policies"),
    ]);

    state.runs = runs;
    renderStats(runs, datasets, policies);

    if (!state.selectedRunId && runs.length) {
      state.selectedRunId = runs[0].id;
    }

    renderRunTable();
    await loadSelectedRunDetails();
  } catch (error) {
    el.runsTableBody.innerHTML = `<tr><td class="empty" colspan="5">Failed loading data: ${escapeHtml(
      String(error)
    )}</td></tr>`;
    renderSummary(null);
    state.results = [];
    renderResultChips();
  } finally {
    el.refreshBtn.disabled = false;
    el.refreshBtn.textContent = "Refresh";
  }
}

el.refreshBtn.addEventListener("click", loadDashboard);
loadDashboard();
