"""Sonnet responder with SQLite cache + graceful degradation."""
from __future__ import annotations

import logging
from typing import Any

from config import ANTHROPIC_API_KEY, RESPONDER_MODEL
from contract.email_contract import EmailContractView
from storage import db

logger = logging.getLogger("alfred.responder")

SYSTEM_PROMPT = (
    "You are Alfred, a careful executive email assistant. Draft a short, "
    "professional reply (4-8 sentences) to the inbound email. Do not invent "
    "facts, prices, or commitments. Sign off as 'Alex'. Return the reply body only."
)

PLACEHOLDER = "[Alfred placeholder reply — responder unavailable]"


def draft_reply(view: EmailContractView, intent: str, contract_mode_name: str) -> str:
    cached = db.get_response(view.message_id, contract_mode_name)
    if cached is not None:
        logger.info("responder cache hit message_id=%s", view.message_id)
        return cached

    if not ANTHROPIC_API_KEY:
        db.put_response(view.message_id, contract_mode_name, PLACEHOLDER)
        return PLACEHOLDER

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=RESPONDER_MODEL,
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"Inbound intent: {intent}\n"
                    f"From: {view.from_name} <{view.from_email}>\n"
                    f"Subject: {view.subject}\n\n"
                    f"Body:\n{view.body[:2000]}\n\n"
                    "Draft the reply now."
                ),
            }],
        )
        reply = "".join(
            getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text"
        ).strip() or PLACEHOLDER
    except Exception as e:
        logger.warning("responder error: %s", e)
        reply = PLACEHOLDER

    db.put_response(view.message_id, contract_mode_name, reply)
    return reply
