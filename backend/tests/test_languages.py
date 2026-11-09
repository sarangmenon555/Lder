import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import languages, prompts
from app.services.keywords import analyze


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def headers(client):
    token = client.post("/api/auth/login", json={"password": "test-password"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


CRITICAL_CASES = [
    ("hi", "मैं गिर गया", "fall"),
    ("hi", "मुझे सीने में दर्द है", "chest_pain"),
    ("hi", "सांस नहीं ले पा रहा", "breathing"),
    ("hi", "मदद करो", "help"),
    ("hi", "main behosh ho gaya", "unconscious"),
    ("ta", "நான் விழுந்துட்டேன்", "fall"),
    ("ta", "நெஞ்சு வலி இருக்கு", "chest_pain"),
    ("ta", "மூச்சு திணறல் இருக்கு", "breathing"),
    ("ta", "உதவி வேண்டும்", "help"),
    ("te", "నేను పడిపోయాను", "fall"),
    ("te", "ఛాతీ నొప్పి ఉంది", "chest_pain"),
    ("te", "ఊపిరి ఆడటం లేదు", "breathing"),
    ("te", "కాపాడండి", "help"),
    ("kn", "ನಾನು ಬಿದ್ದೆ", "fall"),
    ("kn", "ಎದೆ ನೋವು ಇದೆ", "chest_pain"),
    ("kn", "ಉಸಿರು ಕಟ್ಟುತ್ತಿದೆ", "breathing"),
    ("kn", "ಸಹಾಯ ಮಾಡಿ", "help"),
]

CONCERN_CASES = [
    ("hi", "मुझे बुखार है", "fever"),
    ("hi", "चक्कर आ रहे हैं", "dizziness"),
    ("hi", "तबीयत ठीक नहीं है", "unwell"),
    ("ta", "காய்ச்சல் இருக்கு", "fever"),
    ("ta", "தலை சுற்றுது", "dizziness"),
    ("te", "జ్వరం ఉంది", "fever"),
    ("te", "ఒంట్లో బాగోలేదు", "unwell"),
    ("kn", "ಜ್ವರ ಇದೆ", "fever"),
    ("kn", "ಹುಷಾರಿಲ್ಲ", "unwell"),
]

NEGATED_CASES = [
    ("hi", "दर्द नहीं है"),
    ("ta", "வலி இல்லை"),
    ("ta", "வலியில்லை"),
    ("te", "నొప్పి లేదు"),
    ("kn", "ನೋವು ಇಲ್ಲ"),
    ("kn", "ನೋವಿಲ್ಲ"),
]

MEDICINE_CASES = [
    ("hi", "मैंने दवा ले ली", "yes"),
    ("hi", "मैंने दवा नहीं ली", "no"),
    ("ta", "மாத்திரை சாப்பிட்டேன்", "yes"),
    ("ta", "மாத்திரை சாப்பிடவில்லை", "no"),
    ("te", "మందు వేసుకున్నాను", "yes"),
    ("te", "మందు వేసుకోలేదు", "no"),
    ("kn", "ಔಷಧ ತೆಗೆದುಕೊಂಡೆ", "yes"),
    ("kn", "ಔಷಧ ತೆಗೆದುಕೊಂಡಿಲ್ಲ", "no"),
]

BLOOD_TEST_CASES = [
    "मेरा ब्लड प्रेशर ठीक है",
    "रक्तचाप सामान्य है",
    "ரத்த அழுத்தம் சரியாக இருக்கு",
    "రక్తపోటు బాగుంది",
    "ರಕ್ತದೊತ್ತಡ ಸರಿ ಇದೆ",
    "ರಕ್ತ ಪರೀಕ್ಷೆ ಮಾಡಿಸಿದೆ",
]


@pytest.mark.parametrize("code,text,category", CRITICAL_CASES)
def test_critical_keywords(code, text, category):
    assert category in analyze(text).critical


@pytest.mark.parametrize("code,text,category", CONCERN_CASES)
def test_concern_keywords(code, text, category):
    assert category in analyze(text).concern


@pytest.mark.parametrize("code,text", NEGATED_CASES)
def test_negated_pain_is_not_flagged(code, text):
    result = analyze(text)
    assert "pain" not in result.concern
    assert not result.critical


@pytest.mark.parametrize("code,text,expected", MEDICINE_CASES)
def test_medicine_reports(code, text, expected):
    assert analyze(text).medicine == expected


@pytest.mark.parametrize("text", BLOOD_TEST_CASES)
def test_blood_pressure_and_tests_are_not_bleeding(text):
    assert "bleeding" not in analyze(text).critical


@pytest.mark.parametrize("text", ["मैं ठीक हूँ", "நான் நலமாக இருக்கிறேன்", "నేను బాగున్నాను", "ನಾನು ಚೆನ್ನಾಗಿದ್ದೇನೆ"])
def test_healthy_replies_raise_nothing(text):
    result = analyze(text)
    assert not result.critical
    assert not result.concern


def test_every_prompt_has_every_language():
    for key, prompt in prompts.PROMPTS.items():
        assert set(prompt.texts) == set(languages.LANGUAGES), key
        assert len({prompt.texts[code] for code in languages.LANGUAGES}) == len(languages.LANGUAGES), key


def test_audio_filenames_keep_malayalam_names_and_suffix_the_rest():
    assert prompts.audio_filename("morning", "ml") == "morning.mp3"
    assert prompts.audio_filename("morning", "ta") == "morning.ta.mp3"
    assert prompts.audio_filename("morning", "unknown") == "morning.mp3"


def test_unknown_language_falls_back_to_malayalam():
    assert languages.normalize_code("xx") == "ml"
    assert prompts.text_for("morning", "xx") == prompts.PROMPTS["morning"].texts["ml"]


def payload(language):
    return {
        "name": f"Lang {language}",
        "language": language,
        "timezone": "Asia/Kolkata",
        "check_in_times": ["08:30"],
        "consent": True,
        "contacts": [{"name": "Daughter", "channel": "dashboard", "priority": 1}],
        "medicines": [],
    }


def test_invalid_language_rejected(client, headers):
    assert client.post("/api/elders", json=payload("fr"), headers=headers).status_code == 422


@pytest.mark.parametrize("code", ["ta", "te", "hi", "kn"])
def test_language_is_saved_and_drives_simulator_prompt(client, headers, code):
    created = client.post("/api/elders", json=payload(code), headers=headers).json()
    assert created["language"] == code
    token = created["access_token"]
    assert client.get(f"/api/simulator/{token}").json()["language"] == code
    prompt = client.post(f"/api/simulator/{token}/start").json()
    assert prompt["text"] in (prompts.PROMPTS["morning"].texts[code], prompts.PROMPTS["evening"].texts[code])
    updated = client.put(f"/api/elders/{created['id']}", json=payload(code), headers=headers).json()
    assert updated["language"] == code


def test_emergency_reply_in_hindi_alerts_family(client, headers):
    created = client.post("/api/elders", json=payload("hi"), headers=headers).json()
    token = created["access_token"]
    client.post(f"/api/simulator/{token}/start")
    reply = client.post(f"/api/simulator/{token}/reply", data={"text": "मैं गिर गया हूँ"}).json()
    assert reply["family_notified"] is True
    assert reply["ack_text"] == prompts.PROMPTS["ack_help"].texts["hi"]


def test_symptom_phrases_that_contain_a_negation_are_not_cancelled_by_later_words():
    assert "breathing" in analyze("सांस नहीं आ रही, ठीक नहीं लग रहा").critical
    assert "unwell" in analyze("ಹುಷಾರಿಲ್ಲ, ನೋವು ಇಲ್ಲ").concern
    assert "unconscious" in analyze("ബോധമില്ല, വേദനയില്ല").critical


def test_a_later_negative_clause_does_not_hide_a_fall():
    assert "fall" in analyze("मैं गिर गया और उठ नहीं पा रहा").critical
    assert "fall" in analyze("വീണു, എഴുന്നേൽക്കാൻ പറ്റുന്നില്ല").critical
    assert "fall" in analyze("I fell and I can't get up, no one is here").critical


@pytest.mark.parametrize(
    "text",
    ["chest pain illa", "നെഞ്ചുവേദന ഒന്നും ഇല്ല", "നെഞ്ചുവേദനയില്ല", "सीने में दर्द नहीं है", "छाती में दर्द बिल्कुल नहीं"],
)
def test_a_direct_negation_still_clears_a_critical_symptom(text):
    assert not analyze(text).critical
