import logging
import threading
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Alert, CheckIn, Contact, Elder, SummaryLog
from ..timeutil import format_local, utcnow, zone_or_default
from . import classifier, escalation, keywords, notifier, prompts, whatsapp

log = logging.getLogger("lder.checkins")

_tick_lock = threading.Lock()


def kind_for(elder: Elder, when: datetime) -> str:
    local = when.astimezone(zone_or_default(elder.timezone))
    return "morning" if local.hour < 15 else "evening"


def due_medicine_names(elder: Elder, when: datetime) -> list[str]:
    local = when.astimezone(zone_or_default(elder.timezone))
    minutes = local.hour * 60 + local.minute
    names = []
    for medicine in elder.medicines:
        hour, minute = (int(p) for p in medicine.time_of_day.split(":"))
        diff = abs(hour * 60 + minute - minutes)
        if min(diff, 1440 - diff) <= 90:
            names.append(medicine.name)
    return names


def default_channel(elder: Elder) -> str:
    return "whatsapp" if (whatsapp.enabled() and elder.phone) else "simulator"


def create_checkin(
    db: Session,
    elder: Elder,
    scheduled_at: datetime,
    channel: str | None = None,
    kind: str | None = None,
) -> CheckIn:
    checkin = CheckIn(
        elder_id=elder.id,
        scheduled_at=scheduled_at,
        kind=kind or kind_for(elder, scheduled_at),
        channel=channel or default_channel(elder),
        status="awaiting_reply",
        attempt=1,
    )
    db.add(checkin)
    db.commit()
    return checkin


def send_prompt(db: Session, checkin: CheckIn, elder: Elder, now: datetime | None = None) -> None:
    now = now or utcnow()
    key = prompts.prompt_key(checkin.kind, checkin.attempt)
    prompt = prompts.PROMPTS[key]
    body = prompt.text_ml
    names = due_medicine_names(elder, checkin.scheduled_at)
    if names:
        body += "\n\n" + ", ".join(names)
    if checkin.channel == "whatsapp" and whatsapp.enabled() and elder.phone:
        try:
            whatsapp.send_to_elder(elder, body, prompts.ensure_audio(key), now)
        except Exception as exc:
            log.warning("Could not send prompt to elder %s: %s", elder.id, exc)
    checkin.last_prompt_at = now
    db.commit()


def send_ack(elder: Elder, key: str, now: datetime) -> None:
    if not (whatsapp.enabled() and elder.phone):
        return
    try:
        whatsapp.send_to_elder(elder, prompts.PROMPTS[key].text_ml, prompts.ensure_audio(key), now)
    except Exception as exc:
        log.warning("Could not send acknowledgement to elder %s: %s", elder.id, exc)


def find_open_checkin(db: Session, elder: Elder, now: datetime) -> CheckIn | None:
    since = now - timedelta(hours=6)
    return db.scalars(
        select(CheckIn)
        .where(
            CheckIn.elder_id == elder.id,
            CheckIn.status.in_(("awaiting_reply", "missed")),
            CheckIn.created_at >= since,
        )
        .order_by(CheckIn.created_at.desc())
    ).first()


def make_alert(
    db: Session,
    elder: Elder,
    checkin: CheckIn | None,
    contact: Contact | None,
    severity: str,
    reason: str,
) -> Alert:
    alert = Alert(
        elder_id=elder.id,
        checkin_id=checkin.id if checkin else None,
        contact_id=contact.id if contact else None,
        severity=severity,
        reason=reason,
    )
    db.add(alert)
    db.flush()
    notifier.dispatch_alert(db, alert, elder, contact, checkin, reason)
    db.commit()
    return alert


def _reason_for(decision: classifier.Decision) -> str:
    if decision.severity == "critical":
        return "distress"
    if decision.status in ("unwell", "confused", "unclear"):
        return "needs_follow_up"
    return "medicine_missed"


def notify_for_decision(
    db: Session,
    elder: Elder,
    checkin: CheckIn,
    decision: classifier.Decision,
    was_missed: bool,
) -> None:
    contacts = list(elder.contacts)
    if decision.severity == "critical":
        targets = contacts or [None]
        for contact in targets:
            make_alert(db, elder, checkin, contact, "critical", "distress")
    elif decision.severity == "warning":
        make_alert(db, elder, checkin, contacts[0] if contacts else None, "warning", _reason_for(decision))
    elif was_missed:
        contact_ids = db.scalars(
            select(Alert.contact_id).where(Alert.checkin_id == checkin.id, Alert.contact_id.is_not(None)).distinct()
        ).all()
        for contact in contacts:
            if contact.id in contact_ids:
                make_alert(db, elder, checkin, contact, "info", "late_response")


