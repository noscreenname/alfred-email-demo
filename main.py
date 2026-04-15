"""Alfred FastAPI app."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agent import classifier, decision as dec, responder
from contract.calendar_contract import build_calendar_view
from contract.crm_contract import build_crm_view
from contract.email_contract import build_email_view
from contract.loader import extended_field_names, field_names
from storage import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("alfred")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

app = FastAPI(title="Alfred")
app.mount("/static", StaticFiles(directory=BASE_DIR / "ui" / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "ui" / "templates"))


# In-memory dataset cache.
class State:
    emails: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    contacts: list[dict[str, Any]] = []
    contacts_by_email: dict[str, dict[str, Any]] = {}
    emails_by_id: dict[str, dict[str, Any]] = {}
    loaded_at: datetime = datetime.now(timezone.utc)


state = State()


def _load_datasets() -> None:
    with (DATA_DIR / "emails.json").open() as f:
        state.emails = json.load(f)
    with (DATA_DIR / "calendar.json").open() as f:
        state.events = json.load(f)
    with (DATA_DIR / "crm_contacts.json").open() as f:
        state.contacts = json.load(f)
    state.contacts_by_email = {c["email"].lower(): c for c in state.contacts}
    state.emails_by_id = {e["message_id"]: e for e in state.emails}
    state.loaded_at = datetime.now(timezone.utc)
    logger.info(
        "datasets loaded: %d emails, %d events, %d contacts",
        len(state.emails), len(state.events), len(state.contacts),
    )


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    _load_datasets()


def _normalize_mode(m: str) -> str:
    return "extended" if m == "extended" else "standard"


def _run_pipeline(message_id: str, contract_mode: str) -> dict[str, Any]:
    raw = state.emails_by_id.get(message_id)
    if raw is None:
        raise HTTPException(status_code=404, detail=f"email {message_id} not found")

    # 1. classify (cached)
    classification = classifier.classify(message_id, raw["subject"], raw["body"])

    # 2. build views
    email_view = build_email_view(raw, contract_mode, classification)
    cal_view = build_calendar_view(state.events, contract_mode, state.loaded_at)
    contact = state.contacts_by_email.get(raw["from_email"].lower())
    crm_view = build_crm_view(contact, contract_mode)

    # 3. decide
    decision = dec.decide(email_view, cal_view, crm_view)

    # 4. responder (only if ACT)
    if decision.status == dec.ACT:
        try:
            decision.draft_reply = responder.draft_reply(
                email_view, classification.get("label", "unknown"), contract_mode
            )
        except Exception as e:
            logger.warning("responder pipeline error: %s", e)
            decision.status = dec.ESCALATE
            decision.reason = "responder unavailable — escalating"

    # 5. log the action
    db.append_action(
        message_id=message_id,
        sender=f"{raw['from_name']} <{raw['from_email']}>",
        subject=raw["subject"],
        contract_mode=contract_mode,
        status=decision.status,
        reason=decision.reason,
    )

    return {
        "email": {
            "message_id": raw["message_id"],
            "from_name": raw["from_name"],
            "from_email": raw["from_email"],
            "subject": raw["subject"],
            "body": raw["body"],
            "received_at": raw["received_at"],
        },
        "contract_mode": contract_mode,
        "classification": classification,
        "contract_views": {
            "email": email_view.to_dict(),
            "calendar": cal_view.to_dict(),
            "crm": crm_view.to_dict() if crm_view else None,
        },
        "contract_fields": {
            "email": field_names("email", contract_mode),
            "calendar": field_names("calendar", contract_mode),
            "crm": field_names("crm", contract_mode),
            "email_extended_only": extended_field_names("email"),
            "calendar_extended_only": extended_field_names("calendar"),
            "crm_extended_only": extended_field_names("crm"),
        },
        "decision": decision.to_dict(),
    }


@app.get("/")
def index(request: Request, mode: str = Query("standard")):
    contract_mode = _normalize_mode(mode)
    inbox = [
        {
            "message_id": e["message_id"],
            "from_name": e["from_name"],
            "subject": e["subject"],
            "received_at": e["received_at"],
        }
        for e in state.emails
    ]
    first_id = inbox[0]["message_id"] if inbox else None
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "inbox": inbox,
            "first_id": first_id,
            "contract_mode": contract_mode,
        },
    )


@app.get("/api/email/{message_id}")
def api_email(message_id: str, mode: str = Query("standard")):
    return JSONResponse(_run_pipeline(message_id, _normalize_mode(mode)))


@app.get("/api/refresh")
def api_refresh():
    _load_datasets()
    return {"status": "ok", "loaded_at": state.loaded_at.isoformat()}


@app.get("/log")
def log_page(request: Request, mode: Optional[str] = None):
    contract_mode = _normalize_mode(mode) if mode in ("standard", "extended") else None
    rows = db.list_actions(mode_filter=contract_mode)
    return templates.TemplateResponse(
        request,
        "log.html",
        {"rows": rows, "mode_filter": contract_mode or ""},
    )
