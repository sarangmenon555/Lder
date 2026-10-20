import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage

from ..config import get_settings
from ..timeutil import format_local, utcnow
from . import whatsapp

log = logging.getLogger("lder.notifier")


class NotifierError(Exception):
    pass


TITLES = {
    "distress": "Urgent: {name} may need help",
    "missed_checkin": "Missed check-in: {name} has not replied",
    "needs_follow_up": "Follow-up suggested: {name}",
    "medicine_missed": "Medicine not taken: {name}",
    "pattern": "Pattern noticed: {name} has seemed unwell for several check-ins",
    "late_response": "Update: {name} has now replied",
}

ACTIONS = {
    "distress": "Please call {name} right away.",
    "missed_checkin": "Please try calling {name} now.",
    "needs_follow_up": "Please call {name} when you can.",
    "medicine_missed": "Please remind {name} about the medicine.",
    "pattern": "Please arrange a call or a visit.",
    "late_response": "No further action is needed unless you are still concerned.",
}

FOOTER = (
    "Lder is a check-in aid, not an emergency service. If you cannot reach {name} and are worried, "
    "contact local emergency services (112 in India)."
)


def email_enabled() -> bool:
    s = get_settings()
    return bool(s.smtp_user and s.smtp_password)


def send_email(to: str, subject: str, body: str) -> None:
    s = get_settings()
    if not email_enabled():
        raise NotifierError("SMTP is not configured")
    if not to:
        raise NotifierError("Contact has no email address")
    message = EmailMessage()
    message["From"] = s.smtp_from or s.smtp_user
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as server:
            server.starttls()
            server.login(s.smtp_user, s.smtp_password)
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        raise NotifierError(f"Email failed: {exc}") from exc


def compose_alert(elder, contact, checkin, reason: str, when: datetime) -> tuple[str, str]:
    s = get_settings()
    tz = contact.timezone if contact is not None else elder.timezone
    subject = "[Lder] " + TITLES.get(reason, "Check-in update: {name}").format(name=elder.name)
    lines = [
        TITLES.get(reason, "Check-in update: {name}").format(name=elder.name),
        "",
        f"Time: {format_local(when, tz)}",
        f"Local time for {elder.name}: {format_local(when, elder.timezone)}",
    ]
    if checkin is not None and checkin.summary:
        lines.append(f"Summary: {checkin.summary}")
    if checkin is not None and checkin.transcript:
        excerpt = checkin.transcript.strip().replace("\n", " ")
        if len(excerpt) > 240:
            excerpt = excerpt[:240] + "..."
        lines.append(f'What they said: "{excerpt}"')
    lines += [
        "",
        ACTIONS.get(reason, "").format(name=elder.name),
        f"Dashboard: {s.frontend_base_url.rstrip('/')}/elders/{elder.id}",
        "To acknowledge, reply OK to this message on WhatsApp or press Acknowledge in the dashboard.",
        "",
        FOOTER.format(name=elder.name),
    ]
    return subject, "\n".join(line for line in lines)


def dispatch_alert(db, alert, elder, contact, checkin, reason: str) -> None:
    now = utcnow()
    subject, body = compose_alert(elder, contact, checkin, reason, now)
    alert.message = body
    channels: list[str] = []
    if contact is not None:
        if contact.channel in ("email", "both"):
            channels.append("email")
        if contact.channel in ("whatsapp", "both"):
            channels.append("whatsapp")
    delivered: list[str] = []
    errors: list[str] = []
    for channel in channels:
        try:
            if channel == "email":
                send_email(contact.email, subject, body)
            else:
                whatsapp.send_to_contact(contact, subject + "\n\n" + body, now)
            delivered.append(channel)
        except Exception as exc:
            log.warning("Alert delivery via %s failed: %s", channel, exc)
            errors.append(f"{channel}: {exc}")
    if not channels:
        alert.channel = "dashboard"
        alert.delivered = True
    else:
        alert.channel = "+".join(delivered) if delivered else "+".join(channels)
        alert.delivered = bool(delivered)
    alert.error = "; ".join(errors) if errors else None


def compose_summary(elder, contact, stats: dict) -> tuple[str, str]:
    s = get_settings()
    rate = stats["response_rate"]
    adherence = stats["adherence_pct"]
    lines = [
        f"Weekly summary for {elder.name}",
        "",
        f"Check-ins: {stats['total']} scheduled, {stats['responded']} answered, {stats['missed']} missed"
        + (f" ({rate}% answered)." if rate is not None else "."),
        "Medicine: "
        + (f"{adherence}% of reported doses were taken." if adherence is not None else "no clear reports this week."),
        f"Alerts raised: {stats['alerts_total']} (urgent: {stats['critical_alerts']}).",
    ]
    if stats["status_counts"]:
        mix = ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in sorted(stats["status_counts"].items()))
        lines.append(f"How the replies looked: {mix}.")
    if stats["recent_summaries"]:
        lines += ["", "Recent notes:"] + [f"- {item}" for item in stats["recent_summaries"]]
    lines += ["", f"Dashboard: {s.frontend_base_url.rstrip('/')}/elders/{elder.id}"]
    return f"[Lder] Weekly summary for {elder.name}", "\n".join(lines)
