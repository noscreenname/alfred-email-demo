// Alfred — vanilla JS controller (4-tier comparison view).

const state = { selectedId: null };

const TIER_META = {
  none: {
    label: "No product",
    desc: "Agent sees only raw email text. No CRM, calendar, or classification.",
    level: 0,
  },
  uncontracted: {
    label: "Product, no contract",
    desc: "Data products exist but without formal governance. Agent accesses data blindly — no SLAs, no quality signals.",
    level: 1,
  },
  standard: {
    label: "Standard contract",
    desc: "ODCS-compliant data products with guaranteed schemas, field presence, and freshness SLAs.",
    level: 2,
  },
  agentic: {
    label: "Agentic contract",
    desc: "Full ODCS + agent-specific extensions: confidence thresholds, staleness checks, off-system detection.",
    level: 3,
  },
};

const TIER_ORDER = ["none", "uncontracted", "standard", "agentic"];

const ISSUE_LABELS = {
  inconsistency: "wrong decision",
  risk: "failure mode",
  gap: "knowledge gap",
  assumption: "false assumption",
};

function escapeHtml(s) {
  return (s ?? "").toString()
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

async function loadEmail(id) {
  state.selectedId = id;
  document.querySelectorAll(".inbox-row").forEach((r) => {
    r.classList.toggle("selected", r.dataset.id === id);
  });
  const res = await fetch(`/api/email/${id}/compare`);
  const data = await res.json();
  renderDetail(data);
  renderComparison(data);
}

function renderDetail(data) {
  const e = data.email;
  document.getElementById("email-detail").innerHTML = `
    <div class="email-header">
      <h1>${escapeHtml(e.subject)}</h1>
      <div class="from">${escapeHtml(e.from_name)} &lt;${escapeHtml(e.from_email)}&gt;</div>
      <div class="from">${escapeHtml(e.received_at)}</div>
    </div>
    <div class="email-body">${escapeHtml(e.body)}</div>
  `;
}

function renderComparison(data) {
  const grid = document.getElementById("comparison-grid");
  let html = "";

  for (const tier of TIER_ORDER) {
    const meta = TIER_META[tier];
    const t = data.tiers[tier];
    const d = t.decision;
    const statusCls = d.status.toLowerCase();
    const issueCount = t.issues.length;

    // Signals used
    const signalsHtml = d.signals_used.length
      ? d.signals_used.map((s) => `<span class="signal-tag">${escapeHtml(s)}</span>`).join("")
      : '<span class="signal-tag none">none</span>';

    // Issues
    let issuesHtml = "";
    if (issueCount > 0) {
      issuesHtml = t.issues.map((i) => {
        const label = ISSUE_LABELS[i.type] || i.type;
        return `<div class="issue issue-${i.type}"><span class="issue-badge">${label}</span> ${escapeHtml(i.text)}</div>`;
      }).join("");
    } else {
      issuesHtml = '<div class="no-issues">All signals available — full guardrails active</div>';
    }

    // Tier level indicator
    const dots = Array.from({ length: 4 }, (_, i) =>
      `<span class="level-dot ${i <= meta.level ? "filled" : ""}"></span>`
    ).join("");

    html += `
      <div class="tier-card tier-${tier}">
        <div class="tier-header">
          <div class="tier-level">${dots}</div>
          <h3>${meta.label}</h3>
          <p class="tier-desc">${meta.desc}</p>
        </div>
        <div class="decision-card ${statusCls}">
          <div class="decision-status ${statusCls}">${escapeHtml(d.status)}</div>
          <div class="decision-reason">${escapeHtml(d.reason)}</div>
          <div class="decision-meta">
            <span>confidence ${d.confidence.toFixed(2)}</span>
            <span>signals: ${signalsHtml}</span>
          </div>
        </div>
        <div class="issues-section">
          <div class="issues-header">${issueCount > 0 ? `${issueCount} issue${issueCount > 1 ? "s" : ""} detected` : "No issues"}</div>
          ${issuesHtml}
        </div>
      </div>
    `;
  }
  grid.innerHTML = html;
}

function wire() {
  document.querySelectorAll(".inbox-row").forEach((r) => {
    r.addEventListener("click", () => loadEmail(r.dataset.id));
  });

  const refreshBtn = document.getElementById("refresh-btn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", async () => {
      await fetch("/api/refresh");
      if (state.selectedId) loadEmail(state.selectedId);
    });
  }

  const firstId = document.body.dataset.firstId;
  if (firstId) loadEmail(firstId);
}

document.addEventListener("DOMContentLoaded", wire);
