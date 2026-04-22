---
title: "Sprint Change Proposal — Structured Output + Comparison Table"
date: "2026-04-22"
status: "approved"
scope: "moderate"
trigger: "3-level output looks too similar — differences invisible without careful reading"
---

# Sprint Change Proposal

## Issue Summary

The 3-level output uses free-form markdown, producing visually similar recaps across all levels. The differences in classification and reasoning — which prove the thesis — are invisible without careful reading. This undermines the core product goal: screenshot-ready evidence where differences are instantly legible.

## Recommended Approach: Structured Output + Comparison Table

Change the agent output from prose to structured JSON. Each email gets a classification and reasoning per level. Render as a comparison table where differences are color-coded.

## Detailed Changes

### 1. System prompt (`prompts/system.md`)

Agent returns JSON with summary, stats, and per-email classification with reasoning.

### 2. `alfred_agent.py`

- `run_agent()` parses JSON response
- Fallback to raw text on parse failure

### 3. `main.py`

- Pass structured results to template
- Compute diff highlights: where do classifications differ between levels?

### 4. `templates/index.html`

- Top row: Summary + stats per level (side by side)
- Comparison table: One row per email, 3 classification cells (color-coded)
- Rows where classifications differ are highlighted
- Expandable reasoning: Click any cell → see agent's reasoning

### 5. `static/style.css`

- Color coding: green = Require Action, yellow = Informatif, grey = Notification
- Highlight rows with classification differences
- Expandable reasoning panel styling

## Impact on Artifacts

| Artifact | Change | Scope |
|----------|--------|-------|
| PRD FR6 | Output format: markdown → structured JSON | Minor |
| Architecture — LLM output | Markdown → JSON with parsing | Medium |
| System prompt | Complete rewrite | Medium |
| Template | Complete rewrite — comparison table | Medium |
| Data pipeline | No change | None |

## Handoff

Scope: Moderate. Route to Quick Dev for implementation.
