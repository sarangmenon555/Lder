from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Alert, CheckIn, Contact, Elder, Medicine
from ..schemas import ElderIn, ElderListItem, ElderOut, CheckInOut, ContactIn, MedicineIn
from ..security import require_auth
from ..services import checkins as checkin_service
from ..timeutil import utcnow

router = APIRouter(prefix="/elders", tags=["elders"], dependencies=[Depends(require_auth)])


def _sync_contacts(elder: Elder, items: list[ContactIn]) -> None:
    existing = {c.id: c for c in elder.contacts}
    keep: set[int] = set()
    for item in items:
        fields = item.model_dump(exclude={"id"})
        if item.id is not None and item.id in existing:
            contact = existing[item.id]
            for key, value in fields.items():
                setattr(contact, key, value)
            keep.add(contact.id)
        else:
            elder.contacts.append(Contact(**fields))
    for contact_id, contact in existing.items():
        if contact_id not in keep:
            elder.contacts.remove(contact)


def _sync_medicines(elder: Elder, items: list[MedicineIn]) -> None:
    existing = {m.id: m for m in elder.medicines}
    keep: set[int] = set()
    for item in items:
        fields = item.model_dump(exclude={"id"})
        if item.id is not None and item.id in existing:
            medicine = existing[item.id]
            for key, value in fields.items():
                setattr(medicine, key, value)
            keep.add(medicine.id)
        else:
            elder.medicines.append(Medicine(**fields))
    for medicine_id, medicine in existing.items():
        if medicine_id not in keep:
            elder.medicines.remove(medicine)


def _apply(elder: Elder, payload: ElderIn) -> None:
    elder.name = payload.name
    elder.phone = payload.phone
    elder.language = payload.language
    elder.timezone = payload.timezone
    elder.check_in_times = payload.check_in_times
    elder.active = payload.active
    if payload.consent and elder.consent_at is None:
        elder.consent_at = utcnow()
    if not payload.consent:
        elder.consent_at = None
    _sync_contacts(elder, payload.contacts)
    _sync_medicines(elder, payload.medicines)


def _get(db: Session, elder_id: int) -> Elder:
    elder = db.get(Elder, elder_id)
    if elder is None:
        raise HTTPException(status_code=404, detail="Person not found")
    return elder


@router.get("", response_model=list[ElderListItem])
def list_elders(db: Session = Depends(get_db)):
    items = []
    for elder in db.scalars(select(Elder).order_by(Elder.name)).all():
        latest = db.scalars(
            select(CheckIn).where(CheckIn.elder_id == elder.id).order_by(CheckIn.scheduled_at.desc())
        ).first()
        open_alerts = db.scalar(
            select(func.count(Alert.id)).where(
                Alert.elder_id == elder.id, Alert.acknowledged_at.is_(None), Alert.severity != "info"
            )
        ) or 0
        summary = checkin_service.build_summary(db, elder, 7)
        base = ElderOut.model_validate(elder).model_dump()
        items.append(
            ElderListItem(
                **base,
                latest_checkin=CheckInOut.model_validate(latest) if latest else None,
                open_alerts=open_alerts,
                adherence_7d=summary["adherence_pct"],
            )
        )
    return items


@router.post("", response_model=ElderOut, status_code=201)
def create_elder(payload: ElderIn, db: Session = Depends(get_db)):
    elder = Elder()
    db.add(elder)
    _apply(elder, payload)
    db.commit()
    return ElderOut.model_validate(elder)


@router.get("/{elder_id}", response_model=ElderOut)
def get_elder(elder_id: int, db: Session = Depends(get_db)):
    return ElderOut.model_validate(_get(db, elder_id))


@router.put("/{elder_id}", response_model=ElderOut)
def update_elder(elder_id: int, payload: ElderIn, db: Session = Depends(get_db)):
    elder = _get(db, elder_id)
    _apply(elder, payload)
    db.commit()
    return ElderOut.model_validate(elder)


@router.delete("/{elder_id}", status_code=204)
def delete_elder(elder_id: int, db: Session = Depends(get_db)):
    elder = _get(db, elder_id)
    db.delete(elder)
    db.commit()