def detect_pattern(db: Session, elder: Elder, checkin: CheckIn, now: datetime) -> None:
    recent = db.scalars(
        select(CheckIn)
        .where(CheckIn.elder_id == elder.id, CheckIn.status == "completed", CheckIn.classification.is_not(None))
        .order_by(CheckIn.responded_at.desc())
        .limit(3)
    ).all()
    if len(recent) < 3:
        return
    if not all(c.mood == "low" or c.classification in ("unwell", "needs_help") for c in recent):
        return
    existing = db.scalar(
        select(Alert.id).where(
            Alert.elder_id == elder.id,
            Alert.reason == "pattern",
            Alert.sent_at >= now - timedelta(hours=24),
        )
    )
    if existing:
        return
    contacts = list(elder.contacts)
    make_alert(db, elder, checkin, contacts[0] if contacts else None, "warning", "pattern")


def process_reply(
    db: Session,
    elder: Elder,
    checkin: CheckIn | None,
    transcript: str,
    channel: str,
) -> tuple[CheckIn, classifier.Decision]:
    now = utcnow()
    was_missed = checkin is not None and checkin.status == "missed"
    if checkin is None:
        checkin = create_checkin(db, elder, now, channel=channel, kind="inbound")
    kw = keywords.analyze(transcript)
    llm = None
    error = None
    if transcript.strip():
        try:
            llm = classifier.classify_with_llm(
                transcript, due_medicine_names(elder, checkin.scheduled_at), checkin.kind
            )
        except classifier.ClassifierError as exc:
            error = str(exc)
            log.warning("Classifier unavailable: %s", exc)
    decision = classifier.build_decision(transcript, llm, kw, get_settings().confidence_threshold, error)
    checkin.transcript = transcript
    checkin.classification = decision.status
    checkin.medicine_taken = decision.medicine_taken
    checkin.distress = decision.distress
    checkin.mood = decision.mood
    checkin.confidence = decision.confidence
    checkin.summary = decision.summary
    checkin.keyword_hits = decision.keyword_hits
    checkin.classifier_error = decision.error
    checkin.status = "completed"
    checkin.responded_at = now
    checkin.escalation_active = False
    db.commit()
    notify_for_decision(db, elder, checkin, decision, was_missed)
    detect_pattern(db, elder, checkin, now)
    return checkin, decision


def escalate_next(db: Session, checkin: CheckIn, elder: Elder, now: datetime) -> None:
    contacts = list(elder.contacts)
    if not contacts:
        make_alert(db, elder, checkin, None, "warning", "missed_checkin")
        checkin.escalation_active = False
        db.commit()
        return
    contact = escalation.pick_contact(contacts, checkin.escalation_level)
    if contact is None:
        checkin.escalation_active = False
        db.commit()
        return
    make_alert(db, elder, checkin, contact, "warning", "missed_checkin")
    checkin.escalation_level += 1
    checkin.last_escalation_at = now
    if checkin.escalation_level >= len(contacts):
        checkin.escalation_active = False
    db.commit()


def force_missed(db: Session, elder: Elder) -> CheckIn:
    now = utcnow()
    checkin = create_checkin(db, elder, now, kind=kind_for(elder, now))
    checkin.status = "missed"
    checkin.attempt = 3
    checkin.last_prompt_at = now
    checkin.escalation_active = True
    checkin.escalation_level = 0
    db.commit()
    escalate_next(db, checkin, elder, now)
    return checkin


def acknowledge(db: Session, alert: Alert) -> Alert:
    now = utcnow()
    alert.acknowledged_at = now
    if alert.checkin_id:
        checkin = db.get(CheckIn, alert.checkin_id)
        if checkin is not None:
            checkin.escalation_active = False
    db.commit()
    return alert


