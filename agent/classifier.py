"""Haiku classifier with SQLite cache + graceful degradation."""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from config import ANTHROPIC_API_KEY, CLASSIFIER_MODEL
from storage import db

logger = logging.getLogger("alfred.classifier")

LABELS = [
    "invoice", "support", "meeting-request", "proposal-confirmation",
    "newsletter", "internal", "personal", "ambiguous",
]

SYSTEM_PROMPT = (
    "You classify short business emails into one of these intents: "
    + ", ".join(LABELS)
    + ". Respond with STRICT JSON only, no prose, matching this shape: "
    '{"label": "<one-of-labels>", "confidence": 0.0-1.0, "reasoning": "<one short sentence>"}. '
    "Confidence should reflect genuine uncertainty; use <0.75 when the email is vague."
)


def _cache_key(message_id: str, body: str) -> str:
    h = hashlib.sha256(f"{message_id}\x00{body[:200]}".encode("utf-8")).hexdigest()
    return h


def _degraded(reason: str) -> dict[str, Any]:
    return {"label": "ambiguous", "confidence": 0.0, "reasoning": reason}


def classify(message_id: str, subject: str, body: str) -> dict[str, Any]:
    key = _cache_key(message_id, body)
    cached = db.get_classification(key)
    if cached is not None:
        logger.info("classifier cache hit message_id=%s", message_id)
        return cached

    if not ANTHROPIC_API_KEY:
        result = _degraded("no api key configured")
        db.put_classification(key, message_id, result)
        return result

    try:
        from anthropic import Anthropic  # lazy import so boot doesn't require key
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=CLASSIFIER_MODEL,
            max_tokens=200,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Subject: {subject}\n\nBody:\n{body[:1500]}",
            }],
        )
        text = "".join(
            getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text"
        ).strip()
        # Defensive JSON parse
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(f"no json in response: {text!r}")
        parsed = json.loads(text[start : end + 1])
        label = parsed.get("label") if parsed.get("label") in LABELS else "ambiguous"
        confidence = float(parsed.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))
        result = {
            "label": label,
            "confidence": confidence,
            "reasoning": str(parsed.get("reasoning", ""))[:240],
        }
    except Exception as e:
        logger.warning("classifier error: %s", e)
        result = _degraded("classifier unavailable")

    db.put_classification(key, message_id, result)
    return result
