
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any

class PlayerCreate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    username: Optional[str] = None
    rfid_uid: Optional[str] = None

class PlayerOut(BaseModel):
    id: int
    email: Optional[str] = None
    name: Optional[str] = None
    username: str
    avatar_url: Optional[str] = None
    class Config:
        from_attributes = True

class PlayerUpdate(BaseModel):
    name: Optional[str] = None
    random_avatar: Optional[bool] = False

class RFIDScanIn(BaseModel):
    kiosk_id: str
    rfid_uid: str

class GameCreate(BaseModel):
    game_id: str
    name: str

class KioskCreate(BaseModel):
    kiosk_id: str
    location: Optional[str] = None
    game_id: str
    api_key: Optional[str] = None
    modes: Optional[Dict[str, Any]] = None  # {"list":[...]}
    objectives: Optional[List[str]] = None  # ["Hint 1", "Hint 2"]
    traits: Optional[Dict[str, Any]] = None  # {"physical":3,"mental":2,"skill":4}

class KioskUpdate(BaseModel):
    location: Optional[str] = None
    modes: Optional[Dict[str, Any]] = None  # {"list":[...]}
    objectives: Optional[List[str]] = None  # ["Hint 1", "Hint 2"]
    traits: Optional[Dict[str, Any]] = None  # {"physical":3,"mental":2,"skill":4}

class QueueLeaveIn(BaseModel):
    player_id: int

class SessionStartIn(BaseModel):
    kiosk_id: str
    mode: Optional[str] = None

class SessionEndIn(BaseModel):
    session_id: int
    game_metrics: Dict[str, Any] = Field(default_factory=dict)
    players: List[Dict[str, Any]]  # [{player_id, score, play_time_sec, metrics:{}}]

class SessionOut(BaseModel):
    id: int
    status: str
    game_id: int