def build_summary(db: Session, elder: Elder, days: int = 7, now: datetime | None = None) -> dict:
    now = now or utcnow()
    tz = zone_or_default(elder.timezone)
    today = now.astimezone(tz).date()
    daily: dict[str, dict] = {}
    for i in range(days):
        key = (today - timedelta(days=days - 1 - i)).isoformat()
        daily[key] = {"date": key, "yes": 0, "no": 0, "unknown": 0, "responded": 0, "missed": 0}
    since = now - timedelta(days=days + 1)
    rows = db.scalars(
        select(CheckIn).where(CheckIn.elder_id == elder.id, CheckIn.scheduled_at >= since).order_by(CheckIn.scheduled_at)
    ).all()
    total = responded = missed = 0
    yes = no = unknown = 0
    status_counts: dict[str, int] = {}
    mood_counts: dict[str, int] = {}
    notes: list[str] = []
    for row in rows:
        key = row.scheduled_at.astimezone(tz).date().isoformat()
        if key not in daily:
            continue
        total += 1
        bucket = daily[key]
        if row.status == "completed":
            responded += 1
            bucket["responded"] += 1
            status_counts[row.classification or "unclear"] = status_counts.get(row.classification or "unclear", 0) + 1
            if row.mood and row.mood != "unknown":
                mood_counts[row.mood] = mood_counts.get(row.mood, 0) + 1
            if row.medicine_taken == "yes":
                yes += 1
                bucket["yes"] += 1
            elif row.medicine_taken == "no":
                no += 1
                bucket["no"] += 1
            else:
                unknown += 1
                bucket["unknown"] += 1
            if row.summary:
                notes.append(f"{format_local(row.responded_at or row.scheduled_at, elder.timezone)}: {row.summary}")
        elif row.status == "missed":
            missed += 1
            bucket["missed"] += 1
    alerts_total = db.scalar(
        select(func.count(Alert.id)).where(Alert.elder_id == elder.id, Alert.sent_at >= since, Alert.severity != "info")
    ) or 0
    critical = db.scalar(
        select(func.count(Alert.id)).where(Alert.elder_id == elder.id, Alert.sent_at >= since, Alert.severity == "critical")
    ) or 0
    return {
        "period_days": days,
        "total": total,
        "responded": responded,
        "missed": missed,
        "response_rate": round(100 * responded / total) if total else None,
        "medicine_yes": yes,
        "medicine_no": no,
        "medicine_unknown": unknown,
        "adherence_pct": round(100 * yes / (yes + no)) if (yes + no) else None,
        "status_counts": status_counts,
        "mood_counts": mood_counts,
        "alerts_total": alerts_total,
        "critical_alerts": critical,
        "daily": list(daily.values()),
        "recent_summaries": notes[-3:],
    }


def send_weekly_summaries(db: Session, now: datetime) -> None:
    s = get_settings()
    if now.weekday() != s.summary_weekday or now.hour != s.summary_hour_utc:
        return
    iso = now.isocalendar()
    week_key = f"{iso[0]}-W{iso[1]:02d}"
    for elder in db.scalars(select(Elder).where(Elder.active.is_(True))).all():
        db.add(SummaryLog(elder_id=elder.id, week_key=week_key))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        stats = build_summary(db, elder, 7, now)
        for contact in elder.contacts:
            if contact.email and contact.channel in ("email", "both"):
                subject, body = notifier.compose_summary(elder, contact, stats)
                try:
                    notifier.send_email(contact.email, subject, body)
                except notifier.NotifierError as exc:
                    log.warning("Weekly summary email failed: %s", exc)


def _handle_awaiting(db: Session, checkin: CheckIn, now: datetime) -> None:
    elder = db.get(Elder, checkin.elder_id)
    if elder is None or not elder.active:
        checkin.status = "cancelled"
        db.commit()
        return
    settings = get_settings()
    action = escalation.plan_retry(
        checkin.attempt,
        checkin.last_prompt_at or checkin.created_at,
        now,
        settings.retry_delays,
        settings.final_wait_minutes,
    )
    if action == "retry":
        checkin.attempt += 1
        db.commit()
        send_prompt(db, checkin, elder, now)
    elif action == "miss":
        checkin.status = "missed"
        checkin.escalation_active = True
        checkin.escalation_level = 0
        db.commit()
        escalate_next(db, checkin, elder, now)


def _handle_escalating(db: Session, checkin: CheckIn, now: datetime) -> None:
    elder = db.get(Elder, checkin.elder_id)
    if elder is None:
        return
    acknowledged = db.scalar(
        select(Alert.id).where(Alert.checkin_id == checkin.id, Alert.acknowledged_at.is_not(None))
    )
    if acknowledged:
        checkin.escalation_active = False
        db.commit()
        return
    if escalation.escalation_due(checkin.last_escalation_at, now, get_settings().escalation_delay_minutes):
        escalate_next(db, checkin, elder, now)


def run_tick(db: Session, now: datetime | None = None) -> dict:
    if not _tick_lock.acquire(blocking=False):
        return {"skipped": True}
    try:
        now = now or utcnow()
        settings = get_settings()
        created = 0
        for elder in db.scalars(select(Elder).where(Elder.active.is_(True))).all():
            if elder.consent_at is None:
                continue
            for _, slot in escalation.due_slots(elder.check_in_times, elder.timezone, now, settings.slot_grace_minutes):
                exists = db.scalar(
                    select(CheckIn.id).where(CheckIn.elder_id == elder.id, CheckIn.scheduled_at == slot)
                )
                if exists:
                    continue
                try:
                    checkin = create_checkin(db, elder, slot)
                except IntegrityError:
                    db.rollback()
                    continue
                created += 1
                send_prompt(db, checkin, elder, now)
        for checkin in db.scalars(select(CheckIn).where(CheckIn.status == "awaiting_reply")).all():
            _handle_awaiting(db, checkin, now)
        for checkin in db.scalars(select(CheckIn).where(CheckIn.escalation_active.is_(True))).all():
            _handle_escalating(db, checkin, now)
        send_weekly_summaries(db, now)
        return {"skipped": False, "created": created}
    finally:
        _tick_lock.release()
