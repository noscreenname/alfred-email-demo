---
title: 'Alfred — data contract transparency demo'
type: 'feature'
created: '2026-04-15'
status: 'done'
context: []
baseline_commit: 'd8b019685026f20fcdcb6e0bbd54060a4d33420e'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** There is no visceral way to show non-technical stakeholders how agent-specific metadata (beyond ODCS v3.1 standard fields) changes an email agent's decisions. Pitching "data contracts for agents" in slides is abstract; the gap only becomes real when you see the same email routed differently under two contract modes.

**Approach:** Build Alfred — a FastAPI + Jinja2 demo that loads local JSON mock inboxes / calendar / CRM, wraps each source in a `ContractView` object produced by a contract layer operating in one of two modes (`standard` mirroring ODCS v3.1; `extended` adding agent signals like `classification_confidence`, `off_system_refs`, `data_age_minutes`, `crm_open_deal`), runs a pure-Python rule-based decision engine over those views, and exposes a three-column UI that makes the presence *and absence* of each signal visible. A mode toggle re-runs the decision on the selected email, so the user sees ACT→ESCALATE flips in place.

## Boundaries & Constraints

**Always:**
- Contract layer is a distinct module. Decision engine reads only `EmailContractView` / `CalendarContractView` / `CrmContractView` — never raw dicts, never a `mode` flag. In standard mode, extended fields on the view must be `None`, and decision rules that depend on them simply do not fire.
- Raw JSON data files contain no contract signals; signals are computed at view-construction time.
- Classification results are cached in SQLite keyed by `sha256(message_id + body[:200])` so mode toggles and refreshes never re-call Claude.
- Every rendered decision is fully traceable to its `signals_used` / `signals_missing` lists.
- Use models `claude-haiku-4-5-20251001` (classifier) and `claude-sonnet-4-6` (responder) via the official `anthropic` SDK.
- No frontend framework, no build step, no external APIs beyond Anthropic.

**Ask First:**
- Any deviation from the two-mode architecture (e.g. a third mode, a hybrid flag).
- Introducing real Gmail/Calendar/CRM API calls.
- Changing the dataset generation scheme after it is committed.

**Never:** real provider APIs; LLM-driven decision logic (decision engine is pure Python rules); re-calling the classifier on a cached message; storing contract signals inside `data/emails.json`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| VIP sender, standard mode | email from `sender_tier: vip` contact | ESCALATE — reason "VIP sender — routing to account owner"; `signals_used=[sender_tier]` | N/A |
| Open-deal contact, standard mode | routine-looking email from contact with `deals[]` containing `stage: negotiation` | ACT — drafts reply (standard cannot see `crm_open_deal`); `signals_missing=[crm_open_deal, deal_stage]` | N/A |
| Same email, extended mode | same message, mode toggled | ESCALATE — reason "Active deal in negotiation — autonomous reply suppressed"; `signals_used=[crm_open_deal, deal_stage]` | N/A |
| Off-system refs, standard | body contains "as we discussed", label `proposal-confirmation` | ACT (cannot see `off_system_refs`); `signals_missing=[off_system_refs, thread_complete]` | N/A |
| Off-system refs, extended | same email | ESCALATE — "Email references off-system context — cannot verify prior commitment" | N/A |
| Low-confidence classification, extended | `classification_confidence < 0.75` | ESCALATE — confidence-below-threshold reason | N/A |
| Stale calendar + meeting request, extended | `data_age_minutes > 10`, label `meeting-request` | ESCALATE — "Calendar data is {n} minutes old" | N/A |
| Unknown sender, internal label | no CRM match, label `internal` or `newsletter` | INFORM (no draft reply) | N/A |
| Routine email, standard | low-stakes invoice/support, no escalation triggers | ACT — responder called, reply cached in action log | Anthropic API error → surface as ESCALATE with reason "classifier/responder unavailable" |
| Classifier cache hit | second load of same message | No Anthropic call; result pulled from SQLite | N/A |
| Mode toggle on selected email | user clicks Extended | Re-run decision + signals panel; call responder only if new decision is ACT and no draft cached for this mode | N/A |

</frozen-after-approval>

## Code Map

