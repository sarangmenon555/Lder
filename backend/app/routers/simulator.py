from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Elder
from ..schemas import PromptOut, ReplyOut, SimulatorState
from ..services import checkins as checkin_service
from ..services import prompts, stt
from ..timeutil import utcnow

router = APIRouter(prefix="/simulator", tags=["simulator"])


def _elder(db: Session, token: str) -> Elder:
    elder = db.scalar(select(Elder).where(Elder.access_token == token))
    if elder is None:
        raise HTTPException(status_code=404, detail="This link is not valid")
    return elder


def _prompt_out(checkin) -> PromptOut:
    key = prompts.prompt_key(checkin.kind, checkin.attempt)
    prompts.ensure_audio(key)
    prompt = prompts.PROMPTS[key]
    return PromptOut(
        checkin_id=checkin.id,
        text_ml=prompt.text_ml,
        text_en=prompt.text_en,
        audio_url=prompts.audio_url(key),
    )


@router.get("/{token}", response_model=SimulatorState)
def state(token: str, db: Session = Depends(get_db)):
    elder = _elder(db, token)
    open_checkin = checkin_service.find_open_checkin(db, elder, utcnow())
    awaiting = _prompt_out(open_checkin) if open_checkin and open_checkin.status == "awaiting_reply" else None
    return SimulatorState(
        elder_name=elder.name,
        consent=elder.consent_at is not None,
        active=elder.active,
        awaiting=awaiting,
    )


@router.post("/{token}/start", response_model=PromptOut)
def start(token: str, db: Session = Depends(get_db)):
    elder = _elder(db, token)
    if elder.consent_at is None or not elder.active:
        raise HTTPException(status_code=403, detail="Check-ins are not enabled for this person")
    now = utcnow()
    open_checkin = checkin_service.find_open_checkin(db, elder, now)
    if open_checkin is None or open_checkin.status != "awaiting_reply":
        open_checkin = checkin_service.create_checkin(db, elder, now, channel="simulator")
        open_checkin.last_prompt_at = now
        db.commit()
    return _prompt_out(open_checkin)


@router.post("/{token}/reply", response_model=ReplyOut)
def reply(
    token: str,
    audio: UploadFile | None = File(default=None),
    text: str = Form(default=""),
    db: Session = Depends(get_db),
):
    elder = _elder(db, token)
    if elder.consent_at is None or not elder.active:
        raise HTTPException(status_code=403, detail="Check-ins are not enabled for this person")
    transcript = text.strip()
    if audio is not None:
        content = audio.file.read()
        try:
            transcript = stt.transcribe(content, audio.content_type)
        except stt.TranscriptionError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"The voice message could not be transcribed ({exc}). You can type the reply instead.",
            )
    if not transcript:
        raise HTTPException(status_code=422, detail="No speech was detected. Please try again.")
    return _process(db, elder, transcript)


def _process(db: Session, elder: Elder, transcript: str) -> ReplyOut:
    now = utcnow()
    open_checkin = checkin_service.find_open_checkin(db, elder, now)
    checkin, decision = checkin_service.process_reply(db, elder, open_checkin, transcript, "simulator")
    key = "ack_help" if decision.severity == "critical" else "ack_ok"
    prompts.ensure_audio(key)
    prompt = prompts.PROMPTS[key]
    return ReplyOut(
        transcript=transcript,
        ack_text_ml=prompt.text_ml,
        ack_text_en=prompt.text_en,
        ack_audio_url=prompts.audio_url(key),
        family_notified=decision.severity in ("critical", "warning"),
    )


@router.post("/{token}/opt-out")
def opt_out(token: str, db: Session = Depends(get_db)):
    elder = _elder(db, token)
    elder.active = False
    db.commit()
    return {"ok": True}
