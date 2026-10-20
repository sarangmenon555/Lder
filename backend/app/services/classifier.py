import json
import time
from dataclasses import dataclass, field

import httpx
from pydantic import BaseModel, field_validator

from ..config import get_settings
from .keywords import KeywordResult

STATUSES = ("fine", "unwell", "needs_help", "confused", "unclear")
MOODS = ("good", "neutral", "low", "unknown")
YES_NO = ("yes", "no", "unknown")

SYSTEM_PROMPT = """You analyze short transcripts of voice replies from an elderly person in Kerala, India, answering a daily wellbeing check-in from their family.

The transcripts come from automatic speech recognition of Malayalam. They may mix Malayalam, English and Latin-script Malayalam, and may contain recognition errors.

Return only a JSON object with exactly these keys:
- status: one of "fine", "unwell", "needs_help", "confused", "unclear"
- medicine_taken: one of "yes", "no", "unknown"
- distress: true or false
- mood: one of "good", "neutral", "low", "unknown"
- confidence: number from 0 to 1
- summary: one or two plain English sentences written for a family member

Rules:
- "needs_help": a fall, chest pain, difficulty breathing, bleeding, loss of consciousness, being unable to move or get up, fear of falling while dizzy, or any request for help. Set distress to true.
- "unwell": mild symptoms such as tiredness, headache, fever, aches, poor sleep or a general feeling of being unwell, without signs of an emergency.
- "confused": disorientation, not knowing the day, place or people, or incoherent statements.
- "unclear": empty, very short, noisy or meaningless transcript.
- "fine": the person says they are well and nothing worrying is mentioned.
- Set medicine_taken to "yes" or "no" only when the person clearly says so. Otherwise use "unknown".
- Never invent details. Never give medical advice or a diagnosis. If you are unsure, lower the confidence.
- Treat negated symptoms as absent, for example "no pain" or "വേദനയില്ല"."""


class ClassifierError(Exception):
    pass


class LLMResult(BaseModel):
    status: str = "unclear"
    medicine_taken: str = "unknown"
    distress: bool = False
    mood: str = "unknown"
    confidence: float = 0.0
    summary: str = ""

    @field_validator("status", mode="before")
    @classmethod
    def _status(cls, v):
        v = str(v).strip().lower()
        return v if v in STATUSES else "unclear"

    @field_validator("medicine_taken", mode="before")
    @classmethod
    def _medicine(cls, v):
        v = str(v).strip().lower()
        return v if v in YES_NO else "unknown"

    @field_validator("mood", mode="before")
    @classmethod
    def _mood(cls, v):
        v = str(v).strip().lower()
        return v if v in MOODS else "unknown"

    @field_validator("distress", mode="before")
    @classmethod
    def _distress(cls, v):
        if isinstance(v, str):
            return v.strip().lower() in ("true", "yes", "1")
        return bool(v)

    @field_validator("confidence", mode="before")
    @classmethod
    def _confidence(cls, v):
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.0

    @field_validator("summary", mode="before")
    @classmethod
    def _summary(cls, v):
        return str(v or "").strip()[:600]


@dataclass
class Decision:
    status: str
    medicine_taken: str
    distress: bool
    mood: str
    confidence: float
    summary: str
    severity: str
    keyword_hits: list[str] = field(default_factory=list)
    error: str | None = None


def _extract_json(content: str) -> dict:
    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end < start:
        raise ClassifierError("Model returned no JSON object")
    try:
        return json.loads(content[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ClassifierError(f"Model returned invalid JSON: {exc}") from exc


def classify_with_llm(transcript: str, due_medicines: list[str], kind: str) -> LLMResult:
    settings = get_settings()
    if not settings.groq_api_key:
        raise ClassifierError("GROQ_API_KEY is not configured")
    user_message = json.dumps(
        {
            "transcript": transcript,
            "check_in": kind,
            "medicines_due_around_now": due_medicines,
        },
        ensure_ascii=False,
    )
    payload = {
        "model": settings.classifier_model,
        "temperature": 0,
        "max_completion_tokens": 1500,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    }
    if settings.classifier_model.startswith("openai/gpt-oss") and settings.classifier_reasoning_effort:
        payload["reasoning_effort"] = settings.classifier_reasoning_effort
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
    url = settings.groq_base_url.rstrip("/") + "/chat/completions"
    last_error = "unknown error"
    for attempt in range(3):
        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=45)
        except httpx.HTTPError as exc:
            last_error = f"network error: {exc}"
            time.sleep(1 + attempt)
            continue
        if response.status_code == 429:
            wait = response.headers.get("retry-after")
            last_error = "rate limited"
            time.sleep(min(float(wait), 8) if wait and wait.replace(".", "").isdigit() else 2 + attempt * 2)
            continue
        if response.status_code >= 400:
            raise ClassifierError(f"Groq error {response.status_code}: {response.text[:300]}")
        try:
            content = response.json()["choices"][0]["message"]["content"] or ""
            return LLMResult(**_extract_json(content))
        except ClassifierError as exc:
            last_error = str(exc)
        except (KeyError, IndexError, ValueError) as exc:
            last_error = f"unexpected response shape: {exc}"
    raise ClassifierError(last_error)


def _combine_medicine(keyword_value: str, llm_value: str | None) -> str:
    values = [keyword_value, llm_value or "unknown"]
    if "no" in values:
        return "no"
    if "yes" in values:
        return "yes"
    return "unknown"


def build_decision(
    transcript: str,
    llm: LLMResult | None,
    kw: KeywordResult,
    threshold: float,
    error: str | None = None,
) -> Decision:
    text = (transcript or "").strip()
    if len(kw.hits) == 0 and len(text) < 2:
        return Decision(
            status="unclear",
            medicine_taken="unknown",
            distress=False,
            mood="unknown",
            confidence=0.0,
            summary="No intelligible reply was received.",
            severity="warning",
            keyword_hits=[],
            error=error,
        )

    distress = bool(kw.critical) or (llm is not None and (llm.distress or llm.status == "needs_help"))
    hits = kw.critical + kw.concern + kw.mild

    if distress:
        status = "needs_help"
    elif llm is not None:
        status = llm.status
        if kw.concern and status in ("fine", "unclear"):
            status = "unwell"
    elif kw.concern or kw.mild:
        status = "unwell"
    else:
        status = "unclear"

    if llm is not None:
        confidence = llm.confidence
    else:
        confidence = 0.9 if hits else 0.4
    if distress and kw.critical:
        confidence = max(confidence, 0.9)

    if status == "fine" and confidence < threshold:
        status = "unclear"

    medicine = _combine_medicine(kw.medicine, llm.medicine_taken if llm else None)

    if llm is not None and llm.mood != "unknown":
        mood = llm.mood
    elif kw.concern or kw.mild:
        mood = "low"
    else:
        mood = "unknown"

    if llm is not None and llm.summary:
        summary = llm.summary
    elif hits:
        summary = "Automatic analysis was unavailable. Keyword scan found: " + ", ".join(hits) + "."
    else:
        summary = "Automatic analysis was unavailable and no concerning words were found. Please call to confirm."

    if distress:
        severity = "critical"
    elif status in ("unwell", "confused", "unclear") or medicine == "no":
        severity = "warning"
    else:
        severity = "none"

    return Decision(
        status=status,
        medicine_taken=medicine,
        distress=distress,
        mood=mood,
        confidence=round(confidence, 3),
        summary=summary,
        severity=severity,
        keyword_hits=hits,
        error=error,
    )