- `generate_datasets.py` -- emits `data/emails.json` (~250), `data/calendar.json` (~120), `data/crm_contacts.json` (30) per distributions in intent; deterministic seed for reproducibility.
- `data/contracts/*.yaml` -- six ODCS v3.1-shaped contracts (email/calendar/crm × standard/extended). Extended files annotate each new field with `agent_specific: true` + `rationale:` and end with a comment block listing additions vs. standard.
- `config.py` -- loads `.env`; exposes `CONTRACT_MODE`, `CONFIDENCE_THRESHOLD`, `CALENDAR_STALENESS_THRESHOLD_MINUTES`, `OFF_SYSTEM_PATTERNS`, `ANTHROPIC_API_KEY`, `GMAIL_MAX_MESSAGES`, `CALENDAR_DAYS_AHEAD`.
- `contract/loader.py` -- reads YAML contracts, exposes field lists per (domain, mode).
- `contract/email_contract.py` -- `build_email_view(raw, mode, classification, off_system_patterns, thread_index) -> EmailContractView` (dataclass). Extended fields set to `None` when `mode=="standard"`.
- `contract/calendar_contract.py` -- `build_calendar_view(events, mode, loaded_at) -> CalendarContractView`; `data_age_minutes`/`safe_to_act` populated only in extended mode.
- `contract/crm_contract.py` -- `build_crm_view(contact, mode) -> CrmContractView | None`; `crm_open_deal`/`deal_stage`/`deal_owner` only extended.
- `agent/classifier.py` -- Anthropic Haiku call returning `{label, confidence, reasoning}`; SQLite-cached by body hash.
- `agent/responder.py` -- Anthropic Sonnet call; takes full `EmailContractView` + `AlfredDecision`; returns reply text. Cached per `(message_id, mode)`.
- `agent/decision.py` -- pure rules over `ContractView` objects; returns `AlfredDecision(status, draft_reply, reason, signals_used, signals_missing, confidence)`. Each rule declares its `signals_missing_in_standard_mode` list so the dataclass can populate that field architecturally.
- `storage/db.py` -- SQLite init, classification cache table, action log table, response cache table.
- `main.py` -- FastAPI app: `GET /` (index), `GET /email/{id}?mode=` (JSON fragment for decision card), `POST /mode` (sets session mode + returns re-rendered HTMX-style partial), `GET /log`, `GET /refresh`. Loads datasets at startup.
- `ui/templates/index.html` -- three-column layout per intent; uses fetch() in `app.js` to re-render email detail + decision column on select/mode-toggle.
- `ui/templates/log.html` -- filterable action-log table.
- `ui/static/style.css` -- palette `#f7f5f0 / #fff / #E24B4A / #EF9F27 / #639922`, 0.5px borders, no shadows/gradients.
- `ui/static/app.js` -- vanilla JS for row-select, mode-toggle, fetch + DOM swap.
- `requirements.txt`, `.env.example`, `README.md`.

## Tasks & Acceptance

**Execution:**
- [x] `requirements.txt`, `.env.example` -- pin deps (`fastapi`, `uvicorn[standard]`, `jinja2`, `anthropic`, `pyyaml`, `python-dotenv`); document env vars.
- [x] `config.py` -- load env; expose constants.
- [x] `generate_datasets.py` -- deterministic generator for emails/calendar/CRM per distributions; writes under `data/`.
- [x] `data/contracts/*.yaml` -- author all six YAML contracts with ODCS v3.1 structure.
- [x] `contract/loader.py` + three `*_contract.py` -- view dataclasses + builders; mode gates extended fields to `None`.
- [x] `storage/db.py` -- SQLite schema + helpers for classification cache, response cache, action log.
- [x] `agent/classifier.py` -- Haiku call, JSON parse, cache read/write, graceful error → `label="ambiguous"`, `confidence=0.0`.
- [x] `agent/responder.py` -- Sonnet call, cache, graceful error.
- [x] `agent/decision.py` -- rule engine returning `AlfredDecision`; rules ordered per intent; `signals_missing` populated architecturally from the contract view, not from a mode flag.
- [x] `main.py` -- FastAPI routes, startup dataset load, per-request pipeline (classify → build views → decide → maybe respond → log).
- [x] `ui/templates/index.html`, `log.html`, `ui/static/style.css`, `ui/static/app.js` -- layout, palette, mode toggle, signals panel with present/missing rendering, decision card.
- [x] `README.md` -- setup, dataset generation, API key, UI walk-through, CRM extension notes.

**Acceptance Criteria:**
- Given a fresh checkout with `ANTHROPIC_API_KEY` set, when I run `python generate_datasets.py && python -m uvicorn main:app`, then `http://localhost:8000` loads the three-column UI with ≥50 emails.
- Given an email from a `sender_tier: vip` contact, when selected in either mode, then decision is ESCALATE with reason mentioning VIP.
- Given an email from a `standard-client` contact whose `deals` contains an active-stage entry, when selected in standard mode then Alfred ACTs and the signals-missing list includes `crm_open_deal`; when toggled to extended the decision flips to ESCALATE without reloading the page.
- Given an email whose body matches an `OFF_SYSTEM_PATTERNS` phrase and classifies as `proposal-confirmation`, when toggled standard↔extended, then ACT↔ESCALATE flip is visible and both runs are appended to the action log with their mode.
- Given the same email is viewed twice, when the page is refreshed, then the classifier cache is hit (no second Anthropic Haiku call; verifiable via a log line or cache row count).
- Given `CONTRACT_MODE="standard"`, when `decision.py` is grep'd, then it contains no reference to `mode`, `standard`, or `extended` — only reads view fields.

