import base64
import hashlib
import hmac
import json
import time

from fastapi import Header, HTTPException

from .config import get_settings


def _sign(payload: str) -> str:
    key = get_settings().secret_key.encode()
    digest = hmac.new(key, payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def create_token() -> str:
    exp = int(time.time()) + get_settings().token_ttl_hours * 3600
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return f"{payload}.{_sign(payload)}"


def verify_token(token: str) -> bool:
    try:
        payload, signature = token.split(".", 1)
    except ValueError:
        return False
    if not hmac.compare_digest(signature, _sign(payload)):
        return False
    try:
        padded = payload + "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        if "scope" in data:
            return False
        return int(data.get("exp", 0)) > time.time()
    except Exception:
        return False


def create_scoped_token(elder_id: int, ttl_seconds: int) -> str:
    exp = int(time.time()) + ttl_seconds
    body = {"scope": "mcp", "elder": int(elder_id), "exp": exp}
    payload = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    return f"{payload}.{_sign(payload)}"


def verify_scoped_token(token: str) -> int | None:
    try:
        payload, signature = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(signature, _sign(payload)):
        return None
    try:
        padded = payload + "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        if data.get("scope") != "mcp" or int(data.get("exp", 0)) <= time.time():
            return None
        return int(data["elder"])
    except Exception:
        return None


def check_password(candidate: str) -> bool:
    return hmac.compare_digest(candidate.encode(), get_settings().admin_password.encode())


def require_auth(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not verify_token(authorization[7:]):
        raise HTTPException(status_code=401, detail="Invalid or expired session")
