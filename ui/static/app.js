// Alfred — vanilla JS controller.

const state = {
  mode: document.body.dataset.mode || "standard",
  selectedId: null,
};

function setModeButtons() {
  document.querySelectorAll("[data-mode-btn]").forEach((b) => {
    b.classList.toggle("active", b.dataset.modeBtn === state.mode);
  });
}

async function loadEmail(id) {
  state.selectedId = id;
  document.querySelectorAll(".inbox-row").forEach((r) => {
    r.classList.toggle("selected", r.dataset.id === id);
  });
  const res = await fetch(`/api/email/${id}?mode=${state.mode}`);
  const data = await res.json();
  renderDetail(data);
  renderDecision(data);
}

function escapeHtml(s) {
  return (s ?? "").toString()
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

function renderDetail(data) {
  const e = data.email;
  const el = document.getElementById("email-detail");
  el.innerHTML = `
    <div class="email-header">
      <h1>${escapeHtml(e.subject)}</h1>
      <div class="from">${escapeHtml(e.from_name)} &lt;${escapeHtml(e.from_email)}&gt;</div>
      <div class="from">${escapeHtml(e.received_at)}</div>
    </div>
    <div class="email-body">${escapeHtml(e.body)}</div>
  `;
}

function signalRow(name, value, present) {
  const icon = present ? "✓" : "✗";
  const cls = present ? "present" : "missing";
  const displayValue = present
    ? escapeHtml(typeof value === "object" ? JSON.stringify(value) : String(value))
    : "not in contract";
  return `<div class="signal-row ${cls}">
    <div class="icon">${icon}</div>
    <div class="name">${escapeHtml(name)}</div>
    <div class="value">${displayValue}</div>
  </div>`;
}

function renderDecision(data) {
  const el = document.getElementById("decision-panel");
  const d = data.decision;
  const statusCls = d.status.toLowerCase();
  const views = data.contract_views;
  const fields = data.contract_fields;

  // Build signals panel.
  const sections = [];
  const domains = [
    { label: "Email", view: views.email, all: fields.email, extOnly: fields.email_extended_only },
    { label: "Calendar", view: views.calendar, all: fields.calendar, extOnly: fields.calendar_extended_only },
    { label: "CRM", view: views.crm || {}, all: fields.crm, extOnly: fields.crm_extended_only },
  ];
  for (const dom of domains) {
    const rows = [];
    for (const f of dom.all) {
      const v = dom.view ? dom.view[f] : undefined;
      const present = v !== null && v !== undefined && v !== "";
      rows.push(signalRow(f, v, present));
    }
    sections.push(`<h3>${dom.label} signals</h3>${rows.join("")}`);
  }

  const draftBlock = d.draft_reply
    ? `<div class="draft-reply"><strong>Draft reply:</strong>\n\n${escapeHtml(d.draft_reply)}</div>`
    : "";

  let calloutBlock = "";
  if (state.mode === "standard" && d.signals_missing && d.signals_missing.length > 0) {
    calloutBlock = `<div class="missing-callout" id="upgrade-callout">
      In <strong>extended mode</strong>, ${d.signals_missing.length} additional signal(s)
      would have changed this decision: <em>${d.signals_missing.map(escapeHtml).join(", ")}</em>.
      <br><small>Click to toggle extended mode for this email.</small>
    </div>`;
  }

  el.innerHTML = `
    <div class="decision-card ${statusCls}">
      <div class="decision-status ${statusCls}">${escapeHtml(d.status)}</div>
      <div class="decision-reason">${escapeHtml(d.reason)}</div>
      <div class="decision-confidence">confidence=${d.confidence.toFixed(2)} · signals_used=[${d.signals_used.map(escapeHtml).join(", ")}]</div>
      ${draftBlock}
    </div>
    <div class="signals-panel">${sections.join("")}</div>
    ${calloutBlock}
  `;

  const callout = document.getElementById("upgrade-callout");
  if (callout) {
    callout.addEventListener("click", () => {
      state.mode = "extended";
      setModeButtons();
      loadEmail(state.selectedId);
    });
  }
}

function wire() {
  setModeButtons();

  document.querySelectorAll("[data-mode-btn]").forEach((b) => {
    b.addEventListener("click", () => {
      state.mode = b.dataset.modeBtn;
      setModeButtons();
      if (state.selectedId) loadEmail(state.selectedId);
    });
  });

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
