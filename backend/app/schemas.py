import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .timeutil import valid_zone

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _check_time(value: str) -> str:
    if not TIME_RE.match(value):
        raise ValueError("Time must be in HH:MM format")
    return value


def _check_zone(value: str) -> str:
    if not valid_zone(value):
        raise ValueError("Unknown time zone")
    return value


class ContactIn(BaseModel):
    id: int | None = None
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(default="", max_length=200)
    phone: str = ""
    channel: Literal["email", "whatsapp", "both", "dashboard"] = "dashboard"
    priority: int = Field(default=1, ge=1, le=20)
    timezone: str = "Asia/Kolkata"

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        return _check_zone(v)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return re.sub(r"\D", "", v or "")


class MedicineIn(BaseModel):
    id: int | None = None
    name: str = Field(min_length=1, max_length=120)
    time_of_day: str = "08:00"

    @field_validator("time_of_day")
    @classmethod
    def _time(cls, v: str) -> str:
        return _check_time(v)


class ElderIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = ""
    language: str = "ml"
    timezone: str = "Asia/Kolkata"
    check_in_times: list[str] = Field(default_factory=lambda: ["08:30", "19:00"])
    consent: bool = False
    active: bool = True
    contacts: list[ContactIn] = Field(default_factory=list)
    medicines: list[MedicineIn] = Field(default_factory=list)

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        return _check_zone(v)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return re.sub(r"\D", "", v or "")

    @field_validator("check_in_times")
    @classmethod
    def _times(cls, v: list[str]) -> list[str]:
        cleaned = sorted({_check_time(t) for t in v})
        if len(cleaned) > 6:
            raise ValueError("At most 6 check-in times are allowed")
        return cleaned


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    phone: str
    channel: str
    priority: int
    timezone: str


class MedicineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    time_of_day: str


class CheckInOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    elder_id: int
    scheduled_at: datetime
    kind: str
    channel: str
    status: str
    attempt: int
    escalation_active: bool
    escalation_level: int
    transcript: str | None
    classification: str | None
    medicine_taken: str | None
    distress: bool
    mood: str | None
    confidence: float | None
    summary: str | None
    keyword_hits: list[str]
    classifier_error: str | None
    responded_at: datetime | None


class ElderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    phone: str
    language: str
    timezone: str
    check_in_times: list[str]
    consent_at: datetime | None
    active: bool
    access_token: str
    created_at: datetime
    contacts: list[ContactOut]
    medicines: list[MedicineOut]


class ElderListItem(ElderOut):
    latest_checkin: CheckInOut | None = None
    open_alerts: int = 0
    adherence_7d: int | None = None


class AlertOut(BaseModel):
    id: int
    elder_id: int
    elder_name: str
    checkin_id: int | None
    contact_id: int | None
    contact_name: str | None
    severity: str
    reason: str
    message: str
    channel: str
    delivered: bool
    error: str | None
    sent_at: datetime
    acknowledged_at: datetime | None


class DailyStat(BaseModel):
    date: str
    yes: int
    no: int
    unknown: int
    responded: int
    missed: int


class SummaryOut(BaseModel):
    period_days: int
    total: int
    responded: int
    missed: int
    response_rate: int | None
    medicine_yes: int
    medicine_no: int
    medicine_unknown: int
    adherence_pct: int | None
    status_counts: dict[str, int]
    mood_counts: dict[str, int]
    alerts_total: int
    critical_alerts: int
    daily: list[DailyStat]
    recent_summaries: list[str]


class TriggerIn(BaseModel):
    mode: Literal["normal", "missed"] = "normal"


class LoginIn(BaseModel):
    password: str


class PromptOut(BaseModel):
    checkin_id: int
    text_ml: str
    text_en: str
    audio_url: str | None


class SimulatorState(BaseModel):
    elder_name: str
    consent: bool
    active: bool
    awaiting: PromptOut | None


class ReplyOut(BaseModel):
    transcript: str
    ack_text_ml: str
    ack_text_en: str
    ack_audio_url: str | None
    family_notified: bool
