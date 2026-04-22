---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain-skipped', 'step-06-innovation', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish', 'step-12-complete']
inputDocuments:
  - docs/user-journeys.md
  - _bmad-output/implementation-artifacts/spec-alfred-transparency-demo.md
  - data/agentic-data-contract.yaml
documentCounts:
  briefs: 0
  research: 0
  brainstorming: 0
  projectDocs: 3
workflowType: 'prd'
classification:
  projectType: web_app (research visualization tool)
  domain: developer advocacy / proof of concept
  complexity: medium
  projectContext: brownfield
  designPrinciple: "Design for the screenshot — UI exists to produce compelling slide-ready evidence, not for daily use"
  evidenceStandard: "Compelling and credible, not rigorous methodology"
---

# Product Requirements Document - Alfred

**Author:** Andrey
**Date:** 2026-04-22

## Executive Summary

Alfred is a research visualization tool that produces empirical evidence for a conference talk on how data contracts improve agent context management. The tool runs the same email agent task — a concise daily/weekly/monthly inbox recap — across four data management maturity levels, generating side-by-side screenshots that show how output quality changes as the underlying data infrastructure matures.

The agent processes four data sources (Gmail, Calendar, Contacts/CRM, Trello tasks) and produces a structured recap: a summary, a stats bar (total, unread, responded, important), and a categorized email list (Action Required / Important / Notification). The user triggers each run manually via the UI, selects a time period, and compares results across maturity levels.

The tool is single-user, mock-data-first (with a path to real data), and designed to be run a handful of times to capture compelling evidence — not operated daily.

## What Makes This Special

The four-level maturity ladder turns "data contracts help agents" from an abstract claim into a visible progression:

- **Level 1 (Raw APIs):** Agent consumes data sources directly via API/MCP. All joins, filtering, and domain logic live in the prompt. Cross-source relationships are invisible. When things break, nobody owns the fix.
- **Level 2 (Data Product):** A curated dataset combines sources into structured, purpose-built fields with clear ownership and status. Relationships are explicit. Quality is unknown.
- **Level 3 (Data Contract):** An ODCS contract makes the product machine-readable and enforceable. Quality rules are explicit. Taxonomy is standardized across domains (email author = CRM client = Trello task owner). Implementation is abstracted — swapping Gmail for Outlook doesn't change the agent. Lifecycle is tracked.
- **Level 4 (Agent Contract):** Extends ODCS with agent-specific metadata (autonomy levels, capability maps, degraded-mode instructions). Parked for later, but architecturally accounted for.

The "aha" moment: Level 1's recap misses that an email sender is a client in active negotiation because the agent can't cross-reference Gmail with CRM. Level 3 catches it because the contract mapped the relationship. That's the screenshot that makes the talk land.

## Project Classification

- **Type:** Web application (research visualization tool)
- **Domain:** Developer advocacy / proof of concept
- **Complexity:** Medium — sophisticated domain concepts, bounded engineering scope
- **Context:** Brownfield — pivoting existing two-mode (standard/extended) demo to four-level maturity model
- **Design principle:** Design for the screenshot — UI exists to produce slide-ready evidence
- **Evidence standard:** Compelling and credible, not rigorous methodology

## Success Criteria

### User Success

- Alfred produces visibly different recap outputs at each maturity level (1–3) against the same mock dataset
- The Level 1 → Level 3 progression tells a self-evident story in screenshots — no narration needed to see the quality gap
- At least one concrete "aha" example where Level 1 makes an obviously wrong decision (e.g., misses that an email sender is a CRM client in active negotiation) and Level 3 catches it
- Screenshots survive the "cold colleague test": someone with zero context sees Level 1 vs Level 3 side-by-side and immediately says "I see why structure matters"

### Business Success (Talk Impact)

- The evidence preempts the skeptic's objection: "This is contrived. Real agents don't benefit from this overhead." The screenshots must show tangible degradation at Level 1, not just "prettier output" at Level 3.
- The core claim is singular and provable: data contracts improve agent context quality by making cross-source relationships explicit
- Generated material is sufficient to structure a compelling 15–20 minute talk section with concrete before/after evidence

### Technical Success

- Agent runs against mock data without errors at all maturity levels
- Same mock data, same time period across all levels — apples-to-apples comparison
- Screenshot mode: deterministic ordering, no loading spinners, no network dependency — works offline at a conference venue
- Clean data injection seam: mock data adapter and agent input have a defined interface so swapping mock → real Gmail/Calendar doesn't require rewriting the agent
- All 4 data sources represented in at least one level's output
- UI renders screenshot-ready output: survives 1024×768 projection, no tooltips or modals required to understand the content

