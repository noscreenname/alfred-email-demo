"""CrmContractView dataclass + builder."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Optional

ACTIVE_STAGES = {"negotiation", "renewal", "at-risk"}


@dataclass
class CrmContractView:
    contact_id: str
    name: str
    email: str
    company: Optional[str] = None
    sender_tier: Optional[str] = None
    # Extended (agent-aware) — None in standard mode.
    crm_open_deal: Optional[bool] = None
    deal_stage: Optional[str] = None
    deal_owner: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_crm_view(contact: Optional[dict[str, Any]], mode_name: str) -> Optional[CrmContractView]:
    if contact is None:
        return None
    view = CrmContractView(
        contact_id=contact["contact_id"],
        name=contact["name"],
        email=contact["email"],
        company=contact.get("company"),
        sender_tier=contact.get("sender_tier"),
    )
    if mode_name == "extended":
        deals = contact.get("deals") or []
        active = next((d for d in deals if d.get("stage") in ACTIVE_STAGES), None)
        view.crm_open_deal = bool(active)
        if active:
            view.deal_stage = active.get("stage")
            view.deal_owner = active.get("owner")
    return view
