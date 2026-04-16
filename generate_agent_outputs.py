"""Run EMAIL_A and AGENDA_A through mock-datasets.json with and without contract.

Produces four JSONL files in data/:
  email_a_with_contract.jsonl
  email_a_no_contract.jsonl
  agenda_a_with_contract.jsonl
  agenda_a_no_contract.jsonl
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

DATA_DIR = Path(__file__).resolve().parent / "data"

# ---------------------------------------------------------------------------
# Load datasets
# ---------------------------------------------------------------------------

with (DATA_DIR / "mock-datasets.json").open() as f:
    DS = json.load(f)

CONTACTS = {c["email"].lower(): c for c in DS["contacts"]}
CONTACTS_BY_ID = {c["contact_id"]: c for c in DS["contacts"]}
PREFERENCES = DS["preferences"]
PRIORITIES = DS["priorities"]
REFERENCES = DS["references"]
EMAILS = DS["emails"]
CALENDAR = DS["calendar"]

# Pre-index references by linked contact
REF_BY_CONTACT: dict[str, list[dict]] = {}
for ref in REFERENCES:
    for cid in ref.get("linked_contacts", []):
        REF_BY_CONTACT.setdefault(cid, []).append(ref)

# Pre-index references by keyword in topic_name
REF_KEYWORDS: list[tuple[list[str], dict]] = []
for ref in REFERENCES:
    words = ref["topic_name"].lower().split()
    REF_KEYWORDS.append((words, ref))

CONFIDENCE_THRESHOLD = 0.75
OVERRIDE_KEYWORDS = [
    "legal", "lawsuit", "confidential", "injunction", "without prejudice",
    "board", "shareholder", "governance",
]
SENSITIVITY_CONTACTS = set(PREFERENCES["context_sensitivity_map"]["contacts"])
SENSITIVITY_TOPICS = set(PREFERENCES["context_sensitivity_map"]["topics"])
ALWAYS_ESCALATE_TYPES = {"board", "press", "unknown"}
DRAFT_ONLY_TOPICS = {
    "client", "investor", "prospect", "hr", "personnel",
    "contract", "pricing",
}
CAN_REPLY_AUTO = set(PREFERENCES["delegation_boundaries"]["can_reply_autonomously"])
DRAFT_ONLY_BOUNDARIES = set(PREFERENCES["delegation_boundaries"]["draft_only"])
ALWAYS_ESCALATE_BOUNDARIES = set(PREFERENCES["delegation_boundaries"]["always_escalate"])

OFF_SYSTEM_PATTERNS = [
    "as we discussed", "per our call", "as agreed",
    "following our conversation", "as promised", "like i mentioned",
    "per my last email", "comme convenu", "suite a notre echange",
]

DEEP_WORK = [("07:00", "09:00"), ("13:00", "14:00")]
MEETINGS_OK = [("09:00", "12:00"), ("14:00", "17:00")]
AVOID_WINDOWS = [("12:00", "13:00"), ("17:30", "19:00")]

PREF_STALE_DAYS = 22  # 2026-03-25 → 2026-04-16 = 22 days
PRIO_STALE_DAYS = 9   # 2026-04-07 → 2026-04-16 = 9 days

BLOCKING_DEPS: set[str] = set()
for proj in PRIORITIES["active_projects"]:
    for cid in proj.get("blocking_dependencies", []):
        BLOCKING_DEPS.add(cid)

# Calendar by date
NOW = datetime(2026, 4, 16, 12, 0)
CAL_BY_DATE: dict[str, list[dict]] = {}
for ev in CALENDAR:
    d = ev["start"][:10]
    CAL_BY_DATE.setdefault(d, []).append(ev)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def has_off_system_refs(body: str) -> list[str]:
    low = body.lower()
    return [p for p in OFF_SYSTEM_PATTERNS if p in low]


def match_reference(email: dict, contact: Optional[dict]) -> Optional[dict]:
    """Match email to a reference topic."""
    # By linked contact
    if contact:
        cid = contact["contact_id"]
        refs = REF_BY_CONTACT.get(cid, [])
        if refs:
            return refs[0]
    # By keyword in subject/body
    text = (email["subject"] + " " + email["body"]).lower()
    for words, ref in REF_KEYWORDS:
        if sum(1 for w in words if w in text) >= 2:
            return ref
    return None


def is_scheduling_email(email: dict) -> bool:
    """Detect if email involves a scheduling request."""
    body_low = email["body"].lower()
    subj_low = email["subject"].lower()
    scheduling_signals = [
        "available", "schedule", "meeting", "call", "sync",
        "find time", "free", "slot", "book", "calendar",
        "minutes", "30 min", "20 min", "45 min",
        "thursday", "friday", "monday", "wednesday",
        "this week", "next week",
    ]
    has_request = email.get("purpose") == "request" and email.get("call_to_action", False)
    has_scheduling_keyword = any(s in body_low or s in subj_low for s in scheduling_signals)
    return has_request and has_scheduling_keyword


def check_body_override_keywords(body: str) -> list[str]:
    low = body.lower()
    return [kw for kw in OVERRIDE_KEYWORDS if kw in low]


def get_available_slots(date_str: str) -> list[str]:
    """Return available 30-min slots on a date, respecting calendar and preferences."""
    events = CAL_BY_DATE.get(date_str, [])
    busy = []
    for ev in events:
        start_h, start_m = int(ev["start"][11:13]), int(ev["start"][14:16])
        end_h, end_m = int(ev["end"][11:13]), int(ev["end"][14:16])
        busy.append((start_h * 60 + start_m, end_h * 60 + end_m))

    slots = []
    for window_start, window_end in MEETINGS_OK:
        ws = int(window_start[:2]) * 60 + int(window_start[3:])
        we = int(window_end[:2]) * 60 + int(window_end[3:])
        t = ws
        while t + 30 <= we:
            # Check buffer (10 min)
            conflict = False
            for bs, be in busy:
                if t < be + 10 and t + 30 > bs - 10:
                    conflict = True
                    break
            if not conflict:
                h, m = divmod(t, 60)
                slots.append(f"{h:02d}:{m:02d}")
            t += 30

    return slots[:3]


# ---------------------------------------------------------------------------
# EMAIL_A — with contract
# ---------------------------------------------------------------------------

def email_a_with_contract(email: dict) -> dict:
    trace: list[str] = []
    signals_used: list[str] = []
    signals_missing: list[str] = []
    warnings: list[str] = []

    contact = CONTACTS.get(email["sender"].lower())
    ref = match_reference(email, contact)
    off_sys = has_off_system_refs(email["body"])

    # Session-level warnings
    warnings.append("Preferences stale (22 days) — ACT blocked")
    warnings.append("Priorities stale (9 days) — INFORM context only")

    # Step 1: Override check
    body_kws = check_body_override_keywords(email["body"])
    if body_kws:
        trace.append(f"OVERRIDE: body contains [{', '.join(body_kws)}]")
        return _email_result(email, contact, ref, "ESCALATE",
            f"Override trigger: body contains {body_kws}",
            trace, signals_used + ["body_keywords"], signals_missing, warnings)

    if contact and contact["contact_id"] in SENSITIVITY_CONTACTS:
        if contact.get("auto_reply_policy") == "never" or contact.get("relationship_type") in ALWAYS_ESCALATE_TYPES:
            trace.append(f"OVERRIDE: sender {contact['name']} is in always_escalate / sensitivity map")
            return _email_result(email, contact, ref, "ESCALATE",
                f"Sender {contact['name']} requires personal attention (always_escalate)",
                trace, ["context_sensitivity_map", "auto_reply_policy"], signals_missing, warnings)

    conf = email.get("classification_confidence", 1.0)
    if conf < 0.5:
        trace.append(f"OVERRIDE: classification_confidence={conf:.2f} < 0.5")
        signals_used.append("classification_confidence")
        return _email_result(email, contact, ref, "ESCALATE",
            f"Classification confidence {conf:.2f} below minimum threshold",
            trace, signals_used, signals_missing, warnings)

    if email.get("tone_shift") and contact and contact.get("relationship_strength_score", 0) > 0.7:
        trace.append(f"OVERRIDE: tone_shift=true with strong relationship ({contact['name']})")
        signals_used.extend(["tone_shift", "relationship_strength_score"])
        return _email_result(email, contact, ref, "ESCALATE",
            f"Tone shift detected from strong relationship ({contact['name']})",
            trace, signals_used, signals_missing, warnings)

    if email.get("thread_completeness") == "references_off_system" and email.get("urgency_score", 0) > 0.6:
        trace.append(f"OVERRIDE: references_off_system with urgency={email['urgency_score']}")
        signals_used.extend(["thread_completeness", "urgency_score"])
        return _email_result(email, contact, ref, "ESCALATE",
            "Off-system references with high urgency — cannot verify prior context",
            trace, signals_used, signals_missing, warnings)

    trace.append("Override check: passed")

    # Step 2: Handling constraint
    hc = email.get("handling_constraint", "auto_ok")
    signals_used.append("handling_constraint")
    if hc == "human_required":
        trace.append(f"HANDLING CONSTRAINT: human_required")
        return _email_result(email, contact, ref, "ESCALATE",
            "Handling constraint is human_required — user must review",
            trace, signals_used, signals_missing, warnings)

    # Step 3: Contact evaluation
    if contact is None:
        trace.append("CONTACT: sender not in contacts — flag and DRAFT")
        signals_missing.append("contact_record")
        if hc == "draft_only" or email.get("purpose") == "request":
            return _email_result(email, contact, ref, "DRAFT",
                "Unknown sender — no contact record. Drafted for review.",
                trace, signals_used, signals_missing, warnings,
                draft=_generate_draft(email, contact, ref, "unknown sender"))
        return _email_result(email, contact, ref, "INFORM",
            "Unknown sender, no action required — informing user",
            trace, signals_used, signals_missing, warnings)

    signals_used.append("contact_record")
    c_name = contact["name"]
    c_type = contact.get("relationship_type", "unknown")
    c_tier = contact.get("temporal_importance", "standard")
    c_policy = contact.get("auto_reply_policy", "allowed")
    c_open = contact.get("open_context_flag", False)
    c_prov = contact.get("provenance", "unknown")

    if c_policy == "never":
        trace.append(f"CONTACT: {c_name} auto_reply_policy=never — notify only")
        signals_used.append("auto_reply_policy")
        return _email_result(email, contact, ref, "ESCALATE",
            f"{c_name} is flagged for personal replies only — no draft produced",
            trace, signals_used, signals_missing, warnings)

    if c_tier == "critical":
        trace.append(f"CONTACT: {c_name} temporal_importance=critical — DRAFT")
        signals_used.append("temporal_importance")
        if c_open:
            warnings.append(f"Open context: {contact.get('open_context_note', '')}")
        return _email_result(email, contact, ref, "DRAFT",
            f"{c_name} has critical importance — drafted for urgent review",
            trace, signals_used, signals_missing, warnings,
            draft=_generate_draft(email, contact, ref, "critical contact"))

    if c_open:
        trace.append(f"CONTACT: {c_name} open_context_flag=true — flagging")
        signals_used.append("open_context_flag")
        warnings.append(f"Open situation: {contact.get('open_context_note', '')}")

    if contact["contact_id"] in SENSITIVITY_CONTACTS:
        trace.append(f"CONTACT: {c_name} in context_sensitivity_map — personal voice required")
        signals_used.append("context_sensitivity_map")
        return _email_result(email, contact, ref, "DRAFT",
            f"{c_name} requires personal voice — no templated drafts",
            trace, signals_used, signals_missing, warnings,
            draft=_generate_draft(email, contact, ref, "sensitivity contact"))

    if c_tier == "elevated":
        trace.append(f"CONTACT: {c_name} temporal_importance=elevated — DRAFT")
        signals_used.append("temporal_importance")

    if c_prov == "inferred":
        warnings.append(f"Relationship context for {c_name} is inferred — may not be accurate")

    # Step 4: Topic matching
    if ref:
        signals_used.append("reference_topic")
        trace.append(f"TOPIC: matched {ref['topic_name']} (completeness={ref['context_completeness']}, threshold={ref['action_threshold']})")

        if ref["action_threshold"] == "human_required":
            return _email_result(email, contact, ref, "ESCALATE",
                f"Topic '{ref['topic_name']}' requires personal attention (human_required)",
                trace, signals_used, signals_missing, warnings)

        if ref["context_completeness"] == "known_gaps":
            warnings.append(f"Incomplete context on '{ref['topic_name']}' — known gaps exist")
            return _email_result(email, contact, ref, "DRAFT",
                f"Known context gaps on '{ref['topic_name']}' — cannot act safely",
                trace, signals_used, signals_missing, warnings,
                draft=_generate_draft(email, contact, ref, "known gaps"))

        if ref.get("off_system_refs"):
            warnings.append(f"Off-system interactions on '{ref['topic_name']}': {ref['off_system_refs']}")

        if ref.get("momentum") == "stalled":
            warnings.append(f"Topic '{ref['topic_name']}' appears stalled")

        if ref["action_threshold"] == "draft_only":
            trace.append(f"TOPIC: action_threshold=draft_only")
    else:
        trace.append("TOPIC: no reference match")

    # Step 5: Priority weighting
    is_blocking = contact["contact_id"] in BLOCKING_DEPS
    if is_blocking:
        signals_used.append("blocking_dependency")
        trace.append(f"PRIORITY: {c_name} is a blocking dependency — elevate")
        warnings.append(f"Blocking dependency: {c_name}")

    matched_proj = None
    for proj in PRIORITIES["active_projects"]:
        if contact["contact_id"] in proj.get("blocking_dependencies", []):
            matched_proj = proj
            break

    if matched_proj and matched_proj.get("sensitivity_flag"):
        trace.append(f"PRIORITY: project '{matched_proj['name']}' has sensitivity_flag — DRAFT only")
        signals_used.append("sensitivity_flag")

    # Step 6: Autonomy decision
    can_act = True
    act_blockers: list[str] = []

    if hc != "auto_ok":
        can_act = False
        act_blockers.append(f"handling_constraint={hc}")
    if conf < CONFIDENCE_THRESHOLD:
        can_act = False
        act_blockers.append(f"classification_confidence={conf:.2f} < {CONFIDENCE_THRESHOLD}")
        signals_used.append("classification_confidence")
    if email.get("thread_completeness") != "full":
        can_act = False
        act_blockers.append(f"thread_completeness={email.get('thread_completeness')}")
    if email.get("tone_shift"):
        can_act = False
        act_blockers.append("tone_shift=true")
    if c_policy != "allowed":
        can_act = False
        act_blockers.append(f"auto_reply_policy={c_policy}")
    if c_tier != "standard":
        can_act = False
        act_blockers.append(f"temporal_importance={c_tier}")
    if c_open:
        can_act = False
        act_blockers.append("open_context_flag=true")
    if ref and ref["action_threshold"] != "auto_ok":
        can_act = False
        act_blockers.append(f"ref.action_threshold={ref['action_threshold']}")
    if ref and ref["context_completeness"] != "full":
        can_act = False
        act_blockers.append(f"ref.context_completeness={ref['context_completeness']}")
    if ref and ref.get("off_system_refs"):
        can_act = False
        act_blockers.append("ref.off_system_refs present")
    if ref and ref.get("momentum") == "stalled":
        can_act = False
        act_blockers.append("ref.momentum=stalled")
    if PREF_STALE_DAYS > 14:
        can_act = False
        act_blockers.append(f"preferences stale ({PREF_STALE_DAYS} days > 14)")
    if PRIO_STALE_DAYS > 7:
        can_act = False
        act_blockers.append(f"priorities stale ({PRIO_STALE_DAYS} days > 7)")
    if off_sys:
        can_act = False
        act_blockers.append(f"off_system_refs detected: {off_sys}")
        signals_used.append("off_system_refs")

    if can_act:
        trace.append("AUTONOMY: all conditions met — ACT")
        purpose = email.get("purpose", "unknown")
        if purpose == "fyi" or not email.get("call_to_action"):
            return _email_result(email, contact, ref, "INFORM",
                f"Routine {c_type} message — no action required",
                trace, signals_used, signals_missing, warnings)
        return _email_result(email, contact, ref, "ACT",
            f"All autonomy conditions met — acting on routine {email.get('purpose', 'message')}",
            trace, signals_used, signals_missing, warnings,
            draft=_generate_draft(email, contact, ref, "auto"))
    else:
        trace.append(f"AUTONOMY: blocked by [{'; '.join(act_blockers)}]")
        purpose = email.get("purpose", "unknown")
        if purpose == "fyi" or not email.get("call_to_action"):
            return _email_result(email, contact, ref, "INFORM",
                f"Informational — no reply needed. Blockers noted: {act_blockers[0]}",
                trace, signals_used, signals_missing, warnings)
        if c_policy == "draft_only" or c_tier in ("elevated", "critical") or hc == "draft_only":
            return _email_result(email, contact, ref, "DRAFT",
                f"Cannot act autonomously ({act_blockers[0]}) — draft for review",
                trace, signals_used, signals_missing, warnings,
                draft=_generate_draft(email, contact, ref, act_blockers[0]))
        return _email_result(email, contact, ref, "DRAFT",
            f"Cannot act autonomously ({act_blockers[0]}) — draft for review",
            trace, signals_used, signals_missing, warnings,
            draft=_generate_draft(email, contact, ref, act_blockers[0]))


# ---------------------------------------------------------------------------
# EMAIL_A — without contract
# ---------------------------------------------------------------------------

def email_a_no_contract(email: dict) -> dict:
    """Agent has raw email + raw data access but no contract governance."""
    trace: list[str] = []
    signals_used: list[str] = []
    warnings: list[str] = []

    contact = CONTACTS.get(email["sender"].lower())

    # No override checks — no contract defines them
    # No handling_constraint — no contract exposes it
    # No freshness checks — no SLAs
    # No off-system detection — no contract-mandated scanning
    # No confidence thresholds — trusts classifier blindly
    # No thread_completeness checks
    # No reference topic matching — no governed topic registry

    trace.append("No contract governance — using raw data only")

    purpose = email.get("purpose", "unknown")
    urgency = email.get("urgency_score", 0.5)
    has_cta = email.get("call_to_action", False)

    # Basic heuristic: if sender is known, use relationship type
    if contact:
        c_name = contact["name"]
        c_type = contact.get("relationship_type", "unknown")
        signals_used.append("contact_record")
        trace.append(f"CONTACT: found {c_name} ({c_type})")

        # Without contract, no auto_reply_policy enforcement
        # Without contract, no temporal_importance checks
        # Without contract, no open_context_flag checks
        # Agent just sees the relationship type and decides

        if c_type in ("board", "press"):
            # Some common sense, but no formal rule
            trace.append(f"HEURISTIC: {c_type} sender — probably should escalate but no rule enforces it")
            # Without contract, agent might still try to draft
            if has_cta:
                return _email_result(email, contact, None, "ACT",
                    f"Request from {c_type} contact {c_name} — drafting reply (no governance prevents this)",
                    trace, signals_used, [],  warnings,
                    draft=_generate_draft(email, contact, None, "no contract"))

        if purpose == "fyi" or not has_cta:
            return _email_result(email, contact, None, "INFORM",
                f"Informational message from {c_name} — no reply needed",
                trace, signals_used, [], warnings)

        # Default: ACT on everything with a CTA
        trace.append("DEFAULT: has call_to_action — ACT (no contract prevents autonomous action)")
        return _email_result(email, contact, None, "ACT",
            f"Request from {c_name} — acting autonomously (no contract governance)",
            trace, signals_used, [], warnings,
            draft=_generate_draft(email, contact, None, "no contract"))
    else:
        trace.append("CONTACT: sender not found — no context available")
        if purpose == "fyi" or not has_cta:
            return _email_result(email, None, None, "INFORM",
                "No sender context, informational — skipping",
                trace, signals_used, [], warnings)

        # Without contract, agent has no rule against replying to unknowns
        if urgency > 0.7:
            trace.append(f"HEURISTIC: high urgency ({urgency:.2f}) — acting despite unknown sender")
            return _email_result(email, None, None, "ACT",
                f"High urgency from unknown sender — acting (no contract blocks this)",
                trace, signals_used + ["urgency_score"], [], warnings,
                draft=_generate_draft(email, None, None, "unknown sender, no contract"))

        return _email_result(email, None, None, "ACT",
            "Request from unknown sender — acting (no governance prevents this)",
            trace, signals_used, [], warnings,
            draft=_generate_draft(email, None, None, "no contract"))


# ---------------------------------------------------------------------------
# AGENDA_A — with contract
# ---------------------------------------------------------------------------

def agenda_a_with_contract(email: dict) -> dict:
    trace: list[str] = []
    signals_used: list[str] = []
    signals_missing: list[str] = []
    warnings: list[str] = []

    if not is_scheduling_email(email):
        return _agenda_result(email, None, None, "SKIP",
            "Not a scheduling request",
            trace, signals_used, signals_missing, warnings)

    contact = CONTACTS.get(email["sender"].lower())
    ref = match_reference(email, contact)

    warnings.append("Preferences stale (22 days) — ACT blocked for all scheduling")
    warnings.append("Priorities stale (9 days) — context only")
    warnings.append(f"Focus this week: {PRIORITIES['focus_this_week']}")

    signals_used.append("email_scheduling_signals")

    # Calendar freshness (simulated — assume 3 min for demo)
    cal_age_minutes = 3
    signals_used.append("data_age_minutes")
    trace.append(f"CALENDAR: data_age_minutes={cal_age_minutes}")

    if cal_age_minutes > 10:
        return _agenda_result(email, contact, ref, "INFORM",
            f"Calendar data is {cal_age_minutes} minutes old — cannot propose slots. User must check manually.",
            trace, signals_used, signals_missing, warnings)

    if cal_age_minutes > 5:
        warnings.append(f"Calendar data is {cal_age_minutes} min old — proposals need user confirmation")

    # Contact check
    if contact:
        signals_used.append("contact_record")
        c_name = contact["name"]
        c_policy = contact.get("auto_reply_policy", "allowed")
        c_tier = contact.get("temporal_importance", "standard")
        c_type = contact.get("relationship_type", "unknown")

        trace.append(f"CONTACT: {c_name} (type={c_type}, importance={c_tier}, policy={c_policy})")

        if c_policy == "never":
            return _agenda_result(email, contact, ref, "ESCALATE",
                f"{c_name} auto_reply_policy=never — cannot send invite. User must handle.",
                trace, signals_used, signals_missing, warnings)

        if c_tier == "critical":
            trace.append(f"CONTACT: critical importance — DRAFT only")
        elif c_tier == "elevated":
            trace.append(f"CONTACT: elevated importance — DRAFT only")
            warnings.append(f"{c_name} has elevated importance — drafting invite rather than sending")

        if c_type not in ("client", "prospect", "internal", "personal"):
            trace.append(f"CONTACT: relationship_type={c_type} — requires DRAFT or escalation")
    else:
        trace.append("CONTACT: sender not in contacts")
        signals_missing.append("contact_record")

    # Reference check
    if ref:
        signals_used.append("reference_topic")
        trace.append(f"TOPIC: matched {ref['topic_name']} (threshold={ref['action_threshold']})")
        if ref["action_threshold"] == "human_required":
            return _agenda_result(email, contact, ref, "ESCALATE",
                f"Topic '{ref['topic_name']}' requires human review before booking",
                trace, signals_used, signals_missing, warnings)
        if ref["action_threshold"] == "draft_only":
            trace.append("TOPIC: action_threshold=draft_only")
    else:
        trace.append("TOPIC: no reference match")

    # Extract requested time signals from email body
    requested = _extract_time_signals(email["body"])
    trace.append(f"REQUESTED: {requested}")

    # Find available slots
    target_dates = _get_target_dates(email)
    proposed_slots: list[dict] = []
    excluded_slots: list[dict] = []

    for d in target_dates:
        date_str = d.strftime("%Y-%m-%d")
        day_events = CAL_BY_DATE.get(date_str, [])

        if len(day_events) >= 5:
            excluded_slots.append({"date": date_str, "reason": "max_meetings_per_day (5) reached"})
            continue

        available = get_available_slots(date_str)
        for slot_time in available:
            if len(proposed_slots) >= 3:
                break
            # Check deep work
            is_deep = any(
                slot_time >= dw[0] and slot_time < dw[1]
                for dw in DEEP_WORK
            )
            if is_deep:
                excluded_slots.append({"date": date_str, "time": slot_time, "reason": "deep_work block"})
                continue
            proposed_slots.append({
                "date": date_str,
                "time": slot_time,
                "rationale": f"Within preferred window, no conflicts, {10}min buffer respected",
            })
        if len(proposed_slots) >= 3:
            break

    # Autonomy decision
    can_act = True
    act_blockers: list[str] = []

    if cal_age_minutes >= 2:
        can_act = False
        act_blockers.append(f"data_age_minutes={cal_age_minutes} >= 2")
    if PREF_STALE_DAYS > 14:
        can_act = False
        act_blockers.append(f"preferences stale ({PREF_STALE_DAYS} days)")
    if contact and contact.get("temporal_importance") != "standard":
        can_act = False
        act_blockers.append(f"temporal_importance={contact.get('temporal_importance')}")
    if contact and contact.get("auto_reply_policy") not in ("allowed", None):
        can_act = False
        act_blockers.append(f"auto_reply_policy={contact.get('auto_reply_policy')}")
    if contact and contact.get("relationship_type") not in ("client", "prospect", "internal", "personal"):
        can_act = False
        act_blockers.append(f"relationship_type={contact.get('relationship_type')}")
    if ref and ref["action_threshold"] != "auto_ok":
        can_act = False
        act_blockers.append(f"ref.action_threshold={ref['action_threshold']}")

    if can_act:
        decision = "ACT"
        reason = "All scheduling conditions met — booking autonomously"
    else:
        decision = "DRAFT"
        reason = f"Cannot book autonomously ({act_blockers[0]}) — proposing slots for review"

    trace.append(f"AUTONOMY: {'ACT' if can_act else 'DRAFT'} [{'; '.join(act_blockers) if act_blockers else 'all clear'}]")

    return _agenda_result(email, contact, ref, decision, reason,
        trace, signals_used, signals_missing, warnings,
        proposed_slots=proposed_slots,
        excluded_slots=excluded_slots)


# ---------------------------------------------------------------------------
# AGENDA_A — without contract
# ---------------------------------------------------------------------------

def agenda_a_no_contract(email: dict) -> dict:
    trace: list[str] = []
    signals_used: list[str] = []
    warnings: list[str] = []

    if not is_scheduling_email(email):
        return _agenda_result(email, None, None, "SKIP",
            "Not a scheduling request",
            trace, signals_used, [], warnings)

    contact = CONTACTS.get(email["sender"].lower())
    trace.append("No contract governance — scheduling with raw calendar access")

    # No freshness check — trusts calendar blindly
    # No contact policy check — books for anyone
    # No energy schedule check — may book during deep work
    # No reference topic check — no governance
    # No max meetings check — no limit enforced

    if contact:
        signals_used.append("contact_record")
        trace.append(f"CONTACT: {contact['name']} ({contact.get('relationship_type', 'unknown')})")

    # Just find ANY open slots without respecting preferences
    target_dates = _get_target_dates(email)
    proposed_slots: list[dict] = []

    for d in target_dates:
        date_str = d.strftime("%Y-%m-%d")
        events = CAL_BY_DATE.get(date_str, [])
        busy = []
        for ev in events:
            sh, sm = int(ev["start"][11:13]), int(ev["start"][14:16])
            eh, em = int(ev["end"][11:13]), int(ev["end"][14:16])
            busy.append((sh * 60 + sm, eh * 60 + em))

        # No preference windows — scan 07:00 to 19:00
        for t in range(7 * 60, 19 * 60, 30):
            if len(proposed_slots) >= 3:
                break
            conflict = any(t < be and t + 30 > bs for bs, be in busy)
            if not conflict:
                h, m = divmod(t, 60)
                proposed_slots.append({
                    "date": date_str,
                    "time": f"{h:02d}:{m:02d}",
                    "rationale": "No calendar conflict (no preference/energy checks applied)",
                })
        if len(proposed_slots) >= 3:
            break

    # Always ACT — no contract prevents it
    trace.append("DEFAULT: ACT — no contract governance prevents autonomous booking")

    return _agenda_result(email, contact, None, "ACT",
        "Booking autonomously — no contract governance in place",
        trace, signals_used, [], warnings,
        proposed_slots=proposed_slots,
        excluded_slots=[])


# ---------------------------------------------------------------------------
# Result builders
# ---------------------------------------------------------------------------

def _email_result(email, contact, ref, decision, reason, trace,
                  signals_used, signals_missing, warnings,
                  draft=None) -> dict:
    return {
        "email": {
            "message_id": email["message_id"],
            "thread_id": email["thread_id"],
            "sender": email["sender"],
            "date": email["date"],
            "subject": email["subject"],
            "body": email["body"],
            "labels": email.get("labels", []),
            "tone": email.get("tone"),
            "purpose": email.get("purpose"),
            "urgency_score": email.get("urgency_score"),
            "call_to_action": email.get("call_to_action"),
            "classification_confidence": email.get("classification_confidence"),
            "thread_completeness": email.get("thread_completeness"),
            "tone_shift": email.get("tone_shift"),
            "handling_constraint": email.get("handling_constraint"),
        },
        "contact": {
            "contact_id": contact["contact_id"],
            "name": contact["name"],
            "relationship_type": contact.get("relationship_type"),
            "temporal_importance": contact.get("temporal_importance"),
            "auto_reply_policy": contact.get("auto_reply_policy"),
            "open_context_flag": contact.get("open_context_flag"),
        } if contact else None,
        "reference": {
            "topic_id": ref["topic_id"],
            "topic_name": ref["topic_name"],
            "context_completeness": ref["context_completeness"],
            "action_threshold": ref["action_threshold"],
            "momentum": ref.get("momentum"),
            "off_system_refs": ref.get("off_system_refs", []),
        } if ref else None,
        "output": {
            "decision": decision,
            "reason": reason,
            "draft_reply": draft,
        },
        "decision_logic": {
            "trace": trace,
            "signals_used": signals_used,
            "signals_missing": signals_missing,
            "warnings": warnings,
        },
    }


def _agenda_result(email, contact, ref, decision, reason, trace,
                   signals_used, signals_missing, warnings,
                   proposed_slots=None, excluded_slots=None) -> dict:
    return {
        "email": {
            "message_id": email["message_id"],
            "thread_id": email["thread_id"],
            "sender": email["sender"],
            "date": email["date"],
            "subject": email["subject"],
            "body": email["body"],
            "labels": email.get("labels", []),
            "purpose": email.get("purpose"),
            "urgency_score": email.get("urgency_score"),
            "call_to_action": email.get("call_to_action"),
        },
        "contact": {
            "contact_id": contact["contact_id"],
            "name": contact["name"],
            "relationship_type": contact.get("relationship_type"),
            "temporal_importance": contact.get("temporal_importance"),
            "auto_reply_policy": contact.get("auto_reply_policy"),
        } if contact else None,
        "reference": {
            "topic_id": ref["topic_id"],
            "topic_name": ref["topic_name"],
            "action_threshold": ref["action_threshold"],
        } if ref else None,
        "output": {
            "decision": decision,
            "reason": reason,
            "proposed_slots": proposed_slots or [],
            "excluded_slots": excluded_slots or [],
        },
        "decision_logic": {
            "trace": trace,
            "signals_used": signals_used,
            "signals_missing": signals_missing,
            "warnings": warnings,
        },
    }


def _generate_draft(email, contact, ref, context: str) -> str:
    """Generate a placeholder draft reply."""
    sender = contact["name"] if contact else email["sender"].split("@")[0]
    subject = email["subject"]
    purpose = email.get("purpose", "message")

    if purpose == "inform" or not email.get("call_to_action"):
        return f"Hi {sender},\n\nThank you for the update. Noted.\n\nBest,\nAlex"
    if purpose == "request":
        return (
            f"Hi {sender},\n\nThank you for reaching out regarding \"{subject}\". "
            f"I've reviewed your message and will follow up shortly with a detailed response.\n\n"
            f"Best,\nAlex"
        )
    if purpose == "escalation":
        return (
            f"Hi {sender},\n\nThank you for flagging this. I understand the urgency around "
            f"\"{subject}\" and will prioritise this today.\n\nBest,\nAlex"
        )
    return f"Hi {sender},\n\nThank you for your message. I'll review and get back to you.\n\nBest,\nAlex"


def _extract_time_signals(body: str) -> dict:
    """Extract scheduling hints from email body."""
    signals: dict[str, Any] = {}
    low = body.lower()

    # Duration
    dur_match = re.search(r"(\d+)\s*(?:min|minute)", low)
    if dur_match:
        signals["requested_duration_minutes"] = int(dur_match.group(1))
    else:
        signals["requested_duration_minutes"] = 30

    # Day mentions
    days = []
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
        if day in low:
            days.append(day)
    if days:
        signals["mentioned_days"] = days

    # Time mentions
    time_match = re.findall(r"(\d{1,2})\s*(?:am|pm|:00|h)", low)
    if time_match:
        signals["mentioned_times"] = time_match

    # This week / next week
    if "this week" in low:
        signals["timeframe"] = "this_week"
    elif "next week" in low:
        signals["timeframe"] = "next_week"

    return signals


def _get_target_dates(email: dict) -> list[datetime]:
    """Determine target dates for scheduling based on email content."""
    base = datetime(2026, 4, 16)
    body_low = email["body"].lower()

    if "next week" in body_low:
        # Mon Apr 21 to Fri Apr 25
        mon = base + timedelta(days=(7 - base.weekday()))
        return [mon + timedelta(days=i) for i in range(5)]

    if "this week" in body_low:
        # Remaining days this week (Thu Apr 17, Fri Apr 18)
        days_left = 4 - base.weekday()  # days until Friday
        if days_left <= 0:
            days_left = 1
        return [base + timedelta(days=i + 1) for i in range(days_left)]

    # Check specific day mentions
    day_map = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4}
    mentioned = []
    for day_name, day_num in day_map.items():
        if day_name in body_low:
            delta = (day_num - base.weekday()) % 7
            if delta == 0:
                delta = 7
            mentioned.append(base + timedelta(days=delta))
    if mentioned:
        return sorted(mentioned)

    # Default: next 5 business days
    dates = []
    d = base + timedelta(days=1)
    while len(dates) < 5:
        if d.weekday() < 5:
            dates.append(d)
        d += timedelta(days=1)
    return dates


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    output_dir = DATA_DIR

    files = {
        "email_a_with_contract": email_a_with_contract,
        "email_a_no_contract": email_a_no_contract,
        "agenda_a_with_contract": agenda_a_with_contract,
        "agenda_a_no_contract": agenda_a_no_contract,
    }

    for name, fn in files.items():
        path = output_dir / f"{name}.jsonl"
        count = 0
        with path.open("w") as f:
            for email in EMAILS:
                result = fn(email)
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                count += 1
        print(f"{path.name}: {count} records")

    # Print summary
    print("\n--- Summary ---")
    for name, fn in files.items():
        decisions: dict[str, int] = {}
        for email in EMAILS:
            result = fn(email)
            d = result["output"]["decision"]
            decisions[d] = decisions.get(d, 0) + 1
        print(f"{name}: {decisions}")


if __name__ == "__main__":
    main()
