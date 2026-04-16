// Alfred — agent output comparison view.

const state = { selectedId: null };

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
  const res = await fetch(`/api/email/${id}/agents`);
  const data = await res.json();
  renderDetail(data.email);
  renderAgents(data.agents, data.email);
}

function renderDetail(e) {
  const labels = (e.labels || []).map((l) =>
    `<span class="label-tag">${escapeHtml(l)}</span>`
  ).join("");
  document.getElementById("email-detail").innerHTML = `
    <div class="email-header">
      <h1>${escapeHtml(e.subject)}</h1>
      <div class="from">${escapeHtml(e.sender)}</div>
      <div class="from">${escapeHtml(e.date)}</div>
      <div class="email-labels">${labels}</div>
      <div class="email-meta-row">
        <span>urgency: ${(e.urgency_score ?? 0).toFixed(2)}</span>
        <span>confidence: ${(e.classification_confidence ?? 0).toFixed(2)}</span>
        <span>purpose: ${escapeHtml(e.purpose)}</span>
        <span>thread: ${escapeHtml(e.thread_completeness)}</span>
        <span>constraint: ${escapeHtml(e.handling_constraint)}</span>
      </div>
    </div>
    <div class="email-body">${escapeHtml(e.body)}</div>
  `;
}

function renderAgents(agents, email) {
  const grid = document.getElementById("agents-grid");

  const agentPairs = [
    {
      label: "EMAIL_A",
      desc: "Email triage & response agent",
      with_key: "email_a_contract",
      without_key: "email_a_no_contract",
    },
    {
      label: "AGENDA_A",
      desc: "Scheduling & calendar agent",
      with_key: "agenda_a_contract",
      without_key: "agenda_a_no_contract",
    },
  ];

  let html = "";
  for (const pair of agentPairs) {
    const withData = agents[pair.with_key];
    const withoutData = agents[pair.without_key];

    // Skip AGENDA_A section entirely if both are SKIP
    if (pair.label === "AGENDA_A"
        && withData?.output?.decision === "SKIP"
        && withoutData?.output?.decision === "SKIP") {
      continue;
    }

    html += `<div class="agent-section">
      <div class="agent-section-header">
        <h2>${pair.label}</h2>
        <span class="agent-desc">${pair.desc}</span>
      </div>
      <div class="agent-pair">
        ${renderAgentPanel(withData, "With contract", "with-contract")}
        ${renderAgentPanel(withoutData, "Without contract", "no-contract")}
      </div>
    </div>`;
  }

  if (!html) {
    html = '<div class="placeholder">No agent outputs available for this email.</div>';
  }
  grid.innerHTML = html;
}

function renderAgentPanel(data, modeLabel, modeCls) {
  if (!data) {
    return `<div class="agent-panel ${modeCls}">
      <div class="panel-header"><h3>${modeLabel}</h3></div>
      <div class="placeholder">No data</div>
    </div>`;
  }

  const d = data.output;
  const logic = data.decision_logic;
  const statusCls = d.decision.toLowerCase();

  // Decision badge
  const decisionHtml = `<div class="decision-badge ${statusCls}">${escapeHtml(d.decision)}</div>`;

  // Reason
  const reasonHtml = `<div class="decision-reason">${escapeHtml(d.reason)}</div>`;

  // Signals
  const signalsUsed = (logic.signals_used || []).map((s) =>
    `<span class="signal-tag used">${escapeHtml(s)}</span>`
  ).join("") || '<span class="signal-tag none">none</span>';

  const signalsMissing = (logic.signals_missing || []).map((s) =>
    `<span class="signal-tag missing">${escapeHtml(s)}</span>`
  ).join("");

  // Warnings
  const warningsHtml = (logic.warnings || []).map((w) =>
    `<div class="warning-row">${escapeHtml(w)}</div>`
  ).join("");

  // Trace
  const traceHtml = (logic.trace || []).map((t) =>
    `<div class="trace-row">${escapeHtml(t)}</div>`
  ).join("");

  // Draft reply
  let draftHtml = "";
  if (d.draft_reply) {
    draftHtml = `<div class="draft-section">
      <div class="draft-label">Draft reply</div>
      <div class="draft-body">${escapeHtml(d.draft_reply)}</div>
    </div>`;
  }

  // Proposed slots (AGENDA_A)
  let slotsHtml = "";
  if (d.proposed_slots && d.proposed_slots.length > 0) {
    const slots = d.proposed_slots.map((s) =>
      `<div class="slot-row">${escapeHtml(s.date)} ${escapeHtml(s.time)} — ${escapeHtml(s.rationale)}</div>`
    ).join("");
    const excluded = (d.excluded_slots || []).map((s) =>
      `<div class="slot-row excluded">${escapeHtml(s.date)} ${s.time ? escapeHtml(s.time) : ""} — ${escapeHtml(s.reason)}</div>`
    ).join("");
    slotsHtml = `<div class="slots-section">
      <div class="slots-label">Proposed slots</div>
      ${slots}
      ${excluded ? `<div class="slots-label excluded-label">Excluded</div>${excluded}` : ""}
    </div>`;
  }

  // Contact & reference context
  let contextHtml = "";
  if (data.contact) {
    const c = data.contact;
    contextHtml += `<div class="context-row">Contact: ${escapeHtml(c.name)} (${escapeHtml(c.relationship_type)}, ${escapeHtml(c.temporal_importance)}, policy=${escapeHtml(c.auto_reply_policy)})</div>`;
  }
  if (data.reference) {
    const r = data.reference;
    contextHtml += `<div class="context-row">Topic: ${escapeHtml(r.topic_name)} (${escapeHtml(r.context_completeness || "")}, threshold=${escapeHtml(r.action_threshold)})</div>`;
  }

  return `<div class="agent-panel ${modeCls}">
    <div class="panel-header">
      <h3>${modeLabel}</h3>
      ${decisionHtml}
    </div>
    ${reasonHtml}
    ${contextHtml ? `<div class="context-section">${contextHtml}</div>` : ""}
    <div class="signals-section">
      <div class="signals-label">Signals used</div>
      <div class="signals-list">${signalsUsed}</div>
      ${signalsMissing ? `<div class="signals-label missing-label">Signals missing</div><div class="signals-list">${signalsMissing}</div>` : ""}
    </div>
    ${warningsHtml ? `<div class="warnings-section"><div class="warnings-label">Warnings</div>${warningsHtml}</div>` : ""}
    ${draftHtml}
    ${slotsHtml}
    <details class="trace-details">
      <summary>Decision trace</summary>
      <div class="trace-body">${traceHtml}</div>
    </details>
  </div>`;
}

function selectOffset(delta) {
  const rows = [...document.querySelectorAll(".inbox-row")];
  if (!rows.length) return;
  const idx = rows.findIndex((r) => r.dataset.id === state.selectedId);
  const next = Math.max(0, Math.min(rows.length - 1, idx + delta));
  const row = rows[next];
  loadEmail(row.dataset.id);
  row.scrollIntoView({ block: "nearest" });
}

function wire() {
  document.querySelectorAll(".inbox-row").forEach((r) => {
    r.addEventListener("click", () => loadEmail(r.dataset.id));
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); selectOffset(1); }
    if (e.key === "ArrowUp") { e.preventDefault(); selectOffset(-1); }
  });

  const firstId = document.body.dataset.firstId;
  if (firstId) loadEmail(firstId);
}

document.addEventListener("DOMContentLoaded", wire);
