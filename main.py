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
from contract.calendar_contract import CalendarContractView, build_calendar_view
from contract.crm_contract import build_crm_view
from contract.email_contract import EmailContractView, build_email_view
from contract.loader import extended_field_names, field_names
from config import CONFIDENCE_THRESHOLD, OFF_SYSTEM_PATTERNS
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


# ---------------------------------------------------------------------------
# 4-tier comparison endpoint
# ---------------------------------------------------------------------------

TIER_ORDER = ("none", "uncontracted", "standard", "agentic")


def _build_tier_views(
    tier: str,
    raw: dict[str, Any],
    classification: dict[str, Any],
    contact: Optional[dict[str, Any]],
) -> tuple:
    """Build (email_view, cal_view, crm_view) for a given maturity tier."""
    if tier == "none":
        # No data products — only raw email text
        email_view = EmailContractView(
            message_id=raw["message_id"],
            from_name=raw["from_name"],
            from_email=raw["from_email"],
            subject=raw["subject"],
            body=raw["body"],
            received_at=raw["received_at"],
            thread_id=raw.get("thread_id"),
        )
        cal_view = CalendarContractView(
            event_count=0, next_event_title=None, next_event_start=None,
        )
        crm_view = None

    elif tier == "uncontracted":
        # Data products exist but no formal contract governance.
        # Agent gets raw access: CRM deals visible, classification label,
        # but no quality signals (confidence, off_system_refs, safe_to_act).
        email_view = build_email_view(raw, "standard", classification)
        cal_view = build_calendar_view(state.events, "standard", state.loaded_at)
        crm_view = build_crm_view(contact, "extended")  # raw CRM access → deals visible

    elif tier == "standard":
        email_view = build_email_view(raw, "standard", classification)
        cal_view = build_calendar_view(state.events, "standard", state.loaded_at)
        crm_view = build_crm_view(contact, "standard")

    else:  # agentic
        email_view = build_email_view(raw, "extended", classification)
        cal_view = build_calendar_view(state.events, "extended", state.loaded_at)
        crm_view = build_crm_view(contact, "extended")

    return email_view, cal_view, crm_view


def _has_off_system_refs(body: str) -> bool:
    low = body.lower()
    return any(p in low for p in OFF_SYSTEM_PATTERNS)


def _compute_issues(
    tier: str,
    tier_dec: dict[str, Any],
    agentic_dec: dict[str, Any],
    raw: dict[str, Any],
    classification: dict[str, Any],
    contact: Optional[dict[str, Any]],
) -> list[dict[str, str]]:
    """Annotate a tier's result with inconsistencies, gaps, and risks."""
    issues: list[dict[str, str]] = []

    # Decision divergence from agentic
    if tier_dec["status"] != agentic_dec["status"]:
        issues.append({
            "type": "inconsistency",
            "text": (
                f"Decides {tier_dec['status']} — agentic contract "
                f"would {agentic_dec['status']}"
            ),
        })

    has_off_sys = _has_off_system_refs(raw["body"])
    conf = classification.get("confidence", 1.0)
    deals = (contact or {}).get("deals", [])
    active_deals = [d for d in deals if d.get("stage") in {"negotiation", "renewal", "at-risk"}]
    active_deal = active_deals[0] if active_deals else None

    if tier == "none":
        issues.append({
            "type": "gap",
            "text": "No email classification — cannot triage by intent",
        })
        if contact:
            issues.append({
                "type": "gap",
                "text": (
                    f"Sender is '{contact.get('sender_tier', 'known')}' "
                    f"in CRM but invisible to agent"
                ),
            })
        if active_deal:
            issues.append({
                "type": "risk",
                "text": (
                    f"€{active_deal['value_eur']:,} deal "
                    f"({active_deal['stage']}) not visible — may reply autonomously"
                ),
            })
        if has_off_sys:
            issues.append({
                "type": "risk",
                "text": "Body references off-system conversation — agent cannot detect",
            })
        issues.append({
            "type": "gap",
            "text": "No calendar data — cannot check availability or detect conflicts",
        })

    elif tier == "uncontracted":
        if conf < CONFIDENCE_THRESHOLD:
            issues.append({
                "type": "assumption",
                "text": (
                    f"Classification confidence is {conf:.0%} — "
                    "no threshold check applied"
                ),
            })
        if has_off_sys:
            issues.append({
                "type": "gap",
                "text": (
                    "Off-system references in body but no contract-mandated "
                    "scanning — agent cannot detect"
                ),
            })
        issues.append({
            "type": "assumption",
            "text": "Calendar data used without freshness verification",
        })
        if contact:
            issues.append({
                "type": "assumption",
                "text": "CRM data trusted blindly — no SLA on data recency",
            })

    elif tier == "standard":
        if has_off_sys:
            issues.append({
                "type": "gap",
                "text": "Off-system references not detectable in standard contract",
            })
        if conf < CONFIDENCE_THRESHOLD:
            issues.append({
                "type": "gap",
                "text": (
                    f"Classification confidence ({conf:.0%}) not exposed "
                    "in standard contract"
                ),
            })
        if active_deal:
            issues.append({
                "type": "gap",
                "text": (
                    f"Deal info ({active_deal['stage']}, "
                    f"€{active_deal['value_eur']:,}) hidden in standard contract"
                ),
            })

    return issues


@app.get("/api/email/{message_id}/compare")
def api_compare(message_id: str):
    raw = state.emails_by_id.get(message_id)
    if raw is None:
        raise HTTPException(status_code=404, detail=f"email {message_id} not found")

    classification = classifier.classify(message_id, raw["subject"], raw["body"])
    contact = state.contacts_by_email.get(raw["from_email"].lower())

    tiers: dict[str, Any] = {}
    for tier in TIER_ORDER:
        email_view, cal_view, crm_view = _build_tier_views(
            tier, raw, classification, contact,
        )
        decision = dec.decide(email_view, cal_view, crm_view)
        tiers[tier] = {
            "decision": decision.to_dict(),
            "contract_views": {
                "email": email_view.to_dict(),
                "calendar": cal_view.to_dict(),
                "crm": crm_view.to_dict() if crm_view else None,
            },
        }

    agentic_dec = tiers["agentic"]["decision"]
    for tier in TIER_ORDER:
        if tier == "agentic":
            tiers[tier]["issues"] = []
        else:
            tiers[tier]["issues"] = _compute_issues(
                tier, tiers[tier]["decision"], agentic_dec,
                raw, classification, contact,
            )

    return JSONResponse({
        "email": {
            "message_id": raw["message_id"],
            "from_name": raw["from_name"],
            "from_email": raw["from_email"],
            "subject": raw["subject"],
            "body": raw["body"],
            "received_at": raw["received_at"],
        },
        "tiers": tiers,
    })


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
