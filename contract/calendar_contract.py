"""CalendarContractView dataclass + builder."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Optional

from config import CALENDAR_STALENESS_THRESHOLD_MINUTES


@dataclass
class CalendarContractView:
    event_count: int
    next_event_title: Optional[str]
    next_event_start: Optional[str]
    # Extended (agent-aware) — None in standard mode.
    data_age_minutes: Optional[int] = None
    safe_to_act: Optional[bool] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_calendar_view(
    events: list[dict[str, Any]],
    mode_name: str,
    loaded_at: datetime,
) -> CalendarContractView:
    now = datetime.now(timezone.utc)
    future = [e for e in events if e["start"] >= now.isoformat().replace("+00:00", "Z")]
    next_event = future[0] if future else None
    view = CalendarContractView(
        event_count=len(events),
        next_event_title=next_event["title"] if next_event else None,
        next_event_start=next_event["start"] if next_event else None,
    )
    if mode_name == "extended":
        age = int((now - loaded_at).total_seconds() // 60)
        view.data_age_minutes = max(age, 0)
        view.safe_to_act = view.data_age_minutes <= CALENDAR_STALENESS_THRESHOLD_MINUTES
    return view
