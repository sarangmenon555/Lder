import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from ..config import get_settings
from . import languages

log = logging.getLogger("lder.prompts")


@dataclass(frozen=True)
class Prompt:
    texts: dict[str, str]
    text_en: str
    file: str

    def text(self, language: str | None) -> str:
        return self.texts.get(languages.normalize_code(language)) or self.texts[languages.DEFAULT_LANGUAGE]

    @property
    def text_ml(self) -> str:
        return self.texts["ml"]


PROMPTS: dict[str, Prompt] = {
    "morning": Prompt(
        texts={
            "ml": "നമസ്കാരം. സുഖമാണോ? ഇന്ന് എങ്ങനെയുണ്ട്? മരുന്ന് കഴിച്ചോ? ഒരു വോയ്സ് മെസ്സേജ് അയച്ച് മറുപടി പറയാമോ?",
            "ta": "வணக்கம். நலமா? இன்று எப்படி இருக்கிறீர்கள்? மருந்து சாப்பிட்டீர்களா? ஒரு குரல் செய்தி அனுப்பி பதில் சொல்லுங்கள்.",
            "te": "నమస్కారం. ఎలా ఉన్నారు? ఈ రోజు ఎలా ఉంది? మందు వేసుకున్నారా? దయచేసి వాయిస్ మెసేజ్ పంపి సమాధానం చెప్పండి.",
            "hi": "नमस्ते। आप कैसे हैं? आज कैसा लग रहा है? क्या आपने दवा ली? कृपया एक वॉइस मैसेज भेजकर जवाब दें।",
            "kn": "ನಮಸ್ಕಾರ. ಹೇಗಿದ್ದೀರಿ? ಇಂದು ಹೇಗಿದೆ? ಔಷಧ ತೆಗೆದುಕೊಂಡಿರಾ? ದಯವಿಟ್ಟು ವಾಯ್ಸ್ ಮೆಸೇಜ್ ಕಳುಹಿಸಿ ಉತ್ತರಿಸಿ.",
        },
        text_en="Good morning. How are you today? Have you taken your medicines? Please reply with a voice message.",
        file="morning",
    ),
    "evening": Prompt(
        texts={
            "ml": "ശുഭ സായാഹ്നം. ഇന്ന് എങ്ങനെയുണ്ടായിരുന്നു? വൈകുന്നേരത്തെ മരുന്ന് കഴിച്ചോ? ഒരു വോയ്സ് മെസ്സേജ് അയച്ച് മറുപടി പറയാമോ?",
            "ta": "மாலை வணக்கம். இன்று நாள் எப்படி இருந்தது? மாலை மருந்து சாப்பிட்டீர்களா? ஒரு குரல் செய்தி அனுப்பி பதில் சொல்லுங்கள்.",
            "te": "శుభ సాయంత్రం. ఈ రోజు ఎలా గడిచింది? సాయంత్రం మందు వేసుకున్నారా? దయచేసి వాయిస్ మెసేజ్ పంపి సమాధానం చెప్పండి.",
            "hi": "शुभ संध्या। आज का दिन कैसा रहा? क्या आपने शाम की दवा ली? कृपया एक वॉइस मैसेज भेजकर जवाब दें।",
            "kn": "ಶುಭ ಸಂಜೆ. ಇಂದಿನ ದಿನ ಹೇಗಿತ್ತು? ಸಂಜೆಯ ಔಷಧ ತೆಗೆದುಕೊಂಡಿರಾ? ದಯವಿಟ್ಟು ವಾಯ್ಸ್ ಮೆಸೇಜ್ ಕಳುಹಿಸಿ ಉತ್ತರಿಸಿ.",
        },
        text_en="Good evening. How was your day? Have you taken your evening medicines? Please reply with a voice message.",
        file="evening",
    ),
    "retry": Prompt(
        texts={
            "ml": "വീണ്ടും ചോദിക്കുകയാണ്. സുഖമാണോ? ഒരു വോയ്സ് മെസ്സേജ് അയച്ച് മറുപടി പറയാമോ?",
            "ta": "மீண்டும் கேட்கிறோம். நலமா? ஒரு குரல் செய்தி அனுப்பி பதில் சொல்லுங்கள்.",
            "te": "మళ్ళీ అడుగుతున్నాము. మీరు బాగున్నారా? దయచేసి వాయిస్ మెసేజ్ పంపి సమాధానం చెప్పండి.",
            "hi": "दोबारा पूछ रहे हैं। क्या आप ठीक हैं? कृपया एक वॉइस मैसेज भेजकर जवाब दें।",
            "kn": "ಮತ್ತೆ ಕೇಳುತ್ತಿದ್ದೇವೆ. ನೀವು ಚೆನ್ನಾಗಿದ್ದೀರಾ? ದಯವಿಟ್ಟು ವಾಯ್ಸ್ ಮೆಸೇಜ್ ಕಳುಹಿಸಿ ಉತ್ತರಿಸಿ.",
        },
        text_en="Asking again. Are you well? Please reply with a voice message.",
        file="retry",
    ),
    "ack_ok": Prompt(
        texts={
            "ml": "നന്ദി. ശ്രദ്ധിക്കണം.",
            "ta": "நன்றி. உடல்நலத்தைப் பார்த்துக்கொள்ளுங்கள்.",
            "te": "ధన్యవాదాలు. జాగ్రత్తగా ఉండండి.",
            "hi": "धन्यवाद। अपना ध्यान रखिए।",
            "kn": "ಧನ್ಯವಾದಗಳು. ಜಾಗರೂಕರಾಗಿರಿ.",
        },
        text_en="Thank you. Please take care.",
        file="ack_ok",
    ),
    "ack_help": Prompt(
        texts={
            "ml": "ഞങ്ങൾ നിങ്ങളുടെ കുടുംബത്തെ അറിയിച്ചിട്ടുണ്ട്. അടിയന്തര സാഹചര്യമാണെങ്കിൽ ഉടൻ 112 എന്ന നമ്പറിൽ വിളിക്കുക.",
            "ta": "உங்கள் குடும்பத்தினருக்குத் தெரிவித்துவிட்டோம். இது அவசர நிலை என்றால் உடனே 112 என்ற எண்ணை அழைக்கவும்.",
            "te": "మేము మీ కుటుంబ సభ్యులకు తెలియజేశాము. ఇది అత్యవసరమైతే వెంటనే 112 కు కాల్ చేయండి.",
            "hi": "हमने आपके परिवार को सूचित कर दिया है। अगर यह आपातकाल है, तो तुरंत 112 पर कॉल करें।",
            "kn": "ನಾವು ನಿಮ್ಮ ಕುಟುಂಬಕ್ಕೆ ತಿಳಿಸಿದ್ದೇವೆ. ಇದು ತುರ್ತು ಪರಿಸ್ಥಿತಿಯಾಗಿದ್ದರೆ ತಕ್ಷಣ 112 ಗೆ ಕರೆ ಮಾಡಿ.",
        },
        text_en="We have informed your family. If this is an emergency, call 112 immediately.",
        file="ack_help",
    ),
    "unclear": Prompt(
        texts={
            "ml": "ക്ഷമിക്കണം, സന്ദേശം മനസ്സിലായില്ല. ദയവായി ഒന്നുകൂടി അയക്കാമോ?",
            "ta": "மன்னிக்கவும், செய்தி புரியவில்லை. தயவுசெய்து ஒருமுறை மீண்டும் அனுப்புங்கள்.",
            "te": "క్షమించండి, సందేశం అర్థం కాలేదు. దయచేసి ఒకసారి మళ్ళీ పంపండి.",
            "hi": "माफ़ कीजिए, संदेश समझ नहीं आया। कृपया एक बार फिर भेजें।",
            "kn": "ಕ್ಷಮಿಸಿ, ಸಂದೇಶ ಅರ್ಥವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಇನ್ನೊಮ್ಮೆ ಕಳುಹಿಸಿ.",
        },
        text_en="Sorry, we could not understand the message. Could you send it once more?",
        file="unclear",
    ),
}


