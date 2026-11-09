import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import Text, TypeDecorator

from .config import get_settings

PREFIX = "enc:"


@lru_cache
def _fernet() -> Fernet | None:
    key = get_settings().encryption_key
    if not key:
        return None
    try:
        return Fernet(key.encode())
    except ValueError:
        derived = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
        return Fernet(derived)


def encrypt(value: str | None) -> str | None:
    if value is None:
        return None
    f = _fernet()
    if f is None:
        return value
    return PREFIX + f.encrypt(value.encode()).decode()


def decrypt(value: str | None) -> str | None:
    if value is None:
        return None
    if not value.startswith(PREFIX):
        return value
    f = _fernet()
    if f is None:
        return "[encrypted]"
    try:
        return f.decrypt(value[len(PREFIX):].encode()).decode()
    except InvalidToken:
        return "[unreadable]"


class EncryptedText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt(value)

    def process_result_value(self, value, dialect):
        return decrypt(value)