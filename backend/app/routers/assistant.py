from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Elder
from ..schemas import AskIn, AskOut
from ..security import require_auth
from ..services import assistant

router = APIRouter(tags=["assistant"], dependencies=[Depends(require_auth)])


@router.post("/elders/{elder_id}/ask", response_model=AskOut)
def ask(elder_id: int, payload: AskIn, db: Session = Depends(get_db)):
    elder = db.get(Elder, elder_id)
    if elder is None:
        raise HTTPException(status_code=404, detail="Person not found")
    try:
        return AskOut(**assistant.ask(db, elder, payload.question.strip()))
    except assistant.AssistantError as exc:
        if exc.kind == "budget":
            raise HTTPException(status_code=402, detail="The AI usage limit for this person has been reached.")
        if exc.kind == "guardrail":
            raise HTTPException(status_code=400, detail="This question was blocked by a safety check.")
        if exc.kind == "config":
            raise HTTPException(status_code=503, detail="The AI gateway is not configured.")
        raise HTTPException(status_code=502, detail="The assistant could not answer right now.")