def prompt_key(kind: str, attempt: int) -> str:
    if attempt > 1:
        return "retry"
    return "evening" if kind == "evening" else "morning"


def text_for(key: str, language: str | None) -> str:
    return PROMPTS[key].text(language)


def audio_filename(key: str, language: str | None) -> str:
    code = languages.normalize_code(language)
    base = PROMPTS[key].file
    return f"{base}.mp3" if code == languages.DEFAULT_LANGUAGE else f"{base}.{code}.mp3"


def audio_path(key: str, language: str | None = None) -> Path:
    return get_settings().prompt_dir / audio_filename(key, language)


async def _synthesize(text: str, voice: str, path: Path) -> None:
    import edge_tts

    await edge_tts.Communicate(text, voice).save(str(path))


def _run_synthesis(text: str, voice: str, path: Path) -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(_synthesize(text, voice, path))
        return
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(lambda: asyncio.run(_synthesize(text, voice, path))).result()


def ensure_audio(key: str, language: str | None = None) -> Path | None:
    path = audio_path(key, language)
    if path.exists() and path.stat().st_size > 0:
        return path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _run_synthesis(text_for(key, language), languages.get(language).voice, path)
    except Exception as exc:
        log.warning("Could not synthesize prompt %s (%s): %s", key, language, exc)
        if path.exists() and path.stat().st_size == 0:
            path.unlink()
        return None
    return path if path.exists() else None


def audio_url(key: str, language: str | None = None) -> str | None:
    path = audio_path(key, language)
    if not (path.exists() and path.stat().st_size > 0):
        return None
    return f"{get_settings().public_base_url.rstrip('/')}/static/prompts/{audio_filename(key, language)}"
