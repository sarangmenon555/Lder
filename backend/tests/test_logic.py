from datetime import datetime, timedelta, timezone

from app.services import classifier, escalation
from app.services.keywords import analyze

T0 = datetime(2026, 10, 19, 3, 0, tzinfo=timezone.utc)


def test_retry_sequence():
    delays = [15, 30]
    assert escalation.plan_retry(1, T0, T0 + timedelta(minutes=14), delays, 30) == "wait"
    assert escalation.plan_retry(1, T0, T0 + timedelta(minutes=15), delays, 30) == "retry"
    second = T0 + timedelta(minutes=15)
    assert escalation.plan_retry(2, second, second + timedelta(minutes=29), delays, 30) == "wait"
    assert escalation.plan_retry(2, second, second + timedelta(minutes=30), delays, 30) == "retry"
    third = T0 + timedelta(minutes=45)
    assert escalation.plan_retry(3, third, third + timedelta(minutes=29), delays, 30) == "wait"
    assert escalation.plan_retry(3, third, third + timedelta(minutes=30), delays, 30) == "miss"


def test_escalation_due():
    assert escalation.escalation_due(None, T0, 20)
    assert not escalation.escalation_due(T0, T0 + timedelta(minutes=19), 20)
    assert escalation.escalation_due(T0, T0 + timedelta(minutes=20), 20)


def test_pick_contact():
    contacts = ["a", "b"]
    assert escalation.pick_contact(contacts, 0) == "a"
    assert escalation.pick_contact(contacts, 1) == "b"
    assert escalation.pick_contact(contacts, 2) is None


def test_due_slots_in_elder_time_zone():
    now = datetime(2026, 10, 19, 3, 5, tzinfo=timezone.utc)
    slots = escalation.due_slots(["08:30", "19:00"], "Asia/Kolkata", now, 60)
    assert [label for label, _ in slots] == ["08:30"]
    assert slots[0][1] == datetime(2026, 10, 19, 3, 0, tzinfo=timezone.utc)


def test_due_slots_outside_grace():
    now = datetime(2026, 10, 19, 4, 31, tzinfo=timezone.utc)
    assert escalation.due_slots(["08:30"], "Asia/Kolkata", now, 60) == []


def test_due_slots_previous_local_day():
    now = datetime(2026, 10, 18, 22, 0, tzinfo=timezone.utc)
    slots = escalation.due_slots(["03:30"], "Asia/Kolkata", now, 60)
    assert len(slots) == 1


def test_empty_transcript_is_unclear():
    decision = classifier.build_decision("", None, analyze(""), 0.55)
    assert decision.status == "unclear"
    assert decision.severity == "warning"


def test_keyword_critical_overrides_llm_fine():
    llm = classifier.LLMResult(status="fine", confidence=0.9, summary="Doing well")
    decision = classifier.build_decision("ഞാൻ വീണു", llm, analyze("ഞാൻ വീണു"), 0.55)
    assert decision.status == "needs_help"
    assert decision.distress
    assert decision.severity == "critical"


def test_llm_distress_without_keywords():
    llm = classifier.LLMResult(status="needs_help", distress=True, confidence=0.8, summary="Feels faint")
    decision = classifier.build_decision("something worrying", llm, analyze("something worrying"), 0.55)
    assert decision.severity == "critical"


def test_low_confidence_fine_becomes_unclear():
    llm = classifier.LLMResult(status="fine", confidence=0.3, summary="Maybe fine")
    decision = classifier.build_decision("ഉം", llm, analyze("ഉം"), 0.55)
    assert decision.status == "unclear"
    assert decision.severity == "warning"


def test_fine_with_medicine_missed_is_warning():
    llm = classifier.LLMResult(status="fine", confidence=0.9, summary="Well")
    text = "സുഖമാണ്, പക്ഷേ മരുന്ന് കഴിച്ചില്ല"
    decision = classifier.build_decision(text, llm, analyze(text), 0.55)
    assert decision.medicine_taken == "no"
    assert decision.severity == "warning"


def test_fine_has_no_alert():
    llm = classifier.LLMResult(status="fine", medicine_taken="yes", confidence=0.9, summary="Well", mood="good")
    text = "സുഖമാണ്, മരുന്ന് കഴിച്ചു"
    decision = classifier.build_decision(text, llm, analyze(text), 0.55)
    assert decision.severity == "none"
    assert decision.status == "fine"


def test_llm_unavailable_falls_back_conservatively():
    decision = classifier.build_decision("സുഖമാണ്", None, analyze("സുഖമാണ്"), 0.55, "offline")
    assert decision.status == "unclear"
    assert decision.error == "offline"


def test_llm_result_coerces_bad_values():
    result = classifier.LLMResult(status="great", medicine_taken="maybe", confidence="2", distress="true", mood="odd")
    assert result.status == "unclear"
    assert result.medicine_taken == "unknown"
    assert result.confidence == 1.0
    assert result.distress is True
    assert result.mood == "unknown"


def test_public_base_url_uses_render_url(monkeypatch):
    from app.config import Settings

    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://lder-api.onrender.com")
    assert Settings().public_base_url == "https://lder-api.onrender.com"
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://custom.example.com")
    assert Settings().public_base_url == "https://custom.example.com"


def test_postgres_urls_are_normalised():
    from app.config import Settings

    assert Settings(database_url="postgres://u:p@h:5432/db").sqlalchemy_url.startswith("postgresql+psycopg2://")
    assert Settings(database_url="postgresql://u:p@h:5432/db").sqlalchemy_url.startswith("postgresql+psycopg2://")
    assert Settings(database_url="sqlite:///./x.db").sqlalchemy_url == "sqlite:///./x.db"