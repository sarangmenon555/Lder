from datetime import datetime, time as dtime, timedelta, timezone
from typing import Sequence

from ..timeutil import zone_or_default


def plan_retry(
    attempt: int,
    last_prompt_at: datetime,
    now: datetime,
    delays: Sequence[int],
    final_wait: int,
) -> str:
    if attempt <= len(delays):
        due = last_prompt_at + timedelta(minutes=delays[attempt - 1])
        return "retry" if now >= due else "wait"
    due = last_prompt_at + timedelta(minutes=final_wait)
    return "miss" if now >= due else "wait"


def escalation_due(last_escalation_at: datetime | None, now: datetime, delay_minutes: int) -> bool:
    if last_escalation_at is None:
        return True
    return now >= last_escalation_at + timedelta(minutes=delay_minutes)


def pick_contact(contacts: Sequence, level: int):
    if 0 <= level < len(contacts):
        return contacts[level]
    return None


def due_slots(
    check_in_times: Sequence[str],
    tz_name: str,
    now: datetime,
    grace_minutes: int,
) -> list[tuple[str, datetime]]:
    tz = zone_or_default(tz_name)
    local_now = now.astimezone(tz)
    slots: list[tuple[str, datetime]] = []
    for label in check_in_times:
        hour, minute = (int(part) for part in label.split(":"))
        for offset in (0, -1):
            day = (local_now + timedelta(days=offset)).date()
            local_dt = datetime.combine(day, dtime(hour, minute), tzinfo=tz)
            slot_utc = local_dt.astimezone(timezone.utc)
            if slot_utc <= now < slot_utc + timedelta(minutes=grace_minutes):
                slots.append((label, slot_utc))
    return slots
