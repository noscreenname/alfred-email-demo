# Alfred — data contract transparency demo

Alfred is a FastAPI + Jinja2 demo that shows, viscerally, how agent-specific
metadata on top of ODCS v3.1 changes an email agent's decisions. The same
inbox is routed differently under two contract flavors, and the UI makes the
presence *and absence* of each signal visible.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # then edit ANTHROPIC_API_KEY
python3 generate_datasets.py
python3 -m uvicorn main:app --port 8000
```

Open `http://localhost:8000`.

## Environment

See `.env.example`. Required:

- `ANTHROPIC_API_KEY` — used by the Haiku classifier and Sonnet responder.

Optional tunables: `CONFIDENCE_THRESHOLD`, `CALENDAR_STALENESS_THRESHOLD_MINUTES`,
`OFF_SYSTEM_PATTERNS`.

## UI walkthrough

- **Left column** — mock inbox.
- **Middle column** — selected email body.
- **Right column** — Alfred's decision card (ACT / ESCALATE / INFORM), its
  reason, the signals it used, and a signals panel listing every field in the
  active contract. Fields missing from the active contract render as a red
  cross and "not in contract".
- **Top-right mode toggle** — flip between `standard` (ODCS v3.1 fields only)
  and `extended` (agent-specific fields like `classification_confidence`,
  `off_system_refs`, `crm_open_deal`). The decision re-runs live on the
  selected email.
- **Bottom callout** — when you are in standard mode and the decision *would
  have* depended on extended signals, Alfred tells you which ones. Click to
  toggle extended mode for that email.
- `/log` — action log of every decision including mode + reason, filterable
  by mode.

## Architecture

- `contract/` builds `EmailContractView` / `CalendarContractView` /
  `CrmContractView` dataclasses from raw JSON. Extended fields are populated
  or left `None` depending on the active contract flavor.
- `agent/decision.py` is a pure-Python rule engine that reads only view
  objects. It contains **no reference** to the strings `mode`, `standard`,
  or `extended` — rules short-circuit naturally on falsy checks, and
  `signals_missing` is populated architecturally from each rule's declared
  required signals.
- `agent/classifier.py` calls Claude Haiku with SQLite caching keyed by
  `sha256(message_id + body[:200])`.
- `agent/responder.py` calls Claude Sonnet with per-message, per-contract
  caching. Both degrade gracefully on API error.
- `storage/db.py` holds classification cache, response cache, and action log
  in SQLite.
- `main.py` wires the pipeline: classify → build views → decide → maybe
  respond → log.

## Extending Alfred with a new data source

1. Add a raw JSON file under `data/`.
2. Write `data/contracts/<domain>_standard.yaml` and `<domain>_extended.yaml`.
3. Create `contract/<domain>_contract.py` with a view dataclass and builder;
   set extended fields to `None` when the contract flavor is standard.
4. Add rules to `agent/decision.py` that read your new view fields; remember
   to list the agent-specific signal names in each rule's `required_signals`.
5. Wire the view into `main.py`'s pipeline.

## Verifying the architectural invariant

```bash
grep -nE "standard|extended|mode" agent/decision.py
# expected: no output
```
