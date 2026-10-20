import pytest

from app.services.keywords import analyze


@pytest.mark.parametrize(
    "text,category",
    [
        ("ഞാൻ വീണു, എഴുന്നേൽക്കാൻ പറ്റുന്നില്ല", "fall"),
        ("veenu poyi, kaal anakkan pattunilla", "fall"),
        ("I fell in the bathroom and my hip hurts", "fall"),
        ("നെഞ്ചുവേദനയുണ്ട്", "chest_pain"),
        ("ശ്വാസം മുട്ടുന്നു", "breathing"),
        ("ഒരുപാട് രക്തം വരുന്നു", "bleeding"),
        ("ബോധം പോകുന്നപോലെ തോന്നുന്നു", "unconscious"),
        ("ആരെങ്കിലും സഹായിക്കണേ", "help"),
        ("ഇന്ന് രാവിലെ മുതൽ നെഞ്ചിൽ ഭാരം പോലെ, ശ്വാസം എടുക്കാൻ ബുദ്ധിമുട്ട്", "breathing"),
    ],
)
def test_critical_detected(text, category):
    assert category in analyze(text).critical


@pytest.mark.parametrize(
    "text,category",
    [
        ("കാലിന് വേദനയുണ്ട്, നടക്കാൻ പ്രയാസം", "pain"),
        ("ചെറിയ പനി പോലെ തോന്നുന്നു", "fever"),
        ("വയ്യ, കിടക്കുകയാണ്", "unwell"),
        ("തല കറങ്ങുന്നു", "dizziness"),
    ],
)
def test_concern_detected(text, category):
    result = analyze(text)
    assert category in result.concern
    assert not result.critical


@pytest.mark.parametrize(
    "text",
    [
        "സുഖമാണ്. വേദനയില്ല",
        "സുഖമാണ്, മരുന്ന് കഴിച്ചു",
        "എനിക്ക് കുഴപ്പമില്ല, ഇപ്പോൾ ചായ കുടിച്ചു",
        "I am fine, took my tablet",
        "my blood pressure is normal",
    ],
)
def test_no_false_alarm(text):
    result = analyze(text)
    assert not result.critical
    assert not result.concern


def test_mild_detected():
    assert "tired" in analyze("ഇന്ന് നല്ല ക്ഷീണം തോന്നുന്നു").mild


def test_negated_tiredness_ignored():
    assert not analyze("ക്ഷീണമില്ല").mild


@pytest.mark.parametrize(
    "text,expected",
    [
        ("സുഖമാണ്, മരുന്ന് കഴിച്ചു", "yes"),
        ("രാവിലെ ഗുളിക കഴിച്ചു", "yes"),
        ("marunnu kazhichu", "yes"),
        ("I am fine, took my tablet", "yes"),
        ("ഗുളിക കഴിക്കാൻ മറന്നു", "no"),
        ("മരുന്ന് തീർന്നു, കഴിച്ചില്ല", "no"),
        ("marunnu kazhichilla, theernnu poyi", "no"),
        ("I forgot my medicine today", "no"),
        ("എല്ലാം ശരിയാണ്. ഭക്ഷണം കഴിച്ചു", "unknown"),
        ("", "unknown"),
    ],
)
def test_medicine(text, expected):
    assert analyze(text).medicine == expected


def test_chillu_forms_match():
    assert "pain" in analyze("കാലിൽ വേദന").concern
    assert "pain" in analyze("കാലില്\u200d വേദന").concern
