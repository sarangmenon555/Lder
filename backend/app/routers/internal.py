import hmac

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..services import checkins as checkin_service

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/tick")
def tick(key: str = Query(default=""), db: Session = Depends(get_db)):
    secret = get_settings().cron_secret
    if not secret or not hmac.compare_digest(key.encode(), secret.encode()):
        raise HTTPException(status_code=403, detail="Forbidden")
    return checkin_service.run_tick(db)
