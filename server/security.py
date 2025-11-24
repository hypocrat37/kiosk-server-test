
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from .settings import settings
import secrets

def verify_kiosk_key(request: Request, kiosk_id: str):
    api_key = request.headers.get("X-API-Key")
    expected = settings.kiosk_keys.get(kiosk_id)
    if not expected or api_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid kiosk API key")

def verify_game_key(request: Request, game_id: str):
    api_key = request.headers.get("X-API-Key")
    expected = settings.game_keys.get(game_id)
    if not expected or api_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid game client API key")


_admin_basic = HTTPBasic()

def verify_admin(credentials: HTTPBasicCredentials = Depends(_admin_basic)) -> bool:
    """
    HTTP Basic auth guard for admin-only pages and tools.
    Username/password are configured via ADMIN_USER / ADMIN_PASSWORD env vars.
    """
    correct_username = secrets.compare_digest(credentials.username, settings.admin_username)
    correct_password = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True
