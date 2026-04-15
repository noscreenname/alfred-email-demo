"""Pure-Python rule engine operating only on contract view dataclasses.

Architectural invariant: this file never inspects a flag describing which
contract variant is active. It only reads fields on the view objects. Fields
that the active contract does not expose are None, and rule predicates
short-circuit naturally on falsy checks. Missing signals are reported
architecturally: when a rule's predicate is falsy AND its declared required
signals are all None on the view, those signal names are collected into
`signals_missing` on the final decision.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from contract.calendar_contract import CalendarContractView
from contract.crm_contract import CrmContractView
from contract.email_contract import EmailContractView
from config import CONFIDENCE_THRESHOLD

ACT = "ACT"
ESCALATE = "ESCALATE"
INFORM = "INFORM"


@dataclass
class AlfredDecision:
    status: str
    reason: str
    signals_used: list[str] = field(default_factory=list)
    signals_missing: list[str] = field(default_factory=list)
    confidence: float = 1.0
    draft_reply: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "signals_used": list(self.signals_used),
            "signals_missing": list(self.signals_missing),
            "confidence": self.confidence,
            "draft_reply": self.draft_reply,
        }


@dataclass
class Rule:
    name: str
    predicate: Callable[[EmailContractView, CalendarContractView, Optional[CrmContractView]], bool]
    decide: Callable[[EmailContractView, CalendarContractView, Optional[CrmContractView]], tuple[str, str, list[str]]]
    required_signals: list[str]


def _view_attr(view: Any, name: str) -> Any:
    if view is None:
        return None
    return getattr(view, name, None)


def _all_signals_absent(
    signal_names: list[str],
    email: EmailContractView,
    cal: CalendarContractView,
    crm: Optional[CrmContractView],
) -> bool:
    if not signal_names:
        return False
    for s in signal_names:
        source = None
        if s in ("classification_confidence", "classification_label",
                 "off_system_refs", "thread_complete"):
            source = email
        elif s in ("data_age_minutes", "safe_to_act"):
            source = cal
        elif s in ("crm_open_deal", "deal_stage", "deal_owner"):
            source = crm
        if _view_attr(source, s) is not None:
            return False
    return True


# Rule predicate + decision helpers ------------------------------------------------

def _vip_pred(e, c, r):
    return r is not None and r.sender_tier == "vip"


def _vip_decide(e, c, r):
    return (ESCALATE, "VIP sender — routing to account owner", ["sender_tier"])


def _open_deal_pred(e, c, r):
    return (
        r is not None
        and r.crm_open_deal
        and r.deal_stage in {"negotiation", "renewal", "at-risk"}
    )


def _open_deal_decide(e, c, r):
    return (
        ESCALATE,
        f"Active deal in {r.deal_stage} — autonomous reply suppressed",
        ["crm_open_deal", "deal_stage"],
    )


def _offsys_pred(e, c, r):
    return bool(e.off_system_refs) and e.label in {"proposal-confirmation", "invoice"}


def _offsys_decide(e, c, r):
    return (
        ESCALATE,
        "Email references off-system context — cannot verify prior commitment",
        ["off_system_refs", "thread_complete"],
    )


def _lowconf_pred(e, c, r):
    return (
        e.classification_confidence is not None
        and e.classification_confidence < CONFIDENCE_THRESHOLD
    )


def _lowconf_decide(e, c, r):
    return (
        ESCALATE,
        f"Classifier confidence {e.classification_confidence:.2f} below threshold",
        ["classification_confidence"],
    )


def _stale_cal_pred(e, c, r):
    return (
        e.label == "meeting-request"
        and c.safe_to_act is False
        and c.data_age_minutes is not None
    )


def _stale_cal_decide(e, c, r):
    return (
        ESCALATE,
        f"Calendar data is {c.data_age_minutes} minutes old — cannot schedule safely",
        ["data_age_minutes", "safe_to_act"],
    )


def _inform_pred(e, c, r):
    return r is None and e.label in {"internal", "newsletter"}


def _inform_decide(e, c, r):
    return (INFORM, f"Informational {e.label} — no reply drafted", ["label"])


def _default_pred(e, c, r):
    return True


def _default_decide(e, c, r):
    return (ACT, f"Routine {e.label or 'message'} — drafting reply", ["label"])


RULES: list[Rule] = [
    Rule("vip", _vip_pred, _vip_decide, []),
    Rule("open_deal", _open_deal_pred, _open_deal_decide, ["crm_open_deal", "deal_stage"]),
    Rule("off_system", _offsys_pred, _offsys_decide, ["off_system_refs", "thread_complete"]),
    Rule("low_confidence", _lowconf_pred, _lowconf_decide, ["classification_confidence"]),
    Rule("stale_calendar", _stale_cal_pred, _stale_cal_decide, ["data_age_minutes", "safe_to_act"]),
    Rule("inform_only", _inform_pred, _inform_decide, []),
    Rule("default_act", _default_pred, _default_decide, []),
]


def decide(
    email: EmailContractView,
    calendar: CalendarContractView,
    crm: Optional[CrmContractView],
) -> AlfredDecision:
    chosen: Optional[Rule] = None
    chosen_result: Optional[tuple[str, str, list[str]]] = None
    chosen_index: int = -1
    pending_missing: list[str] = []

    for idx, rule in enumerate(RULES):
        try:
            fired = rule.predicate(email, calendar, crm)
        except Exception:
            fired = False
        if fired and chosen is None:
            chosen = rule
            chosen_index = idx
            chosen_result = rule.decide(email, calendar, crm)
            break
        if not fired and rule.required_signals:
            if _all_signals_absent(rule.required_signals, email, calendar, crm):
                for s in rule.required_signals:
                    if s not in pending_missing:
                        pending_missing.append(s)

    # Only signals that *would have changed the decision* count as missing —
    # meaning they belong to rules with higher priority than the chosen one.
    # Since we break at the first firing rule, pending_missing only contains
    # signals from earlier, higher-priority rules that short-circuited on None.
    missing = pending_missing

    assert chosen is not None and chosen_result is not None
    status, reason, used = chosen_result
    conf = email.classification_confidence if email.classification_confidence is not None else 1.0
    return AlfredDecision(
        status=status,
        reason=reason,
        signals_used=used,
        signals_missing=missing,
        confidence=conf,
    )
