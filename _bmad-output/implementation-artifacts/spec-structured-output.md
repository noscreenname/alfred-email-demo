---
title: 'Structured JSON output + comparison table UI'
type: 'feature'
created: '2026-04-22'
status: 'done'
baseline_commit: '4d1f870'
context:
  - _bmad-output/planning-artifacts/sprint-change-proposal-2026-04-22.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The 3-level output uses free-form markdown, producing visually similar recaps. The classification differences that prove the thesis are invisible without careful reading.

**Approach:** Change agent output to structured JSON with per-email classification and reasoning. Render as a comparison table where one row = one email, three columns = three levels, color-coded by classification. Rows where levels disagree are highlighted. Reasoning is expandable per cell.

## Boundaries & Constraints

**Always:**
- Same system prompt for all 3 levels (content changes but structure is identical)
- JSON output must include: summary, stats, and per-email classification with reasoning
- Comparison table must show all emails with color-coded classifications
- Rows where classifications differ across levels must be visually highlighted
- Keep existing: metrics bar (tokens, time, data KB), raw data toggle
- Data pipeline, data files, and contract are unchanged

**Ask First:**
- Changing the classification categories (currently: require_action, informatif, notification)
- Adding new fields to the JSON output schema

**Never:**
- Don't change data files or build_product.py
- Don't change the data contract
- Don't remove metrics or raw data toggle

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | 3 levels return valid JSON | Comparison table with color-coded cells, summary row, expandable reasoning | N/A |
| Classification differs | L1 says "notification", L3 says "require_action" for same email | Row is highlighted, both cells show their classification | N/A |
| All levels agree | Same classification for an email | Row shown normally, no highlight | N/A |
| JSON parse failure | LLM returns malformed JSON | Fallback: show raw text in that level's column | Catch JSON error, render raw |
| Different email counts | L1 classifies 50 emails, L2 only 15 (mock data) | Table shows union of all emails, missing classifications shown as "—" | N/A |

</frozen-after-approval>

## Code Map

- `prompts/system.md` -- rewrite: return JSON with summary, stats, emails[{subject, sender, classification, reasoning}]
- `alfred_agent.py` -- parse JSON from LLM response, fallback to raw text
- `main.py` -- pass structured results, compute diff highlights across levels
- `templates/index.html` -- comparison table: summary row + email rows with color-coded classifications + expandable reasoning
- `static/style.css` -- color coding, diff highlights, reasoning panels

## Tasks & Acceptance

**Execution:**
- [x] `prompts/system.md` -- Rewrite system prompt to return structured JSON output with summary, stats object, and emails array with classification and reasoning per email
- [x] `alfred_agent.py` -- Parse JSON from LLM response. Extract summary, stats, emails. Fallback to raw text display on parse failure.
- [x] `main.py` -- Build comparison data structure: match emails across levels by subject/sender, compute diff flags (where classifications disagree), pass to template
- [x] `templates/index.html` -- Complete rewrite: summary+stats row per level at top, then comparison table body with one row per email, 3 classification cells, expandable reasoning, keep metrics bar and raw data toggle
- [x] `static/style.css` -- Color coding (green=require_action, amber=informatif, grey=notification), diff row highlighting, reasoning toggle panels

**Acceptance Criteria:**
- Given all 3 levels return valid JSON, when the page renders, then a comparison table shows one row per email with 3 color-coded classification cells
- Given Level 1 classifies an email as "notification" and Level 3 as "require_action", when viewing the table, then that row is visually highlighted as a difference
- Given the user clicks a classification cell, when the reasoning panel expands, then the agent's reasoning for that classification is visible
- Given one level returns malformed JSON, when the page renders, then that level shows raw text while the other two render as structured table

## Verification

**Commands:**
- `uvicorn main:app --port 8000` -- expected: server starts, GET / returns 200

**Manual checks:**
- Run Alfred, verify comparison table renders with color-coded cells
- Find a row where classifications differ — verify it's highlighted
- Click a cell to expand reasoning — verify reasoning text appears
- Check metrics bar and raw data toggle still work
