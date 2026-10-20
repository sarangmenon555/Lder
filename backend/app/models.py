import secrets
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from .crypto import EncryptedText
from .database import Base
from .timeutil import utcnow


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


class Elder(Base):
    __tablename__ = "elders"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(32), default="")
    language: Mapped[str] = mapped_column(String(8), default="ml")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    check_in_times: Mapped[list] = mapped_column(JSON, default=list)
    consent_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    access_token: Mapped[str] = mapped_column(
        String(64), unique=True, default=lambda: secrets.token_urlsafe(24)
    )
    last_inbound_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="elder", cascade="all, delete-orphan", order_by="Contact.priority"
    )
    medicines: Mapped[list["Medicine"]] = relationship(
        back_populates="elder", cascade="all, delete-orphan", order_by="Medicine.time_of_day"
    )
    checkins: Mapped[list["CheckIn"]] = relationship(
        back_populates="elder", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="elder", cascade="all, delete-orphan"
    )


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(32), default="")
    channel: Mapped[str] = mapped_column(String(16), default="dashboard")
    priority: Mapped[int] = mapped_column(Integer, default=1)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    last_inbound_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    elder: Mapped["Elder"] = relationship(back_populates="contacts")


class Medicine(Base):
    __tablename__ = "medicines"

    id: Mapped[int] = mapped_column(primary_key=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    time_of_day: Mapped[str] = mapped_column(String(5), default="08:00")

    elder: Mapped["Elder"] = relationship(back_populates="medicines")


class CheckIn(Base):
    __tablename__ = "checkins"
    __table_args__ = (UniqueConstraint("elder_id", "scheduled_at", name="uq_checkin_slot"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(UTCDateTime)
    kind: Mapped[str] = mapped_column(String(16), default="morning")
    channel: Mapped[str] = mapped_column(String(16), default="simulator")
    status: Mapped[str] = mapped_column(String(16), default="awaiting_reply", index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    last_prompt_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    escalation_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    last_escalation_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    transcript: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    classification: Mapped[str | None] = mapped_column(String(16), nullable=True)
    medicine_taken: Mapped[str | None] = mapped_column(String(8), nullable=True)
    distress: Mapped[bool] = mapped_column(Boolean, default=False)
    mood: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    keyword_hits: Mapped[list] = mapped_column(JSON, default=list)
    classifier_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    elder: Mapped["Elder"] = relationship(back_populates="checkins")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), index=True)
    checkin_id: Mapped[int | None] = mapped_column(
        ForeignKey("checkins.id", ondelete="CASCADE"), nullable=True, index=True
    )
    contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    severity: Mapped[str] = mapped_column(String(16), default="warning")
    reason: Mapped[str] = mapped_column(String(32), default="needs_follow_up")
    message: Mapped[str] = mapped_column(EncryptedText, default="")
    channel: Mapped[str] = mapped_column(String(32), default="dashboard")
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    elder: Mapped["Elder"] = relationship(back_populates="alerts")


class SummaryLog(Base):
    __tablename__ = "summary_logs"
    __table_args__ = (UniqueConstraint("elder_id", "week_key", name="uq_summary_week"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"))
    week_key: Mapped[str] = mapped_column(String(12))
