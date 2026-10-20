import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request

from ..schemas import LoginIn
from ..security import check_password, create_token

router = APIRouter(prefix="/auth", tags=["auth"])

_attempts: dict[str, list[float]] = defaultdict(list)
WINDOW_SECONDS = 300
MAX_ATTEMPTS = 10


@router.post("/login")
def login(payload: LoginIn, request: Request):
    host = request.client.host if request.client else "unknown"
    now = time.time()
    recent = [t for t in _attempts[host] if now - t < WINDOW_SECONDS]
    _attempts[host] = recent
    if len(recent) >= MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in a few minutes.")
    if not check_password(payload.password):
        _attempts[host].append(now)
        raise HTTPException(status_code=401, detail="Incorrect password")
    return {"token": create_token()}