### Measurable Outcomes

- 3 maturity levels (1–3) producing distinct recap outputs from the same dataset
- At least 2–3 "aha" screenshots where cross-source context changes the agent's decision
- UI polished enough for direct slide inclusion without post-processing
- Each maturity level has distinct visual density so the progression is instantly legible

## Product Scope

**MVP Strategy:** Validation MVP — prove that data management maturity visibly affects agent output quality before investing in anything else. If the 3-level progression doesn't produce compelling visual evidence, the talk premise needs rethinking.

**Resource Requirements:** Solo developer (Andrey). Existing FastAPI + Jinja2 codebase provides foundation. LLM API access (Anthropic) required for agent execution.

### MVP (Phase 1)

- 3 data adapters (raw API/CSV, curated product, ODCS contract) for the same underlying mock data from 4 sources (Gmail, Calendar, CRM, Trello)
- Same agent prompt, 3 sequential LLM calls with different context preparation
- Structured recap output: summary, stats bar, categorized email list (Action Required / Important / Notification)
- Day/week/month granularity picker
- Vertical stacked rendering (Level 1 → 2 → 3) with distinct visual density per level
- SQLite caching of agent outputs for instant re-rendering
- Screenshot mode: deterministic output, no spinners, offline-capable
- Mock datasets with enough cross-source complexity to stress Level 1

### Post-MVP (Phase 2)

- Level 4 (Agent Contract) — extends ODCS with agent-specific metadata
- Real data integration via MCP (Gmail, Calendar) through existing data adapter seam
- Prev/next period navigation
- Switchable toggle view for internal exploration

### Vision

- Removed. Ship the talk version. If audience demand emerges, revisit then.

### Risk Mitigation

**Technical Risk:** Agent compensates for poor data packaging — Level 1 output is indistinguishable from Level 3.
- *Mitigation:* Design mock data with ambiguous senders, multi-domain relationships, and tasks that only resolve with explicit cross-source mapping. If needed, constrain Level 1 agent prompt to not infer beyond what's explicitly provided.
- *Fallback:* "Data contracts matter less than expected for capable models" is still a valid, provocative talk.

**Resource Risk:** Solo developer, bounded scope. If time-constrained, Level 2 can be cut (Level 1 vs Level 3 binary comparison still proves the thesis).

## User Journeys

### Journey 1 — Andrey generates the evidence

**Who:** Andrey, data engineering professional preparing a conference talk on data contracts for agent context management. Needs concrete proof that the theory holds.

**Opening Scene:** Andrey has architecture diagram slides explaining data contracts. Technically correct but abstract. He needs visceral before/after evidence. He opens Alfred.

**Rising Action:**
1. Selects a time period (last week) and triggers Alfred
2. The same agent runs three times against the same underlying data, but with different data-fetching approaches:
   - **Level 1:** Agent fetches raw data via API calls / CSV extracts. Gets Gmail messages, calendar JSON, CRM CSV, Trello export. Has to infer relationships, handle joins, parse schemas on its own.
   - **Level 2:** Agent receives a curated data product — pre-joined, purpose-built fields, clear ownership. Relationships are explicit but no formal quality guarantees.
   - **Level 3:** Agent receives data through an ODCS contract — machine-readable schema, enforced quality rules, standardized taxonomy (email.author = contacts.email = trello.assignee), lifecycle metadata.
3. Three recaps appear stacked vertically. Each shows: summary, stats, categorized emails (Action Required / Important / Notification).
4. Andrey scrolls through the progression. Level 1's recap looks reasonable but flat — it treated a client-in-negotiation email as routine because it couldn't reliably join the CRM CSV to the email sender. Level 3 caught it because the contract mapped the relationship explicitly.

**Climax:** The data was always there. The contract is what made it usable. Andrey screenshots the stack.

**Resolution:** Andrey has 2–3 screenshots showing the progression. He restructures the talk around the evidence — the maturity ladder tells itself visually. He has concrete data points: Level 1 miscategorized X emails, Level 3 caught Y cross-source relationships using the same underlying data.

**What could go wrong:**
- All three levels produce nearly identical output → the agent is smart enough to infer relationships from raw CSVs anyway, thesis weakened. Andrey adjusts mock data complexity or agent prompt constraints to make the difference emerge.
- Level 2 and Level 3 outputs are too similar → the contract layer doesn't add enough over the curated product. May need to rethink what Level 3 specifically enables.

### Journey Requirements Summary

This journey maps to FR1–FR18 across all five capability areas: Data Management, Agent Execution, Time Period Selection, Results Visualization, and Screenshot Readiness.

