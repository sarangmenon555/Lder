from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    native_name: str
    voice: str
    stt_prompt: str


LANGUAGES: dict[str, Language] = {
    "ml": Language(
        "ml",
        "Malayalam",
        "മലയാളം",
        "ml-IN-SobhanaNeural",
        "സുഖമാണ്. മരുന്ന് കഴിച്ചു. വേദന. വീണു. ശ്വാസം മുട്ടൽ.",
    ),
    "ta": Language(
        "ta",
        "Tamil",
        "தமிழ்",
        "ta-IN-PallaviNeural",
        "நலமாக இருக்கிறேன். மருந்து சாப்பிட்டேன். வலி. விழுந்துவிட்டேன். மூச்சு திணறல்.",
    ),
    "te": Language(
        "te",
        "Telugu",
        "తెలుగు",
        "te-IN-ShrutiNeural",
        "బాగున్నాను. మందు వేసుకున్నాను. నొప్పి. పడిపోయాను. ఊపిరి ఆడటం లేదు.",
    ),
    "hi": Language(
        "hi",
        "Hindi",
        "हिन्दी",
        "hi-IN-SwaraNeural",
        "मैं ठीक हूँ। दवा ले ली। दर्द है। गिर गया। सांस लेने में तकलीफ।",
    ),
    "kn": Language(
        "kn",
        "Kannada",
        "ಕನ್ನಡ",
        "kn-IN-SapnaNeural",
        "ಚೆನ್ನಾಗಿದ್ದೇನೆ. ಔಷಧ ತೆಗೆದುಕೊಂಡೆ. ನೋವು. ಬಿದ್ದೆ. ಉಸಿರಾಡಲು ತೊಂದರೆ.",
    ),
}

DEFAULT_LANGUAGE = "ml"


def normalize_code(code: str | None) -> str:
    value = (code or "").strip().lower()
    return value if value in LANGUAGES else DEFAULT_LANGUAGE


def get(code: str | None) -> Language:
    return LANGUAGES[normalize_code(code)]
