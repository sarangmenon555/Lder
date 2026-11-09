import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from ..config import get_settings

_media_cache: dict[str, str] = {}


class WhatsAppError(Exception):
    pass


@dataclass
class InboundMessage:
    sender: str
    kind: str
    text: str = ""
    media_id: str = ""
    mime: str = ""


def enabled() -> bool:
    s = get_settings()
    return bool(s.whatsapp_token and s.whatsapp_phone_number_id)


def normalize_phone(phone: str | None) -> str:
    return re.sub(r"\D", "", phone or "")


def same_phone(a: str | None, b: str | None) -> bool:
    x, y = normalize_phone(a), normalize_phone(b)
    if not x or not y:
        return False
    return x[-10:] == y[-10:]


def window_open(last_inbound_at: datetime | None, now: datetime) -> bool:
    return last_inbound_at is not None and now - last_inbound_at < timedelta(hours=24)


def _base() -> str:
    return f"https://graph.facebook.com/{get_settings().whatsapp_api_version}"


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_settings().whatsapp_token}"}


def _post_message(payload: dict) -> None:
    if not enabled():
        raise WhatsAppError("WhatsApp is not configured")
    url = f"{_base()}/{get_settings().whatsapp_phone_number_id}/messages"
    body = {"messaging_product": "whatsapp", **payload}
    try:
        response = httpx.post(url, json=body, headers=_headers(), timeout=20)
    except httpx.HTTPError as exc:
        raise WhatsAppError(f"Network error: {exc}") from exc
    if response.status_code >= 400:
        raise WhatsAppError(f"WhatsApp error {response.status_code}: {response.text[:300]}")


def send_text(to: str, body: str) -> None:
    _post_message({"to": normalize_phone(to), "type": "text", "text": {"body": body[:3900]}})


def send_template(to: str) -> None:
    s = get_settings()
    _post_message(
        {
            "to": normalize_phone(to),
            "type": "template",
            "template": {"name": s.whatsapp_template_name, "language": {"code": s.whatsapp_template_language}},
        }
    )


def upload_audio(path: Path) -> str:
    key = str(path)
    if key in _media_cache:
        return _media_cache[key]
    url = f"{_base()}/{get_settings().whatsapp_phone_number_id}/media"
    try:
        response = httpx.post(
            url,
            headers=_headers(),
            data={"messaging_product": "whatsapp", "type": "audio/mpeg"},
            files={"file": (path.name, path.read_bytes(), "audio/mpeg")},
            timeout=40,
        )
    except httpx.HTTPError as exc:
        raise WhatsAppError(f"Network error: {exc}") from exc
    if response.status_code >= 400:
        raise WhatsAppError(f"WhatsApp media error {response.status_code}: {response.text[:300]}")
    media_id = response.json().get("id")
    if not media_id:
        raise WhatsAppError("WhatsApp did not return a media id")
    _media_cache[key] = media_id
    return media_id


def send_audio(to: str, media_id: str) -> None:
    _post_message({"to": normalize_phone(to), "type": "audio", "audio": {"id": media_id}})


def send_to_elder(elder, body: str, audio: Path | None, now: datetime) -> str:
    to = normalize_phone(elder.phone)
    if not to:
        raise WhatsAppError("Elder has no phone number")
    if window_open(elder.last_inbound_at, now):
        send_text(to, body)
        if audio is not None:
            send_audio(to, upload_audio(audio))
        return "message"
    send_template(to)
    return "template"


def send_to_contact(contact, body: str, now: datetime) -> None:
    to = normalize_phone(contact.phone)
    if not to:
        raise WhatsAppError("Contact has no phone number")
    if window_open(contact.last_inbound_at, now):
        send_text(to, body)
        return
    send_template(to)
    raise WhatsAppError("Recipient window closed; template sent instead of the alert text")


def download_media(media_id: str) -> tuple[bytes, str]:
    try:
        meta = httpx.get(f"{_base()}/{media_id}", headers=_headers(), timeout=20)
        if meta.status_code >= 400:
            raise WhatsAppError(f"Media lookup failed {meta.status_code}")
        info = meta.json()
        file_response = httpx.get(info["url"], headers=_headers(), timeout=60)
    except httpx.HTTPError as exc:
        raise WhatsAppError(f"Network error: {exc}") from exc
    if file_response.status_code >= 400:
        raise WhatsAppError(f"Media download failed {file_response.status_code}")
    return file_response.content, info.get("mime_type", "audio/ogg")


def verify_signature(raw_body: bytes, header: str | None) -> bool:
    secret = get_settings().whatsapp_app_secret
    if not secret:
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256="):])


def parse_inbound(payload: dict) -> list[InboundMessage]:
    messages: list[InboundMessage] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                sender = normalize_phone(msg.get("from"))
                kind = msg.get("type", "")
                if kind == "audio":
                    audio = msg.get("audio", {})
                    messages.append(
                        InboundMessage(sender, "audio", media_id=audio.get("id", ""), mime=audio.get("mime_type", ""))
                    )
                elif kind == "text":
                    messages.append(InboundMessage(sender, "text", text=msg.get("text", {}).get("body", "")))
                else:
                    messages.append(InboundMessage(sender, kind or "other"))
    return messages
