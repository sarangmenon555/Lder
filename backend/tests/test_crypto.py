import pytest
from cryptography.fernet import Fernet

from app import crypto
from app.config import get_settings


@pytest.fixture(autouse=True)
def reset_cache():
    crypto._fernet.cache_clear()
    yield
    crypto._fernet.cache_clear()


def test_plaintext_when_no_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "encryption_key", "")
    assert crypto.encrypt("hello") == "hello"
    assert crypto.decrypt("hello") == "hello"


def test_round_trip_with_fernet_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "encryption_key", Fernet.generate_key().decode())
    token = crypto.encrypt("ഞാൻ സുഖമായിരിക്കുന്നു")
    assert token.startswith("enc:")
    assert crypto.decrypt(token) == "ഞാൻ സുഖമായിരിക്കുന്നു"


def test_round_trip_with_arbitrary_secret(monkeypatch):
    monkeypatch.setattr(get_settings(), "encryption_key", "any-long-generated-secret-value+/=")
    token = crypto.encrypt("check-in")
    assert token.startswith("enc:")
    assert crypto.decrypt(token) == "check-in"


def test_wrong_key_is_unreadable(monkeypatch):
    monkeypatch.setattr(get_settings(), "encryption_key", "first-secret")
    token = crypto.encrypt("private")
    crypto._fernet.cache_clear()
    monkeypatch.setattr(get_settings(), "encryption_key", "second-secret")
    assert crypto.decrypt(token) == "[unreadable]"


def test_encrypted_value_without_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "encryption_key", "first-secret")
    token = crypto.encrypt("private")
    crypto._fernet.cache_clear()
    monkeypatch.setattr(get_settings(), "encryption_key", "")
    assert crypto.decrypt(token) == "[encrypted]"