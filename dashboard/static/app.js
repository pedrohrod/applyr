"use strict";

const CHART_DEFAULTS = {
  color: "#e2e4ef",
  borderColor: "#2a2d3e",
  plugins: { legend: { labels: { color: "#6b7280", boxWidth: 12 } } },
  scales: {
    x: { ticks: { color: "#6b7280" }, grid: { color: "#1f2232" } },
    y: { ticks: { color: "#6b7280" }, grid: { color: "#1f2232" } },
  },
};

function scoreClass(s) {
  if (s >= 70) return "score-high";
  if (s >= 50) return "score-mid";
  return "score-low";
}

async function loadStats() {
  const r = await fetch("/api/stats");
  const d = await r.json();
  document.getElementById("stat-total").textContent   = d.total;
  document.getElementById("stat-applied").textContent  = d.applied;
  document.getElementById("stat-skipped").textContent  = d.skipped;
  document.getElementById("stat-failed").textContent   = d.failed;
  document.getElementById("stat-avg").textContent      = d.avg_score;
}

async function loadTimeline() {
  const r = await fetch("/api/timeline");
  const rows = await r.json();
  new Chart(document.getElementById("timeline-chart"), {
    type: "line",
    data: {
      labels: rows.map(r => r.day),
      datasets: [{
        label: "Applications",
        data: rows.map(r => r.count),
        borderColor: "#3b82f6",
        backgroundColor: "rgba(59,130,246,0.1)",
        fill: true,
        tension: 0.35,
        pointRadius: 3,
      }],
    },
    options: {
      ...CHART_DEFAULTS,
      plugins: { legend: { display: false } },
    },
  });
}

async function loadScoreDistribution() {
  const r = await fetch("/api/score-distribution");
  const d = await r.json();
  const labels = Object.keys(d);
  const colors = ["#ef4444", "#eab308", "#3b82f6", "#22c55e"];
  new Chart(document.getElementById("score-chart"), {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Jobs",
        data: Object.values(d),
        backgroundColor: colors,
        borderRadius: 6,
      }],
    },
    options: {
      ...CHART_DEFAULTS,
      plugins: { legend: { display: false } },
    },
  });
}

async function loadPlatforms() {
  const r = await fetch("/api/platforms");
  const rows = await r.json();
  const colors = ["#3b82f6", "#a855f7", "#22c55e", "#eab308", "#ef4444"];
  new Chart(document.getElementById("platform-chart"), {
    type: "doughnut",
    data: {
      labels: rows.map(r => r.platform),
      datasets: [{
        data: rows.map(r => r.count),
        backgroundColor: colors.slice(0, rows.length),
        borderWidth: 0,
      }],
    },
    options: {
      plugins: { legend: { labels: { color: "#6b7280" } } },
    },
  });
}

async function loadTopCompanies() {
  const r = await fetch("/api/top-companies?limit=10");
  const rows = await r.json();
  new Chart(document.getElementById("companies-chart"), {
    type: "bar",
    data: {
      labels: rows.map(r => r.company),
      datasets: [{
        label: "Applications",
        data: rows.map(r => r.count),
        backgroundColor: "#3b82f6",
        borderRadius: 6,
      }],
    },
    options: {
      ...CHART_DEFAULTS,
      indexAxis: "y",
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#6b7280", stepSize: 1 }, grid: { color: "#1f2232" } },
        y: { ticks: { color: "#6b7280" }, grid: { display: false } },
      },
    },
  });
}

let currentPage = 1;
let totalPages = 1;

async function loadApplications(page = 1) {
  const status   = document.getElementById("filter-status").value;
  const platform = document.getElementById("filter-platform").value;
  const params   = new URLSearchParams({ page, per_page: 20 });
  if (status)   params.set("status",   status);
  if (platform) params.set("platform", platform);

  const r = await fetch(`/api/applications?${params}`);
  const d = await r.json();

  currentPage = page;
  totalPages  = Math.ceil(d.total / 20) || 1;

  const tbody = document.getElementById("applications-tbody");
  tbody.innerHTML = d.items.map(a => {
    const date  = a.applied_at ? a.applied_at.slice(0, 10) : "—";
    const score = a.score != null
      ? `<span class="score-pill ${scoreClass(a.score)}">${a.score}</span>`
      : "—";
    const status = `<span class="badge badge-${a.status}">${a.status}</span>`;
    const link   = a.url ? `<a href="${a.url}" target="_blank">view</a>` : "—";
    return `<tr>
      <td>${date}</td>
      <td>${a.title}</td>
      <td>${a.company}</td>
      <td>${a.location || "—"}</td>
      <td>${a.platform}</td>
      <td>${score}</td>
      <td>${status}</td>
      <td>${link}</td>
    </tr>`;
  }).join("");

  renderPagination();
}

function renderPagination() {
  const el = document.getElementById("pagination");
  el.innerHTML = "";

  const prev = document.createElement("button");
  prev.textContent = "←";
  prev.disabled = currentPage === 1;
  prev.addEventListener("click", () => loadApplications(currentPage - 1));
  el.appendChild(prev);

  const start = Math.max(1, currentPage - 2);
  const end   = Math.min(totalPages, currentPage + 2);
  for (let p = start; p <= end; p++) {
    const btn = document.createElement("button");
    btn.textContent = p;
    if (p === currentPage) btn.classList.add("active");
    btn.addEventListener("click", () => loadApplications(p));
    el.appendChild(btn);
  }

  const next = document.createElement("button");
  next.textContent = "→";
  next.disabled = currentPage === totalPages;
  next.addEventListener("click", () => loadApplications(currentPage + 1));
  el.appendChild(next);
}

document.getElementById("filter-apply").addEventListener("click", () => loadApplications(1));

async function init() {
  await Promise.all([
    loadStats(),
    loadTimeline(),
    loadScoreDistribution(),
    loadPlatforms(),
    loadTopCompanies(),
    loadApplications(1),
  ]);
}

init();
