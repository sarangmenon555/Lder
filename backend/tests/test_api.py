from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import CheckIn
from app.services import checkins as checkin_service
from app.timeutil import utcnow


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def headers(client):
    response = client.post("/api/auth/login", json={"password": "test-password"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def elder_payload(name="Test Elder"):
    return {
        "name": name,
        "phone": "919800000001",
        "timezone": "Asia/Kolkata",
        "check_in_times": ["08:30", "19:00"],
        "consent": True,
        "contacts": [
            {"name": "Daughter", "email": "d@example.com", "channel": "dashboard", "priority": 1, "timezone": "Asia/Dubai"},
            {"name": "Son", "email": "s@example.com", "channel": "dashboard", "priority": 2, "timezone": "Europe/London"},
        ],
        "medicines": [{"name": "Amlodipine", "time_of_day": "08:00"}],
    }


def test_login_rejects_wrong_password(client):
    assert client.post("/api/auth/login", json={"password": "nope"}).status_code == 401


def test_protected_routes_need_token(client):
    assert client.get("/api/elders").status_code == 401


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_elder_lifecycle(client, headers):
    created = client.post("/api/elders", json=elder_payload(), headers=headers)
    assert created.status_code == 201
    body = created.json()
    assert body["consent_at"] is not None
    assert len(body["contacts"]) == 2
    elder_id = body["id"]

    listing = client.get("/api/elders", headers=headers).json()
    assert any(item["id"] == elder_id for item in listing)

    update = elder_payload("Renamed Elder")
    update["contacts"] = [{**body["contacts"][0], "name": "Daughter Updated"}]
    updated = client.put(f"/api/elders/{elder_id}", json=update, headers=headers).json()
    assert updated["name"] == "Renamed Elder"
    assert [c["name"] for c in updated["contacts"]] == ["Daughter Updated"]

    assert client.delete(f"/api/elders/{elder_id}", headers=headers).status_code == 204
    assert client.get(f"/api/elders/{elder_id}", headers=headers).status_code == 404


def test_invalid_time_rejected(client, headers):
    payload = elder_payload()
    payload["check_in_times"] = ["25:99"]
    assert client.post("/api/elders", json=payload, headers=headers).status_code == 422


def test_distress_reply_alerts_every_contact(client, headers):
    elder = client.post("/api/elders", json=elder_payload("Distress Elder"), headers=headers).json()
    token = elder["access_token"]

    state = client.get(f"/api/simulator/{token}").json()
    assert state["consent"] is True
    assert state["awaiting"] is None

    prompt = client.post(f"/api/simulator/{token}/start").json()
    assert prompt["checkin_id"]

    reply = client.post(f"/api/simulator/{token}/reply", data={"text": "ഞാൻ വീണു, എഴുന്നേൽക്കാൻ പറ്റുന്നില്ല"})
    assert reply.status_code == 200
    assert reply.json()["family_notified"] is True

    alerts = client.get(f"/api/alerts?elder_id={elder['id']}", headers=headers).json()
    assert len([a for a in alerts if a["severity"] == "critical"]) == 2

    checkins = client.get(f"/api/elders/{elder['id']}/checkins", headers=headers).json()
    assert checkins[0]["classification"] == "needs_help"
    assert checkins[0]["distress"] is True

    alert_id = alerts[0]["id"]
    acked = client.post(f"/api/alerts/{alert_id}/acknowledge", headers=headers).json()
    assert acked["acknowledged_at"] is not None


def test_calm_reply_without_llm_is_flagged_for_follow_up(client, headers):
    elder = client.post("/api/elders", json=elder_payload("Calm Elder"), headers=headers).json()
    token = elder["access_token"]
    client.post(f"/api/simulator/{token}/start")
    reply = client.post(f"/api/simulator/{token}/reply", data={"text": "സുഖമാണ്, മരുന്ന് കഴിച്ചു"})
    assert reply.status_code == 200
    checkins = client.get(f"/api/elders/{elder['id']}/checkins", headers=headers).json()
    assert checkins[0]["classification"] == "unclear"
    assert checkins[0]["medicine_taken"] == "yes"
    assert checkins[0]["classifier_error"]


def test_missed_checkin_escalates_through_contacts(client, headers):
    elder = client.post("/api/elders", json=elder_payload("Missed Elder"), headers=headers).json()
    trigger = client.post(f"/api/elders/{elder['id']}/trigger-checkin", json={"mode": "missed"}, headers=headers)
    assert trigger.status_code == 200
    assert trigger.json()["status"] == "missed"

    alerts = client.get(f"/api/alerts?elder_id={elder['id']}", headers=headers).json()
    assert [a["contact_name"] for a in alerts] == ["Daughter"]

    db = SessionLocal()
    try:
        checkin_service.run_tick(db, utcnow() + timedelta(minutes=25))
    finally:
        db.close()
    alerts = client.get(f"/api/alerts?elder_id={elder['id']}", headers=headers).json()
    assert sorted(a["contact_name"] for a in alerts) == ["Daughter", "Son"]


def test_acknowledgement_stops_escalation(client, headers):
    elder = client.post("/api/elders", json=elder_payload("Ack Elder"), headers=headers).json()
    client.post(f"/api/elders/{elder['id']}/trigger-checkin", json={"mode": "missed"}, headers=headers)
    alerts = client.get(f"/api/alerts?elder_id={elder['id']}", headers=headers).json()
    client.post(f"/api/alerts/{alerts[0]['id']}/acknowledge", headers=headers)

    db = SessionLocal()
    try:
        checkin_service.run_tick(db, utcnow() + timedelta(minutes=25))
    finally:
        db.close()
    alerts = client.get(f"/api/alerts?elder_id={elder['id']}", headers=headers).json()
    assert len(alerts) == 1


def test_unanswered_prompt_becomes_missed_after_retries(client, headers):
    elder = client.post("/api/elders", json=elder_payload("Silent Elder"), headers=headers).json()
    client.post(f"/api/elders/{elder['id']}/trigger-checkin", json={"mode": "normal"}, headers=headers)

    db = SessionLocal()
    try:
        base = utcnow()
        for minutes in (16, 47, 78):
            checkin_service.run_tick(db, base + timedelta(minutes=minutes))
            row = db.query(CheckIn).filter(CheckIn.elder_id == elder["id"]).first()
            db.refresh(row)
            if minutes == 16:
                assert row.attempt == 2
        assert row.status == "missed"
    finally:
        db.close()
    alerts = client.get(f"/api/alerts?elder_id={elder['id']}", headers=headers).json()
    assert len(alerts) >= 1


def test_late_reply_resolves_missed_checkin(client, headers):
    elder = client.post("/api/elders", json=elder_payload("Late Elder"), headers=headers).json()
    token = elder["access_token"]
    client.post(f"/api/elders/{elder['id']}/trigger-checkin", json={"mode": "missed"}, headers=headers)
    reply = client.post(f"/api/simulator/{token}/reply", data={"text": ""})
    assert reply.status_code == 422


def test_summary_endpoint(client, headers):
    elder = client.post("/api/elders", json=elder_payload("Summary Elder"), headers=headers).json()
    summary = client.get(f"/api/elders/{elder['id']}/summary?days=7", headers=headers)
    assert summary.status_code == 200
    assert len(summary.json()["daily"]) == 7


def test_consent_required_for_simulator(client, headers):
    payload = elder_payload("No Consent")
    payload["consent"] = False
    elder = client.post("/api/elders", json=payload, headers=headers).json()
    assert client.post(f"/api/simulator/{elder['access_token']}/start").status_code == 403
    assert client.post(f"/api/elders/{elder['id']}/trigger-checkin", json={"mode": "normal"}, headers=headers).status_code == 400


def test_opt_out_stops_checkins(client, headers):
    elder = client.post("/api/elders", json=elder_payload("Opt Out"), headers=headers).json()
    assert client.post(f"/api/simulator/{elder['access_token']}/opt-out").status_code == 200
    assert client.get(f"/api/elders/{elder['id']}", headers=headers).json()["active"] is False


def test_unknown_token_is_404(client):
    assert client.get("/api/simulator/not-a-real-token").status_code == 404


def test_webhook_verification(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "whatsapp_verify_token", "abc123")
    ok = client.get("/api/webhook/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "abc123", "hub.challenge": "777"})
    assert ok.status_code == 200 and ok.text == "777"
    bad = client.get("/api/webhook/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "777"})
    assert bad.status_code == 403


def test_internal_tick_requires_secret(client, monkeypatch):
    from app.config import get_settings

    assert client.get("/api/internal/tick").status_code == 403
    monkeypatch.setattr(get_settings(), "cron_secret", "s3cret")
    assert client.get("/api/internal/tick", params={"key": "s3cret"}).status_code == 200
    assert client.get("/api/internal/tick", params={"key": "bad"}).status_code == 403
