import re
import unicodedata
from dataclasses import dataclass

INJECTION_PATTERNS = [
    (r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|prompts|rules|messages)", 0.97),
    (r"disregard (all |any |the )?(previous|prior|above|earlier|your) (instructions|prompts|rules)", 0.97),
    (r"forget (all |everything |your )?(previous |prior )?(instructions|rules|prompt)", 0.93),
    (r"(reveal|show|print|repeat|output|leak) (me )?(your |the )?(system|hidden|initial|original) (prompt|instructions|message)", 0.97),
    (r"you are now (a |an |in )?(dan|developer mode|jailbroken|unrestricted)", 0.95),
    (r"(act|behave|pretend) (as|like) (if )?(you (have|had) )?no (rules|restrictions|filters|guidelines)", 0.93),
    (r"\bjailbreak\b", 0.85),
    (r"developer mode", 0.8),
    (r"</?\s*(system|assistant|tool|instructions?)\s*>", 0.9),
    (r"\bnew (system )?instructions?\s*:", 0.85),
    (r"(dump|export|list|show) (me )?(all|every) (the )?(elders|patients|people|users|records|check-?ins|data)", 0.85),
    (r"(other|another|all) (elders?|patients?|people|users?|families|persons?)('s)? (data|records|check-?ins|transcripts|details)", 0.85),
    (r"(api|secret|admin|access)[ _-]?(key|token|password)", 0.8),
    (r"(മുമ്പത്തെ|മുൻപത്തെ|എല്ലാ) നിർദ്ദേശങ്ങൾ (അവഗണിക്കുക|മറക്കുക)", 0.9),
    (r"(पिछले|पहले के|सभी) (निर्देश|आदेश) (अनदेखा|नज़रअंदाज़|भूल)", 0.9),
    (r"(முந்தைய|எல்லா) (அறிவுறுத்தல்களை|கட்டளைகளை) (புறக்கணி|மற)", 0.9),
    (r"(మునుపటి|అన్ని) (సూచనలను|ఆదేశాలను) (విస్మరించు|మర)", 0.9),
    (r"(ಹಿಂದಿನ|ಎಲ್ಲಾ) (ಸೂಚನೆಗಳನ್ನು|ಆದೇಶಗಳನ್ನು) (ನಿರ್ಲಕ್ಷಿಸಿ|ಮರೆತುಬಿಡಿ)", 0.9),
]

COMPILED = [(re.compile(p, re.IGNORECASE), s) for p, s in INJECTION_PATTERNS]

PII_PATTERNS = [
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("aadhaar", re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")),
    ("pan", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("card", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("phone", re.compile(r"(?<!\d)(?:\+?91[ -]?)?[6-9]\d{9}(?!\d)")),
]

MAX_QUESTION_CHARS = 500


@dataclass
class Verdict:
    valid: bool
    score: float
    explanation: str | None


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub(r"[​-‏⁠﻿]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def check_injection(text: str) -> Verdict:
    clean = _normalize(text)
    best = 0.0
    hit = None
    for pattern, score in COMPILED:
        if pattern.search(clean) and score > best:
            best = score
            hit = pattern.pattern
    if hit is None:
        return Verdict(True, 0.0, None)
    return Verdict(False, best, "prompt injection pattern matched")


def find_pii(text: str) -> list[str]:
    return [name for name, pattern in PII_PATTERNS if pattern.search(text or "")]


def redact_pii(text: str) -> tuple[str, list[str]]:
    found = []
    result = text or ""
    for name, pattern in PII_PATTERNS:
        if pattern.search(result):
            found.append(name)
            result = pattern.sub(f"[{name} removed]", result)
    return result, found


def validate(profile: str, text: str) -> dict:
    if profile in ("prompt-injection", "injection"):
        verdict = check_injection(text)
    elif profile in ("pii", "personally-identifiable-information"):
        found = find_pii(text)
        verdict = Verdict(not found, 0.99 if found else 0.0, ("contains " + ", ".join(found)) if found else None)
    else:
        return {"profile": profile, "result": {"valid": None, "explanation": f"unknown profile '{profile}'", "score": None}}
    return {"profile": profile, "result": {"valid": verdict.valid, "explanation": verdict.explanation, "score": verdict.score}}


def screen_question(question: str) -> tuple[str, list[str]]:
    clean = _normalize(question)[:MAX_QUESTION_CHARS]
    verdict = check_injection(clean)
    if not verdict.valid:
        raise Blocked(verdict.explanation or "blocked")
    return redact_pii(clean)


class Blocked(Exception):
    pass