## Design Notes

Architectural invariant worth protecting: the decision engine must have no way to know which mode it is running under. It only sees view objects; extended fields are `None` in standard mode; rules that read them short-circuit naturally (`if view.crm_open_deal:` is falsy when `None`). The `signals_missing` list on each rule is a *static declaration* attached to the rule definition, not computed from runtime mode — so when a rule *would have fired but its signal was None*, the engine records those signal names in `signals_missing`. Sketch:

```python
RULES = [
    Rule(
        name="vip",
        predicate=lambda e, c, r: r and r.sender_tier == "vip",
        decide=lambda e, c, r: ("escalate", "VIP sender — routing to account owner", ["sender_tier"]),
        extended_signals=[],
    ),
    Rule(
        name="open_deal",
        predicate=lambda e, c, r: r and r.crm_open_deal and r.deal_stage in {"negotiation","renewal","at-risk"},
        decide=lambda e, c, r: ("escalate", f"Active deal in {r.deal_stage} — autonomous reply suppressed", ["crm_open_deal","deal_stage"]),
        extended_signals=["crm_open_deal","deal_stage"],
    ),
    ...
]
```

When a rule's predicate is false *because* its `extended_signals` are all `None` on the view, append those names to `signals_missing`. That is how the standard/extended contrast gets architecturally encoded without the engine inspecting a mode flag.

## Verification

**Commands:**
- `python generate_datasets.py` -- expected: writes `data/emails.json`, `data/calendar.json`, `data/crm_contacts.json` without error; counts ~250/~120/30.
- `python -c "from contract.email_contract import build_email_view; ..."` -- smoke-import all modules.
- `python -m uvicorn main:app --port 8000` -- expected: server boots, `GET /` returns 200.
- `grep -nE "standard|extended|mode" agent/decision.py` -- expected: no matches (architectural invariant).

**Manual checks:**
- Open `http://localhost:8000`, pick an open-deal email, toggle Standard↔Extended; decision card flips ACT→ESCALATE and the signals panel shows/hides extended rows.
- Open `/log`, filter by mode — confirm same message_id appears with different decisions under the two modes.

## Suggested Review Order

**Architectural core — the rule engine and its mode-blindness invariant**

- Entry point: how decisions are made and how "signals_missing" is computed from rules earlier than the chosen one — this is the demo's core claim.
  [`decision.py:178`](../../agent/decision.py#L178)

- Rule ordering is the priority order; each rule declares its `required_signals` statically.
  [`decision.py:167`](../../agent/decision.py#L167)

- `_all_signals_absent` routes each signal name to the right view without a mode flag.
  [`decision.py:60`](../../agent/decision.py#L60)

**Contract layer — where mode gating actually lives**

- Standard vs extended divergence: `classification_confidence`, `off_system_refs`, `thread_complete` are extended-only. `classification_label` is standard too (fix from review).
  [`email_contract.py:40`](../../contract/email_contract.py#L40)

- `data_age_minutes` / `safe_to_act` are extended-only; freshness is derived from the in-memory load timestamp.
  [`calendar_contract.py:19`](../../contract/calendar_contract.py#L19)

- `crm_open_deal` / `deal_stage` / `deal_owner` are extended-only; unknown senders yield `None` view.
  [`crm_contract.py:20`](../../contract/crm_contract.py#L20)

**Pipeline wiring**

- Classify → build views → decide → (maybe) draft → log, all gated on contract mode passed via query string.
  [`main.py:72`](../../main.py#L72)

- Classifier: Haiku call with SQLite cache (now separator-delimited key after review fix).
  [`classifier.py:28`](../../agent/classifier.py#L28)

- Responder: Sonnet call cached per `(message_id, contract_mode)` so mode toggles reuse drafts.
  [`responder.py:22`](../../agent/responder.py#L22)

**UI — the before/after visualization**

- Three-column layout; the signals panel treats absence as loudly as presence.
  [`index.html:1`](../../ui/templates/index.html#L1)

- Mode toggle + row click both re-fetch `/api/email/{id}?mode=…` and re-render detail + decision cards.
  [`app.js:1`](../../ui/static/app.js#L1)

**Supporting**

- Dataset generator (deterministic seed, approximate distributions per spec).
  [`generate_datasets.py:1`](../../generate_datasets.py#L1)

- Six ODCS v3.1 contract YAMLs — extended files annotate new fields with `agent_specific: true` + rationale.
  [`email_extended.yaml`](../../data/contracts/email_extended.yaml)

- SQLite schema: classification cache, response cache, action log.
  [`db.py:1`](../../storage/db.py#L1)

