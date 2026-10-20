import unicodedata
from dataclasses import dataclass, field

_CHILLU = str.maketrans(
    {
        "\u0d7a": "\u0d23\u0d4d",
        "\u0d7b": "\u0d28\u0d4d",
        "\u0d7c": "\u0d30\u0d4d",
        "\u0d7d": "\u0d32\u0d4d",
        "\u0d7e": "\u0d33\u0d4d",
        "\u0d7f": "\u0d15\u0d4d",
    }
)

NEGATION_WINDOW = 14


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").lower().translate(_CHILLU)
    return "".join(ch for ch in text if unicodedata.category(ch)[0] not in "PZSC")


_NEGATION = [normalize(t) for t in ("ില്ല", "ഇല്ല", "illa", "yilla")]

_IGNORE = [normalize(t) for t in ("blood pressure", "blood sugar", "blood test", "blood group")]

_CRITICAL_RAW = {
    "fall": ["വീണു", "veenu", "fell", "fallen", "fall"],
    "chest_pain": [
        "നെഞ്ചുവേദന",
        "നെഞ്ചിൽ വേദന",
        "നെഞ്ചിൽ ഭാര",
        "nenjuvedana",
        "nenju vedana",
        "chest pain",
        "chest hurts",
    ],
    "breathing": [
        "ശ്വാസം മുട്ട",
        "ശ്വാസമുട്ട",
        "ശ്വാസം എടുക്ക",
        "ശ്വാസമെടുക്ക",
        "ശ്വാസം കിട്ടു",
        "swasam mutt",
        "shwasam mutt",
        "swasam kittu",
        "breath",
    ],
    "bleeding": ["രക്തം", "ചോര", "bleed", "blood"],
    "unconscious": ["ബോധം പോ", "ബോധമില്ല", "ബോധക്ഷയം", "bodham po", "unconscious", "faint", "passed out"],
    "help": ["സഹായിക്കണേ", "സഹായിക്കൂ", "സഹായിക്കണ", "sahayikkane", "sahayikku", "help me", "need help", "please help", "ambulance", "ആംബുലൻസ്"],
}

_CONCERN_RAW = {
    "pain": ["വേദന", "vedana", "vedhana", "pain", "hurt"],
    "dizziness": ["തല കറക്ക", "തല കറങ്ങ", "തലകറക്ക", "thala karakk", "thala karang", "dizz"],
    "unwell": ["വയ്യ", "സുഖമില്ല", "vayya", "sukhamilla", "not well", "unwell", "feeling bad", "sick"],
    "fever": ["പനി", "fever"],
    "vomiting": ["ഛർദ്ദി", "ഛർദി", "chardi", "vomit"],
}

_MILD_RAW = {
    "tired": ["ക്ഷീണ", "ksheena", "kshina", "tired", "weak"],
    "low_mood": ["വിഷമം", "ഒറ്റയ്ക്ക്", "lonely", "sad"],
}

_MEDICINE_MENTION = [normalize(t) for t in ("മരുന്", "ഗുളിക", "marunn", "gulika", "tablet", "medicine", "pill", "meds")]
_MEDICINE_NO = [
    normalize(t)
    for t in (
        "കഴിച്ചില്ല",
        "മറന്നു",
        "തീർന്നു",
        "kazhichilla",
        "maranu",
        "theernnu",
        "forgot",
        "not taken",
        "didnt take",
        "did not take",
        "not yet",
        "haventtaken",
    )
]
_MEDICINE_YES = [normalize(t) for t in ("കഴിച്ചു", "kazhichu", "took", "taken")]


def _prep(table: dict[str, list[str]]) -> dict[str, list[str]]:
    return {category: [normalize(k) for k in words] for category, words in table.items()}


CRITICAL = _prep(_CRITICAL_RAW)
CONCERN = _prep(_CONCERN_RAW)
MILD = _prep(_MILD_RAW)


@dataclass
class KeywordResult:
    critical: list[str] = field(default_factory=list)
    concern: list[str] = field(default_factory=list)
    mild: list[str] = field(default_factory=list)
    medicine: str = "unknown"

    @property
    def hits(self) -> list[str]:
        return self.critical + self.concern + self.mild


def _negated(squashed: str, end: int) -> bool:
    window = squashed[end : end + NEGATION_WINDOW]
    return any(token in window for token in _NEGATION)


def _matches(squashed: str, words: list[str]) -> bool:
    for word in words:
        start = 0
        while True:
            index = squashed.find(word, start)
            if index < 0:
                break
            if not _negated(squashed, index + len(word)):
                return True
            start = index + 1
    return False


def _scan(squashed: str, table: dict[str, list[str]]) -> list[str]:
    return [category for category, words in table.items() if _matches(squashed, words)]


def _medicine(squashed: str) -> str:
    if not any(token in squashed for token in _MEDICINE_MENTION):
        return "unknown"
    if any(token in squashed for token in _MEDICINE_NO):
        return "no"
    if any(token in squashed for token in _MEDICINE_YES):
        return "yes"
    return "unknown"


def analyze(text: str) -> KeywordResult:
    squashed = normalize(text)
    for phrase in _IGNORE:
        squashed = squashed.replace(phrase, "")
    return KeywordResult(
        critical=_scan(squashed, CRITICAL),
        concern=_scan(squashed, CONCERN),
        mild=_scan(squashed, MILD),
        medicine=_medicine(squashed),
    )
