
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, ForeignKey, JSON, UniqueConstraint
from datetime import datetime
from .database import Base

class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email_enc: Mapped[str] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    avatar_path: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tags = relationship("RFIDTag", back_populates="player", cascade="all,delete")
    sessions = relationship("SessionPlayer", back_populates="player")

class RFIDTag(Base):
    __tablename__ = "rfid_tags"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uid: Mapped[str] = mapped_column(String, unique=True, index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    player = relationship("Player", back_populates="tags")

class Game(Base):
    __tablename__ = "games"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    kiosks = relationship("Kiosk", back_populates="game")
    sessions = relationship("GameSession", back_populates="game")

class Kiosk(Base):
    __tablename__ = "kiosks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kiosk_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    location: Mapped[str] = mapped_column(String, nullable=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    api_key_hash: Mapped[str] = mapped_column(String, nullable=True)
    modes: Mapped[dict] = mapped_column(JSON, default=dict)  # {"list":["solo","team"]}
    objectives: Mapped[list] = mapped_column(JSON, default=list)  # ["Try to beat your score", ...]
    traits: Mapped[dict] = mapped_column(JSON, default=dict)  # {"physical":3,"mental":2,"skill":4}
    objectives: Mapped[list] = mapped_column(JSON, default=list)  # ["Try to beat your score", ...]
    game = relationship("Game", back_populates="kiosks")
    queues = relationship("QueueEntry", back_populates="kiosk")
    sessions = relationship("GameSession", back_populates="kiosk")

class QueueEntry(Base):
    __tablename__ = "queue_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kiosk_id: Mapped[int] = mapped_column(ForeignKey("kiosks.id"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    kiosk = relationship("Kiosk", back_populates="queues")
    player = relationship("Player")
    __table_args__ = (UniqueConstraint("kiosk_id", "player_id", name="uq_queue_unique_player_per_kiosk"),)

class GameSession(Base):
    __tablename__ = "game_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kiosk_id: Mapped[int] = mapped_column(ForeignKey("kiosks.id"))
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|running|ended|cancelled
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    kiosk = relationship("Kiosk", back_populates="sessions")
    game = relationship("Game", back_populates="sessions")
    players = relationship("SessionPlayer", back_populates="session", cascade="all,delete")

class SessionPlayer(Base):
    __tablename__ = "session_players"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("game_sessions.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    score: Mapped[int] = mapped_column(Integer, default=0)
    play_time_sec: Mapped[int] = mapped_column(Integer, default=0)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)

    session = relationship("GameSession", back_populates="players")
    player = relationship("Player", back_populates="sessions")


class UsernameWord(Base):
    __tablename__ = "username_words"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String)  # "adj" or "noun"
    word: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
