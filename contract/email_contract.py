"""EmailContractView dataclass + builder."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional

from config import OFF_SYSTEM_PATTERNS


@dataclass
class EmailContractView:
    # Standard fields
    message_id: str
    from_name: str
    from_email: str
    subject: str
    body: str
    received_at: str
    thread_id: Optional[str] = None
    label: Optional[str] = None
    # Extended (agent-aware) fields — None in standard mode.
    classification_label: Optional[str] = None
    classification_confidence: Optional[float] = None
    off_system_refs: Optional[list[str]] = None
    thread_complete: Optional[bool] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_off_system_refs(body: str) -> list[str]:
    low = body.lower()
    hits = []
    for phrase in OFF_SYSTEM_PATTERNS:
        if phrase in low:
            hits.append(phrase)
    return hits


def build_email_view(
    raw: dict[str, Any],
    mode_name: str,
    classification: Optional[dict[str, Any]] = None,
) -> EmailContractView:
    # classification_label is a STANDARD signal per the spec — set it in both
    # modes. Only classification_confidence is extended-only.
    label = None
    if classification:
        label = classification.get("label")
    if label is None:
        label = raw.get("label_hint")
    base = EmailContractView(
        message_id=raw["message_id"],
        from_name=raw["from_name"],
        from_email=raw["from_email"],
        subject=raw["subject"],
        body=raw["body"],
        received_at=raw["received_at"],
        thread_id=raw.get("thread_id"),
        label=label,
        classification_label=label,
    )
    if mode_name == "extended":
        if classification:
            base.classification_confidence = classification.get("confidence")
        else:
            base.classification_confidence = 0.0
        base.off_system_refs = detect_off_system_refs(raw["body"])
        base.thread_complete = (raw.get("thread_length", 1) <= 1)
    return base
