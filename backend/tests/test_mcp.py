import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.security import create_scoped_token, create_token, verify_scoped_token, verify_token
from app.services import otari


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def headers(client):
    token = client.post("/api/auth/login", json={"password": "test-password"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def make_elder(client, headers, name):
    payload = {
        "name": name,
        "timezone": "Asia/Kolkata",
        "check_in_times": ["08:30"],
        "consent": True,
        "contacts": [{"name": "Daughter", "channel": "dashboard", "priority": 1}],
        "medicines": [{"name": "Amlodipine", "time_of_day": "08:00"}],
    }
    return client.post("/api/elders", json=payload, headers=headers).json()


def rpc(client, token, method, params=None, request_id=1):
    body = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        body["id"] = request_id
    if params is not None:
        body["params"] = params
    return client.post("/api/mcp", json=body, headers={"Authorization": f"Bearer {token}"})


def test_scoped_token_round_trip_and_expiry():
    token = create_scoped_token(5, 60)
    assert verify_scoped_token(token) == 5
    assert verify_scoped_token(create_scoped_token(5, -10)) is None
    assert verify_scoped_token(token + "x") is None


def test_scoped_token_cannot_open_dashboard_api(client):
    token = create_scoped_token(1, 60)
    assert verify_token(token) is False
    assert client.get("/api/elders", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_admin_token_is_not_a_scoped_token():
    assert verify_scoped_token(create_token()) is None


def test_mcp_requires_token(client):
    assert client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"}).status_code == 401
    bad = client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"}, headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401


def test_mcp_initialize_and_list_tools(client, headers):
    elder = make_elder(client, headers, "Mcp Elder")
    token = create_scoped_token(elder["id"], 60)
    init = rpc(client, token, "initialize", {"protocolVersion": "2025-06-18"}).json()
    assert init["result"]["protocolVersion"] == "2025-06-18"
    assert init["result"]["serverInfo"]["name"] == "lder-checkins"
    listed = rpc(client, token, "tools/list").json()
    names = [tool["name"] for tool in listed["result"]["tools"]]
    assert names == ["get_profile", "get_recent_checkins", "get_summary", "get_alerts"]
    assert rpc(client, token, "notifications/initialized", request_id=None).status_code == 202


def test_mcp_tools_are_scoped_to_the_token_elder(client, headers):
    first = make_elder(client, headers, "First Elder")
    second = make_elder(client, headers, "Second Elder")
    token = create_scoped_token(first["id"], 60)
    reply = rpc(client, token, "tools/call", {"name": "get_profile", "arguments": {"elder_id": second["id"]}}).json()
    text = reply["result"]["content"][0]["text"]
    assert "First Elder" in text
    assert "Second Elder" not in text


def test_mcp_unknown_tool_and_method(client, headers):
    elder = make_elder(client, headers, "Unknown Tool Elder")
    token = create_scoped_token(elder["id"], 60)
    assert rpc(client, token, "tools/call", {"name": "delete_everything"}).json()["error"]["code"] == -32602
    assert rpc(client, token, "nope").json()["error"]["code"] == -32601


def test_mcp_summary_and_checkins_tools(client, headers):
    elder = make_elder(client, headers, "Data Elder")
    token = create_scoped_token(elder["id"], 60)
    summary = rpc(client, token, "tools/call", {"name": "get_summary", "arguments": {"days": 7}}).json()
    assert '"total"' in summary["result"]["content"][0]["text"]
    recent = rpc(client, token, "tools/call", {"name": "get_recent_checkins", "arguments": {"limit": 5}}).json()
    assert recent["result"]["isError"] is False


def test_ask_uses_inline_mcp_server_over_https(client, headers, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "otari_api_key", "otk_test")
    monkeypatch.setattr(settings, "mcp_public_url", "https://lder.example.com")
    elder = make_elder(client, headers, "Ask Elder")
    captured = {}

    def fake_chat(models, messages, **kwargs):
        captured.update(models=models, messages=messages, kwargs=kwargs)
        return "She answered both check-ins.", otari.GatewayMeta(model="open/model-a")

    monkeypatch.setattr(otari, "chat", fake_chat)
    reply = client.post(f"/api/elders/{elder['id']}/ask", json={"question": "How was this week?"}, headers=headers)
    assert reply.status_code == 200
    assert reply.json()["mode"] == "mcp"
    server = captured["kwargs"]["extra"]["mcp_servers"][0]
    assert server["url"] == "https://lder.example.com/api/mcp"
    assert verify_scoped_token(server["authorization_token"]) == elder["id"]
    assert server["allowed_tools"] == ["get_profile", "get_recent_checkins", "get_summary", "get_alerts"]
    assert captured["kwargs"]["user"] == f"lder-elder-{elder['id']}"


def test_ask_falls_back_to_context_without_https(client, headers, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "otari_api_key", "otk_test")
    monkeypatch.setattr(settings, "mcp_public_url", "")
    monkeypatch.setattr(settings, "public_base_url", "http://localhost:8000")
    elder = make_elder(client, headers, "Context Elder")
    captured = {}

    def fake_chat(models, messages, **kwargs):
        captured.update(messages=messages, kwargs=kwargs)
        return "No concerns.", otari.GatewayMeta()

    monkeypatch.setattr(otari, "chat", fake_chat)
    reply = client.post(f"/api/elders/{elder['id']}/ask", json={"question": "Any worries?"}, headers=headers)
    assert reply.json()["mode"] == "context"
    assert captured["kwargs"]["extra"] is None
    assert "Context Elder" in captured["messages"][1]["content"]


def test_ask_maps_budget_and_guardrail_errors(client, headers, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "otari_api_key", "otk_test")
    elder = make_elder(client, headers, "Limit Elder")

    def budget(*args, **kwargs):
        raise otari.OtariError("limit", kind="budget")

    monkeypatch.setattr(otari, "chat", budget)
    assert client.post(f"/api/elders/{elder['id']}/ask", json={"question": "Hello there"}, headers=headers).status_code == 402

    def blocked(*args, **kwargs):
        raise otari.OtariError("blocked", kind="guardrail")

    monkeypatch.setattr(otari, "chat", blocked)
    assert client.post(f"/api/elders/{elder['id']}/ask", json={"question": "Hello there"}, headers=headers).status_code == 400


def test_ask_requires_login_and_valid_elder(client, headers):
    assert client.post("/api/elders/1/ask", json={"question": "Hello there"}).status_code == 401
    assert client.post("/api/elders/999999/ask", json={"question": "Hello there"}, headers=headers).status_code == 404
