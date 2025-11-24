
from cryptography.fernet import Fernet, InvalidToken
from ..settings import settings

_fernet = None
if settings.fernet_key:
    try:
        _fernet = Fernet(settings.fernet_key.encode())
    except Exception:
        _fernet = None

def enc(value: str) -> str:
    if not value:
        return value
    if not _fernet:
        return value
    return _fernet.encrypt(value.encode()).decode()

def dec(value: str) -> str:
    if not value:
        return value
    if not _fernet:
        return value
    try:
        return _fernet.decrypt(value.encode()).decode()
    except InvalidToken:
        return value
