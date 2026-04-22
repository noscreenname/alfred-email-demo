---
title: 'Alfred MVP — 3-level maturity comparison research rig'
type: 'feature'
created: '2026-04-22'
status: 'draft'
context:
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/prd.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** There is no concrete way to show that data contracts improve agent context quality. Architecture diagrams are abstract — a conference audience needs to see the same agent produce visibly different output when given raw data vs contract-enriched data.

**Approach:** Build a minimal web app (FastAPI + Jinja2, no JS) where the user picks a time period, triggers the same email agent 3 times with different data packaging (Level 1: raw files, Level 2: curated product, Level 3: product + ODCS contract), and sees 3 stacked recaps on one page. The differences in output quality — especially cross-source context like "sender has open deal in CRM" — prove the thesis visually.

## Boundaries & Constraints

**Always:**
- Same system prompt for all 3 levels. The agent must not know which level it runs at.
- Level 2 and Level 3 share identical `inbox-product.json`. Level 3 adds only `contract.yaml`.
- LLM output is markdown, injected directly into Jinja2 template. No parsing.
- Temperature 0 for reproducibility.
- Pure server-side rendering. No JavaScript.
- If one level's LLM call fails, render the others and show an error for the failed one.

**Ask First:**
- Any change to the system prompt structure (the 4-section recap format).
- Adding client-side JavaScript for any reason.
- Changing the mock data scenarios after initial creation.

**Never:**
- No caching layer (deferred to post-MVP).
- No client-side JS, no HTMX, no fetch calls.
- No database. No SQLite.
- No reuse of existing `agent/`, `contract/`, `storage/` modules — they serve the old two-mode architecture.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | User selects "week", submits form | Page renders 3 stacked recaps (L1, L2, L3) with visible differences in classification | N/A |
| CRM miss scenario | Email from client with open deal | L1: classifies as Informatif (can't cross-ref). L3: Require Action with CRM context | N/A |
| Calendar conflict | Email requesting meeting at conflicting time | L1: misses conflict. L3: flags conflict in context | N/A |
| One LLM call fails | API error on Level 2 call | L1 and L3 render normally. L2 shows error message in its block | Catch per-level, render partial |
| All LLM calls fail | API key invalid or network down | All 3 blocks show error messages. Page still renders with form | Catch all, render error blocks |
| Missing data file | `data/level-1/gmail.json` deleted | App fails to start with clear error naming missing file | Startup validation |

</frozen-after-approval>

## Code Map

- `main.py` -- FastAPI app: GET / (form), POST /run (trigger pipeline, render results)
- `agent.py` -- load_context(level, period) + run_agent(system_prompt, context) → markdown
- `prompts/system.md` -- shared system prompt (Alfred recap instructions)
- `templates/index.html` -- form + 3 vertically stacked recap blocks with CSS classes per level
- `static/style.css` -- visual differentiation per level, screenshot-ready layout
- `data/level-1/gmail.json` -- raw Gmail API response (~15-20 threads)
- `data/level-1/calendar.json` -- raw Calendar API response
- `data/level-1/crm.csv` -- raw CRM export
- `data/level-1/trello.json` -- raw Trello API response
- `data/level-2/inbox-product.json` -- pre-joined curated dataset
- `data/level-3/inbox-product.json` -- identical to level-2
- `data/level-3/contract.yaml` -- ODCS contract with schema, quality rules, taxonomy
- `requirements.txt` -- fastapi, uvicorn, jinja2, anthropic, python-dotenv, pyyaml
- `.env.example` -- ANTHROPIC_API_KEY template

## Tasks & Acceptance

**Execution:**
- [ ] `data/level-1/*` -- Create 4 raw mock data files (gmail.json, calendar.json, crm.csv, trello.json) with ~15-20 email threads including the 3 must-have scenarios (CRM miss, calendar conflict, unknown sender)
- [ ] `data/level-2/inbox-product.json` -- Create pre-joined curated dataset from the same underlying data. Each email record includes contact info, related tasks, calendar context.
- [ ] `data/level-3/inbox-product.json` -- Copy level-2 product verbatim
- [ ] `data/level-3/contract.yaml` -- Create ODCS contract: schema definition, quality rules, taxonomy mapping (email.author = contacts.email = trello.assignee), lifecycle, ownership, SLA
- [ ] `prompts/system.md` -- Write system prompt per architecture doc (4-section recap: Recap, Require Action, Stats, Everything Else)
- [ ] `agent.py` -- Implement load_context(level, period) that reads appropriate data directory and formats prompt context string. Implement run_agent(system_prompt, context) that calls Anthropic API with temperature 0.
- [ ] `main.py` -- FastAPI app with GET / (render form) and POST /run (loop through 3 levels, call agent, render template with results). Startup validation for required data files.
- [ ] `templates/index.html` -- Jinja2 template: time period form (day/week/month) + 3 stacked recap blocks. Each block has a level header and renders markdown content. CSS class per level for visual differentiation.
- [ ] `static/style.css` -- Minimal screenshot-ready styling. Level 1/2/3 get progressively richer visual treatment (e.g., subtle background tint, annotation styling). No chrome, no sidebar.
- [ ] `requirements.txt` -- Pin dependencies: fastapi, uvicorn[standard], jinja2, anthropic, python-dotenv, pyyaml, markdown
- [ ] `.env.example` -- Template with ANTHROPIC_API_KEY placeholder

**Acceptance Criteria:**
- Given a valid ANTHROPIC_API_KEY in .env, when user runs `pip install -r requirements.txt && uvicorn main:app` and opens localhost:8000, then the form page loads
- Given the form is submitted with "week" selected, when the pipeline completes (~30s), then 3 vertically stacked recaps appear on the page
- Given the CRM miss scenario in mock data, when comparing Level 1 and Level 3 output, then Level 3's Require Action section includes the email with CRM context that Level 1 classified as Informatif or Notification
- Given one LLM call fails, when the page renders, then the failed level shows an error message and the other two levels render normally

## Verification

**Commands:**
- `pip install -r requirements.txt` -- expected: all deps install without error
- `uvicorn main:app --port 8000` -- expected: server starts, GET / returns 200

**Manual checks:**
- Open localhost:8000, submit form with "week" — 3 stacked recaps render
- Compare Level 1 vs Level 3 output for the CRM miss scenario — Level 3 should show cross-source context Level 1 missed
- Screenshot the full page — should be slide-ready without post-processing
