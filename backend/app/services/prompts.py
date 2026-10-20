import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from ..config import get_settings

log = logging.getLogger("lder.prompts")


@dataclass(frozen=True)
class Prompt:
    text_ml: str
    text_en: str
    file: str


PROMPTS: dict[str, Prompt] = {
    "morning": Prompt(
        text_ml="നമസ്കാരം. സുഖമാണോ? ഇന്ന് എങ്ങനെയുണ്ട്? മരുന്ന് കഴിച്ചോ? ഒരു വോയ്സ് മെസ്സേജ് അയച്ച് മറുപടി പറയാമോ?",
        text_en="Good morning. How are you today? Have you taken your medicines? Please reply with a voice message.",
        file="morning.mp3",
    ),
    "evening": Prompt(
        text_ml="ശുഭ സായാഹ്നം. ഇന്ന് എങ്ങനെയുണ്ടായിരുന്നു? വൈകുന്നേരത്തെ മരുന്ന് കഴിച്ചോ? ഒരു വോയ്സ് മെസ്സേജ് അയച്ച് മറുപടി പറയാമോ?",
        text_en="Good evening. How was your day? Have you taken your evening medicines? Please reply with a voice message.",
        file="evening.mp3",
    ),
    "retry": Prompt(
        text_ml="വീണ്ടും ചോദിക്കുകയാണ്. സുഖമാണോ? ഒരു വോയ്സ് മെസ്സേജ് അയച്ച് മറുപടി പറയാമോ?",
        text_en="Asking again. Are you well? Please reply with a voice message.",
        file="retry.mp3",
    ),
    "ack_ok": Prompt(
        text_ml="നന്ദി. ശ്രദ്ധിക്കണം.",
        text_en="Thank you. Please take care.",
        file="ack_ok.mp3",
    ),
    "ack_help": Prompt(
        text_ml="ഞങ്ങൾ നിങ്ങളുടെ കുടുംബത്തെ അറിയിച്ചിട്ടുണ്ട്. അടിയന്തര സാഹചര്യമാണെങ്കിൽ ഉടൻ 112 എന്ന നമ്പറിൽ വിളിക്കുക.",
        text_en="We have informed your family. If this is an emergency, call 112 immediately.",
        file="ack_help.mp3",
    ),
    "unclear": Prompt(
        text_ml="ക്ഷമിക്കണം, സന്ദേശം മനസ്സിലായില്ല. ദയവായി ഒന്നുകൂടി അയക്കാമോ?",
        text_en="Sorry, we could not understand the message. Could you send it once more?",
        file="unclear.mp3",
    ),
}


def prompt_key(kind: str, attempt: int) -> str:
    if attempt > 1:
        return "retry"
    return "evening" if kind == "evening" else "morning"


def audio_path(key: str) -> Path:
    return get_settings().prompt_dir / PROMPTS[key].file


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


def ensure_audio(key: str) -> Path | None:
    path = audio_path(key)
    if path.exists() and path.stat().st_size > 0:
        return path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _run_synthesis(PROMPTS[key].text_ml, get_settings().tts_voice, path)
    except Exception as exc:
        log.warning("Could not synthesize prompt %s: %s", key, exc)
        if path.exists() and path.stat().st_size == 0:
            path.unlink()
        return None
    return path if path.exists() else None


def audio_url(key: str) -> str | None:
    path = audio_path(key)
    if not (path.exists() and path.stat().st_size > 0):
        return None
    return f"{get_settings().public_base_url.rstrip('/')}/static/prompts/{PROMPTS[key].file}"
