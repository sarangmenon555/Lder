from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Alert, CheckIn, Contact, Elder
from ..schemas import AlertOut, CheckInOut, SummaryOut, TriggerIn
from ..security import require_auth
from ..services import checkins as checkin_service
from ..timeutil import utcnow

router = APIRouter(tags=["monitoring"], dependencies=[Depends(require_auth)])


def _elder(db: Session, elder_id: int) -> Elder:
    elder = db.get(Elder, elder_id)
    if elder is None:
        raise HTTPException(status_code=404, detail="Person not found")
    return elder


def _alert_out(db: Session, alert: Alert, elder_names: dict[int, str]) -> AlertOut:
    contact_name = None
    if alert.contact_id:
        contact = db.get(Contact, alert.contact_id)
        contact_name = contact.name if contact else None
    return AlertOut(
        id=alert.id,
        elder_id=alert.elder_id,
        elder_name=elder_names.get(alert.elder_id, ""),
        checkin_id=alert.checkin_id,
        contact_id=alert.contact_id,
        contact_name=contact_name,
        severity=alert.severity,
        reason=alert.reason,
        message=alert.message,
        channel=alert.channel,
        delivered=alert.delivered,
        error=alert.error,
        sent_at=alert.sent_at,
        acknowledged_at=alert.acknowledged_at,
    )


@router.get("/elders/{elder_id}/checkins", response_model=list[CheckInOut])
def list_checkins(elder_id: int, limit: int = Query(30, ge=1, le=200), db: Session = Depends(get_db)):
    _elder(db, elder_id)
    rows = db.scalars(
        select(CheckIn).where(CheckIn.elder_id == elder_id).order_by(CheckIn.scheduled_at.desc()).limit(limit)
    ).all()
    return [CheckInOut.model_validate(row) for row in rows]


@router.get("/elders/{elder_id}/summary", response_model=SummaryOut)
def summary(elder_id: int, days: int = Query(7, ge=1, le=30), db: Session = Depends(get_db)):
    elder = _elder(db, elder_id)
    return SummaryOut(**checkin_service.build_summary(db, elder, days))


@router.post("/elders/{elder_id}/trigger-checkin", response_model=CheckInOut)
def trigger_checkin(elder_id: int, payload: TriggerIn, db: Session = Depends(get_db)):
    elder = _elder(db, elder_id)
    if elder.consent_at is None:
        raise HTTPException(status_code=400, detail="Record the person's consent before starting check-ins")
    if payload.mode == "missed":
        checkin = checkin_service.force_missed(db, elder)
    else:
        now = utcnow()
        checkin = checkin_service.create_checkin(db, elder, now)
        checkin_service.send_prompt(db, checkin, elder, now)
    return CheckInOut.model_validate(checkin)


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(
    acknowledged: bool | None = None,
    elder_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = select(Alert).order_by(Alert.sent_at.desc()).limit(limit)
    if acknowledged is True:
        query = query.where(Alert.acknowledged_at.is_not(None))
    elif acknowledged is False:
        query = query.where(Alert.acknowledged_at.is_(None), Alert.severity != "info")
    if elder_id is not None:
        query = query.where(Alert.elder_id == elder_id)
    names = {e.id: e.name for e in db.scalars(select(Elder)).all()}
    return [_alert_out(db, alert, names) for alert in db.scalars(query).all()]


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    checkin_service.acknowledge(db, alert)
    names = {e.id: e.name for e in db.scalars(select(Elder)).all()}
    return _alert_out(db, alert, names)
