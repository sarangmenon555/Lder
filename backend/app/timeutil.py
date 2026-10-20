from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def valid_zone(name: str) -> bool:
    try:
        ZoneInfo(name)
        return True
    except Exception:
        return False


def zone_or_default(name: str | None, default: str = "Asia/Kolkata") -> ZoneInfo:
    try:
        return ZoneInfo(name or default)
    except Exception:
        return ZoneInfo(default)


def to_local(dt: datetime, tz_name: str | None) -> datetime:
    return dt.astimezone(zone_or_default(tz_name))


def format_local(dt: datetime, tz_name: str | None) -> str:
    local = to_local(dt, tz_name)
    return local.strftime("%d %b %Y, %I:%M %p") + " " + (local.tzname() or "")
