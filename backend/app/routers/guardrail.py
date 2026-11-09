import hmac

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ..config import get_settings
from ..services import guardrails

router = APIRouter(tags=["guardrail"])


class ValidateIn(BaseModel):
    profile: str = "prompt-injection"
    input_text: str = ""


def _check(authorization: str | None) -> None:
    secret = get_settings().guardrail_secret
    if not secret:
        raise HTTPException(status_code=503, detail="Guardrail endpoint is not configured")
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied, secret):
        raise HTTPException(status_code=401, detail="Invalid credential")


@router.post("/guardrail/validate")
@router.post("/guardrail")
def validate(payload: ValidateIn, authorization: str | None = Header(default=None)):
    _check(authorization)
    return guardrails.validate(payload.profile, payload.input_text)
