import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response
from sqlalchemy import select

from ..config import get_settings
from ..database import SessionLocal
from ..models import Alert, Contact, Elder
from ..services import checkins as checkin_service
from ..services import keywords, prompts, stt, whatsapp
from ..timeutil import utcnow

log = logging.getLogger("lder.webhook")

router = APIRouter(prefix="/webhook", tags=["webhook"])

STOP_WORDS = {keywords.normalize(w) for w in ("stop", "നിർത്തുക", "nirthuka", "unsubscribe")}


@router.get("/whatsapp")
def verify(
    mode: str = Query(default="", alias="hub.mode"),
    token: str = Query(default="", alias="hub.verify_token"),
    challenge: str = Query(default="", alias="hub.challenge"),
):
    expected = get_settings().whatsapp_verify_token
    if mode == "subscribe" and expected and token == expected:
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/whatsapp")
async def receive(request: Request, background: BackgroundTasks):
    raw = await request.body()
    if not whatsapp.verify_signature(raw, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=403, detail="Invalid signature")
    try:
        payload = await request.json()
    except ValueError:
        return {"status": "ignored"}
    messages = whatsapp.parse_inbound(payload)
    if messages:
        background.add_task(handle_messages, messages)
    return {"status": "ok"}


def _safe_send(to: str, body: str) -> None:
    try:
        whatsapp.send_text(to, body)
    except whatsapp.WhatsAppError as exc:
        log.warning("Reply to %s failed: %s", to, exc)


def handle_messages(messages: list[whatsapp.InboundMessage]) -> None:
    db = SessionLocal()
    try:
        for message in messages:
            try:
                _handle_one(db, message)
            except Exception:
                db.rollback()
                log.exception("Failed to handle inbound WhatsApp message")
    finally:
        db.close()


def _handle_one(db, message: whatsapp.InboundMessage) -> None:
    now = utcnow()
    elders = db.scalars(select(Elder)).all()
    elder = next((e for e in elders if whatsapp.same_phone(e.phone, message.sender)), None)
    contacts = db.scalars(select(Contact)).all()
    contact = next((c for c in contacts if whatsapp.same_phone(c.phone, message.sender)), None)

    if contact is not None:
        contact.last_inbound_at = now
        pending = db.scalars(
            select(Alert)
            .where(Alert.contact_id == contact.id, Alert.acknowledged_at.is_(None))
            .order_by(Alert.sent_at.desc())
        ).first()
        db.commit()
        if pending is not None and message.kind == "text":
            checkin_service.acknowledge(db, pending)
            _safe_send(message.sender, "Thank you. The alert has been marked as acknowledged.")
        if elder is None:
            return

    if elder is None:
        return

    elder.last_inbound_at = now
    db.commit()

    if message.kind == "text" and keywords.normalize(message.text) in STOP_WORDS:
        elder.active = False
        db.commit()
        _safe_send(message.sender, "You will no longer receive check-ins. Your family can turn them back on.")
        return

    if elder.consent_at is None or not elder.active:
        return

    transcript = ""
    if message.kind == "audio" and message.media_id:
        try:
            audio, mime = whatsapp.download_media(message.media_id)
            transcript = stt.transcribe(audio, message.mime or mime)
        except (whatsapp.WhatsAppError, stt.TranscriptionError) as exc:
            log.warning("Could not transcribe WhatsApp audio: %s", exc)
            _safe_send(message.sender, prompts.PROMPTS["unclear"].text_ml)
            return
    elif message.kind == "text":
        transcript = message.text.strip()
    else:
        return

    if not transcript:
        _safe_send(message.sender, prompts.PROMPTS["unclear"].text_ml)
        return

    open_checkin = checkin_service.find_open_checkin(db, elder, now)
    checkin, decision = checkin_service.process_reply(db, elder, open_checkin, transcript, "whatsapp")
    checkin_service.send_ack(elder, "ack_help" if decision.severity == "critical" else "ack_ok", utcnow())
