import httpx
import pytest

from app.config import get_settings
from app.services import classifier, narrator, otari


class FakeResponse:
    def __init__(self, status_code=200, body=None, headers=None, text=""):
        self.status_code = status_code
        self._body = body
        self.headers = httpx.Headers(headers or {})
        self.text = text or (str(body) if body is not None else "")

    def json(self):
        if self._body is None:
            raise ValueError("no body")
        return self._body


def ok_body(content, model="open/model-a", cost="0.000120"):
    return {
        "model": model,
        "choices": [{"message": {"content": content}}],
        "usage": {"cost_usd": cost},
    }


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "otari_api_key", "otk_test")
    monkeypatch.setattr(settings, "classifier_model", "policy-a")
    monkeypatch.setattr(settings, "classifier_fallback_models", "open/model-b")
    monkeypatch.setattr(otari.time, "sleep", lambda _: None)


def test_success_reads_gateway_headers(monkeypatch):
    seen = {}

    def fake_send(url, headers, payload, timeout):
        seen.update(url=url, headers=headers, payload=payload)
        return FakeResponse(
            body=ok_body('{"status": "fine"}'),
            headers={"Otari-Request-ID": "req-1", "Otari-Model": "open/model-a", "Otari-Attempt-Count": "2", "Otari-Fallback": "true"},
        )

    monkeypatch.setattr(otari, "_send", fake_send)
    content, meta = otari.chat(["policy-a"], [{"role": "user", "content": "hi"}], user="lder-elder-7", tags={"purpose": "x"})
    assert content == '{"status": "fine"}'
    assert meta.request_id == "req-1"
    assert meta.fallback is True
    assert meta.attempts == 2
    assert meta.cost_usd == pytest.approx(0.00012)
    assert seen["url"].endswith("/chat/completions")
    assert seen["headers"]["Authorization"] == "Bearer otk_test"
    assert seen["payload"]["user"] == "lder-elder-7"
    assert seen["payload"]["metadata"] == {"purpose": "x"}


def test_falls_through_to_next_model_on_error(monkeypatch):
    calls = []

    def fake_send(url, headers, payload, timeout):
        calls.append(payload["model"])
        if payload["model"] == "policy-a":
            return FakeResponse(status_code=400, body={"detail": "invalid model", "code": "invalid_model"})
        return FakeResponse(body=ok_body("done", model="open/model-b"))

    monkeypatch.setattr(otari, "_send", fake_send)
    content, meta = otari.chat(["policy-a", "open/model-b"], [{"role": "user", "content": "hi"}])
    assert content == "done"
    assert calls == ["policy-a", "open/model-b"]
    assert meta.fallback is True
    assert meta.models_tried == ["policy-a", "open/model-b"]


def test_retries_rate_limit_then_succeeds(monkeypatch):
    responses = [FakeResponse(status_code=429, body={"detail": "slow down", "code": "rate_limited"}), FakeResponse(body=ok_body("ok"))]
    monkeypatch.setattr(otari, "_send", lambda *a, **k: responses.pop(0))
    content, _ = otari.chat(["policy-a"], [{"role": "user", "content": "hi"}])
    assert content == "ok"


def test_budget_error_stops_immediately(monkeypatch):
    calls = []

    def fake_send(url, headers, payload, timeout):
        calls.append(payload["model"])
        return FakeResponse(status_code=403, body={"detail": "limit reached", "code": "budget_exceeded"})

    monkeypatch.setattr(otari, "_send", fake_send)
    with pytest.raises(otari.OtariError) as info:
        otari.chat(["policy-a", "open/model-b"], [{"role": "user", "content": "hi"}])
    assert info.value.kind == "budget"
    assert calls == ["policy-a"]


def test_guardrail_error_is_reported(monkeypatch):
    monkeypatch.setattr(
        otari,
        "_send",
        lambda *a, **k: FakeResponse(status_code=400, body={"detail": "blocked by guardrail", "code": "guardrail_blocked"}),
    )
    with pytest.raises(otari.OtariError) as info:
        otari.chat(["policy-a"], [{"role": "user", "content": "hi"}])
    assert info.value.kind == "guardrail"


def test_missing_key_raises_config_error(monkeypatch):
    monkeypatch.setattr(get_settings(), "otari_api_key", "")
    with pytest.raises(otari.OtariError) as info:
        otari.chat(["policy-a"], [{"role": "user", "content": "hi"}])
    assert info.value.kind == "config"


def test_classifier_uses_chain_and_attaches_gateway(monkeypatch):
    captured = {}

    def fake_chat(models, messages, **kwargs):
        captured.update(models=models, kwargs=kwargs, messages=messages)
        meta = otari.GatewayMeta(requested_model=models[0], model="open/model-a", request_id="r1", cost_usd=0.001)
        return '{"status": "fine", "confidence": 0.9, "summary": "Well", "medicine_taken": "yes"}', meta

    monkeypatch.setattr(otari, "chat", fake_chat)
    result = classifier.classify_with_llm("സുഖമാണ്", ["Amlodipine"], "morning", elder_id=3, idempotency_key="k1", language="ml")
    assert captured["models"] == ["policy-a", "open/model-b"]
    assert captured["kwargs"]["user"] == "lder-elder-3"
    assert captured["kwargs"]["idempotency_key"] == "k1"
    assert captured["kwargs"]["json_mode"] is True
    assert result.status == "fine"
    assert result.gateway["request_id"] == "r1"


def test_classifier_maps_budget_error(monkeypatch):
    def fake_chat(*args, **kwargs):
        raise otari.OtariError("limit", code="budget_exceeded", kind="budget")

    monkeypatch.setattr(otari, "chat", fake_chat)
    with pytest.raises(classifier.ClassifierError) as info:
        classifier.classify_with_llm("hello", [], "morning", elder_id=1)
    assert info.value.kind == "budget"


def test_classifier_rejects_non_json(monkeypatch):
    monkeypatch.setattr(otari, "chat", lambda *a, **k: ("no json here", otari.GatewayMeta()))
    with pytest.raises(classifier.ClassifierError):
        classifier.classify_with_llm("hello", [], "morning", elder_id=1)


def test_weekly_note_returns_text(monkeypatch):
    monkeypatch.setattr(get_settings(), "summary_model", "small-model")
    monkeypatch.setattr(otari, "chat", lambda models, messages, **k: ("A calm week.", otari.GatewayMeta()))
    stats = {"total": 14, "responded": 13, "missed": 1, "response_rate": 93, "adherence_pct": 90}
    assert narrator.weekly_note("Amma", 1, stats) == "A calm week."


def test_weekly_note_none_on_failure(monkeypatch):
    def boom(*args, **kwargs):
        raise otari.OtariError("down")

    monkeypatch.setattr(otari, "chat", boom)
    assert narrator.weekly_note("Amma", 1, {}) is None
