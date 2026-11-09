import json
import logging
import time
from dataclasses import dataclass, field

import httpx

from ..config import get_settings

log = logging.getLogger("lder.otari")

BUDGET_CODES = {"budget_exceeded", "user_blocked", "end_user_limit_reached", "insufficient_funds"}
RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


class OtariError(Exception):
    def __init__(self, message: str, code: str = "", status: int = 0, kind: str = "error"):
        super().__init__(message)
        self.code = code
        self.status = status
        self.kind = kind


@dataclass
class GatewayMeta:
    requested_model: str = ""
    model: str = ""
    provider: str = ""
    request_id: str = ""
    attempts: int = 1
    fallback: bool = False
    cost_usd: float | None = None
    models_tried: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "requested_model": self.requested_model,
            "model": self.model,
            "provider": self.provider,
            "request_id": self.request_id,
            "attempts": self.attempts,
            "fallback": self.fallback,
            "cost_usd": self.cost_usd,
            "models_tried": list(self.models_tried),
        }


def enabled() -> bool:
    return bool(get_settings().otari_api_key)


def elder_user(elder_id: int | None) -> str | None:
    if elder_id is None:
        return None
    return f"{get_settings().otari_user_prefix}{elder_id}"


def _headers(key: str, extra: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {key}"}
    if extra:
        headers.update(extra)
    return headers


def _send(url: str, headers: dict, payload: dict, timeout: float) -> httpx.Response:
    return httpx.post(url, json=payload, headers=headers, timeout=timeout)


def _error_parts(response: httpx.Response) -> tuple[str, str]:
    code = response.headers.get("Otari-Error-Code", "")
    detail = ""
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        code = code or str(body.get("code") or "")
        raw = body.get("detail")
        if raw is None and isinstance(body.get("error"), dict):
            raw = body["error"].get("message")
            code = code or str(body["error"].get("code") or "")
        detail = raw if isinstance(raw, str) else json.dumps(raw) if raw else ""
    if not detail:
        detail = response.text[:300]
    return code, detail


def _classify_error(response: httpx.Response) -> OtariError:
    code, detail = _error_parts(response)
    lowered = f"{code} {detail}".lower()
    if code in BUDGET_CODES or "budget" in lowered:
        kind = "budget"
    elif "guardrail" in lowered or "prompt_injection" in lowered or "prompt injection" in lowered:
        kind = "guardrail"
    elif response.status_code in RETRYABLE_STATUS:
        kind = "retryable"
    else:
        kind = "error"
    return OtariError(f"Otari error {response.status_code} {code}: {detail}".strip(), code, response.status_code, kind)


def _truthy_header(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() not in ("", "0", "false", "none", "no")


def _meta_from(response: httpx.Response, body: dict, requested: str, tried: list[str]) -> GatewayMeta:
    headers = response.headers
    try:
        attempts = int(headers.get("Otari-Attempt-Count", "1") or 1)
    except ValueError:
        attempts = 1
    cost = None
    usage = body.get("usage") if isinstance(body, dict) else None
    if isinstance(usage, dict) and usage.get("cost_usd") is not None:
        try:
            cost = float(usage["cost_usd"])
        except (TypeError, ValueError):
            cost = None
    model = headers.get("Otari-Model") or (body.get("model") if isinstance(body, dict) else "") or requested
    fallback = _truthy_header(headers.get("Otari-Fallback")) or attempts > 1 or len(tried) > 1
    return GatewayMeta(
        requested_model=requested,
        model=str(model),
        provider=headers.get("Otari-Provider", ""),
        request_id=headers.get("Otari-Request-ID", ""),
        attempts=attempts,
        fallback=fallback,
        cost_usd=cost,
        models_tried=list(tried),
    )


def chat(
    models: list[str],
    messages: list[dict],
    user: str | None = None,
    tags: dict | None = None,
    max_tokens: int = 800,
    temperature: float = 0.0,
    json_mode: bool = False,
    extra: dict | None = None,
    idempotency_key: str | None = None,
) -> tuple[str, GatewayMeta]:
    settings = get_settings()
    if not settings.otari_api_key:
        raise OtariError("OTARI_API_KEY is not configured", kind="config")
    if not models:
        raise OtariError("No model is configured", kind="config")
    url = settings.otari_base_url.rstrip("/") + "/chat/completions"
    headers = _headers(settings.otari_api_key, {"Idempotency-Key": idempotency_key} if idempotency_key else None)
    tried: list[str] = []
    last_error: OtariError | None = None
    for model in models:
        tried.append(model)
        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if user:
            payload["user"] = user
        if tags:
            payload["metadata"] = {str(k)[:64]: str(v)[:512] for k, v in list(tags.items())[:16]}
        if extra:
            payload.update(extra)
        for attempt in range(2):
            try:
                response = _send(url, headers, payload, settings.otari_timeout_seconds)
            except httpx.HTTPError as exc:
                last_error = OtariError(f"network error: {exc}", kind="retryable")
                time.sleep(1 + attempt)
                continue
            if response.status_code < 400:
                try:
                    body = response.json()
                    content = body["choices"][0]["message"]["content"] or ""
                except (ValueError, KeyError, IndexError, TypeError) as exc:
                    last_error = OtariError(f"unexpected response shape: {exc}", kind="error")
                    break
                return content, _meta_from(response, body, models[0], tried)
            error = _classify_error(response)
            if error.kind in ("budget", "guardrail"):
                raise error
            if json_mode and response.status_code == 400 and "response_format" in error.args[0].lower():
                json_mode = False
                payload.pop("response_format", None)
                last_error = error
                continue
            last_error = error
            if error.kind == "retryable":
                wait = response.headers.get("retry-after", "")
                try:
                    delay = min(float(wait), 6.0) if wait else 1.0 + attempt
                except ValueError:
                    delay = 1.0 + attempt
                time.sleep(delay)
                continue
            break
        log.warning("Model %s failed: %s", model, last_error)
    raise last_error or OtariError("Otari request failed")


def extract_json(content: str) -> dict:
    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end < start:
        raise OtariError("Model returned no JSON object", kind="parse")
    try:
        return json.loads(content[start : end + 1])
    except json.JSONDecodeError as exc:
        raise OtariError(f"Model returned invalid JSON: {exc}", kind="parse") from exc
