
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Dict
import os

class Settings(BaseSettings):
    database_url: str = Field(default="sqlite:///./kiosk.db", alias="DATABASE_URL")
    secret_key: str = Field(default="dev-secret", alias="SECRET_KEY")
    fernet_key: str = Field(default="", alias="FERNET_KEY")
    server_host: str = Field(default="http://127.0.0.1:8000", alias="SERVER_HOST")
    kiosk_keys_raw: str = Field(default="", alias="KIOSK_KEYS")
    game_keys_raw: str = Field(default="", alias="GAME_KEYS")
    admin_username: str = Field(default="admin", alias="ADMIN_USER")
    admin_password: str = Field(default="changeme", alias="ADMIN_PASSWORD")

    @property
    def kiosk_keys(self) -> Dict[str, str]:
        res: Dict[str, str] = {}
        for pair in (self.kiosk_keys_raw or "").split(","):
            if ":" in pair:
                k,v = pair.split(":",1)
                res[k.strip()] = v.strip()
        return res

    @property
    def game_keys(self) -> Dict[str, str]:
        res: Dict[str, str] = {}
        for pair in (self.game_keys_raw or "").split(","):
            if ":" in pair:
                k,v = pair.split(":",1)
                res[k.strip()] = v.strip()
        return res

    class Config:
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")

settings = Settings()
