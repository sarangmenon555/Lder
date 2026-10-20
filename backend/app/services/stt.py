import httpx

from ..config import get_settings


class TranscriptionError(Exception):
    pass


EXTENSIONS = {
    "audio/ogg": "ogg",
    "audio/opus": "ogg",
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/mp4": "m4a",
    "audio/m4a": "m4a",
    "audio/x-m4a": "m4a",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/flac": "flac",
    "audio/aac": "m4a",
}

MAX_BYTES = 20 * 1024 * 1024


def extension_for(content_type: str | None) -> tuple[str, str]:
    base = (content_type or "").split(";")[0].strip().lower()
    ext = EXTENSIONS.get(base, "webm")
    return ext, base or "audio/webm"


def transcribe(audio: bytes, content_type: str | None) -> str:
    settings = get_settings()
    if not settings.groq_api_key:
        raise TranscriptionError("GROQ_API_KEY is not configured")
    if not audio:
        raise TranscriptionError("Empty audio")
    if len(audio) > MAX_BYTES:
        raise TranscriptionError("Audio is larger than 20 MB")
    ext, mime = extension_for(content_type)
    data = {
        "model": settings.stt_model,
        "response_format": "json",
        "temperature": "0",
    }
    if settings.stt_language:
        data["language"] = settings.stt_language
    if settings.stt_prompt:
        data["prompt"] = settings.stt_prompt
    url = settings.groq_base_url.rstrip("/") + "/audio/transcriptions"
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
    try:
        response = httpx.post(
            url,
            headers=headers,
            data=data,
            files={"file": (f"reply.{ext}", audio, mime)},
            timeout=60,
        )
    except httpx.HTTPError as exc:
        raise TranscriptionError(f"Network error: {exc}") from exc
    if response.status_code >= 400:
        raise TranscriptionError(f"Groq error {response.status_code}: {response.text[:300]}")
    try:
        return (response.json().get("text") or "").strip()
    except ValueError as exc:
        raise TranscriptionError("Unreadable transcription response") from exc