## Innovation & Novel Patterns

### Detected Innovation Areas

- **Cross-domain bridge:** Connecting data contract methodology (traditionally a data engineering concern) to agent context management (traditionally an AI engineering concern). Neither community is making this connection explicitly.
- **Maturity ladder as teaching device:** Moving beyond binary "contracts vs no contracts" to a graduated progression where each level's specific contribution is visible and attributable.
- **Evidence-first advocacy:** Using empirical agent output comparison rather than architecture diagrams to make the case for data contracts.

### Validation Approach

- Run the same agent against the same data at all maturity levels and compare output quality
- If outputs don't meaningfully differ, the thesis is invalidated before going on stage — honest failure mode built into the tool

### Risk Mitigation

- **Risk:** Modern LLMs compensate for messy inputs — Level 1 output may be "good enough" to undermine the progression
- **Mitigation:** Design mock data with sufficient cross-source complexity (ambiguous senders, multi-domain relationships, tasks that only make sense with CRM context) so raw inference genuinely struggles
- **Fallback:** If the progression doesn't emerge naturally, this is a finding in itself — "data contracts matter less than we thought for capable models" is an honest and provocative talk conclusion

## Web App Specific Requirements

### Project-Type Overview

Single-page research visualization tool. Localhost only, single user, no auth, no SEO, no cross-browser concerns. The web layer exists to trigger the agent and render results for screenshotting.

### Technical Architecture Considerations

- **Frontend:** Vanilla JS + Jinja2 templates (carry over from existing codebase). No framework, no build step.
- **Backend:** FastAPI (existing). Serves pages and handles agent execution.
- **Agent execution:** Sequential — 3 LLM calls, one per maturity level, run in sequence. Simplest to implement and debug.
- **Data persistence:** SQLite caching of agent outputs (existing pattern). Re-render screenshots without re-running the agent.
- **Screenshot mode:** Pre-compute all 3 levels, cache results, then render the stacked view instantly from cache. No loading states in the final output.

### Implementation Considerations

- No SPA routing — single page with time period picker and trigger button
- No responsive design — optimized for desktop screenshot capture
- No accessibility requirements — personal tool
- Browser target: Chrome on Mac
- Offline-capable once agent outputs are cached — no network needed for screenshot capture

## Functional Requirements

### Data Management

- FR1: User can provide mock datasets for 4 data sources (Gmail, Calendar, CRM, Trello) as the common underlying data
- FR2: System can package the same underlying data in 3 different formats: raw API/CSV (Level 1), curated data product (Level 2), ODCS contract-bound (Level 3)
- FR3: System can extend the data packaging to a 4th format (Agent Contract, Level 4) without restructuring the existing 3 levels
- FR4: User can adjust mock datasets to introduce cross-source complexity (ambiguous senders, multi-domain relationships)

### Agent Execution

- FR5: System can execute the same agent prompt against each maturity level's data packaging sequentially
- FR6: System can produce a structured recap for each level containing: summary, stats (total, unread, responded, important), and categorized email list (Action Required, Important, Notification)
- FR7: System can cache agent outputs so results can be re-rendered without re-executing the agent
- FR8: System can produce deterministic output ordering for cached results (screenshot mode)

### Time Period Selection

- FR9: User can select a recap granularity: day, week, or month
- FR10: User can trigger Alfred to generate recaps for the selected time period across all maturity levels

### Results Visualization

- FR11: User can view all maturity level recaps in a vertical stacked layout (Level 1 at top, Level 3 at bottom)
- FR12: System displays each level's recap as a self-contained section with its own summary, stats, and categorized email list
- FR13: System renders each maturity level with progressively increasing annotation density — Level 1 shows raw fields only, Level 3 shows cross-source mappings, confidence indicators, and contract metadata
- FR14: System annotates cross-source relationships caught at higher levels (e.g., "Source: CRM + Gmail + Trello")
- FR15: User can expand/collapse individual emails within each category section

### Screenshot Readiness

- FR16: User can view results in a layout with no navigation chrome, no sidebar, and no transient UI elements — only the recap content, suitable for direct slide inclusion
- FR17: System renders all cached results instantly without loading states or spinners
- FR18: System operates offline once agent outputs are cached

## Non-Functional Requirements

### Reproducibility

- Cached agent outputs must render identically across page reloads — same data, same layout, same ordering
- Agent output variance between runs is minimized for reproducibility
- Mock datasets are deterministic — no randomization at load time

### Integration

- System requires LLM API access for agent execution
- API failures during agent execution must not corrupt cached results or leave partial state
- System must gracefully handle API unavailability by displaying cached results where available and clear error messaging where not
