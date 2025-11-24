
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import os, uuid, shutil, random, re

from ..deps import get_db
from .. import models
from ..schemas import PlayerCreate, PlayerOut, PlayerUpdate
from ..services.encryption import enc, dec

router = APIRouter(prefix="/players", tags=["players"])

AVATAR_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)

ADJECTIVES = [
    "brave", "clever", "curious", "swift", "bright",
    "mighty", "quiet", "lucky", "witty", "bold",
    "sneaky", "gentle", "fierce", "cosmic", "stellar",
]
NOUNS = [
    "tiger", "dragon", "panda", "falcon", "otter",
    "wizard", "ranger", "ninja", "pirate", "robot",
    "phoenix", "galaxy", "comet", "builder", "guardian",
]

OFFENSIVE_WORDS = {
    "fuck", "shit", "bitch", "bastard", "asshole", "douche",
    "damn", "hell", "pussy", "nigger", "nigga",
}
blocked_words_store: set[str] = set()

def _validate_display_name(name: Optional[str]):
    """
    Ensure display names avoid offensive language and restrict characters
    to letters/spaces.
    """
    if not name:
        return
    if re.search(r"[^A-Za-z\\s]", name):
        raise HTTPException(
            status_code=400,
            detail="Name can only include letters and spaces.",
        )
    lowered = name.lower()
    for bad in OFFENSIVE_WORDS.union(blocked_words_store):
        if bad and bad in lowered:
            raise HTTPException(status_code=400, detail="Please choose a different name.")


def _random_avatar_filename() -> Optional[str]:
  try:
    files = [f for f in os.listdir(AVATAR_DIR) if not f.startswith('.') and f != "default.png"]
  except FileNotFoundError:
    return None
  if not files:
    return None
  return random.choice(files)

def _generate_username(db: Session) -> str:
  """
  Generate a random 'adjective.noun' username and ensure uniqueness.
  Falls back to adding a number suffix if needed.
  """
  for _ in range(20):
    adj = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    candidate = f"{adj}.{noun}"
    if not db.query(models.Player).filter(models.Player.username == candidate).first():
      return candidate
  # Fallback with numeric suffix
  while True:
    adj = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    suffix = random.randint(1, 999)
    candidate = f"{adj}.{noun}{suffix}"
    if not db.query(models.Player).filter(models.Player.username == candidate).first():
      return candidate

@router.get("", response_model=List[PlayerOut])
def list_players(limit: int = 200, db: Session = Depends(get_db)):
    """
    Lightweight listing endpoint for admin/dev tooling.
    Returns up to `limit` most-recent players.
    """
    limit = max(1, min(int(limit), 500))
    players = (
        db.query(models.Player)
        .order_by(models.Player.created_at.desc())
        .limit(limit)
        .all()
    )
    out: List[PlayerOut] = []
    for p in players:
        out.append(
            PlayerOut(
                id=p.id,
                email=dec(p.email_enc) if p.email_enc else None,
                name=p.name,
                username=p.username,
                avatar_url=f"/static/avatars/{os.path.basename(p.avatar_path)}" if p.avatar_path else None,
            )
        )
    return out


@router.get("/words")
def get_username_words(db: Session = Depends(get_db)) -> Dict[str, List[Dict[str, Any]]]:
    """
    Return the combined adjective/noun pools used to generate usernames.
    Includes built-in defaults plus any custom words stored in the DB.
    """
    extra = db.query(models.UsernameWord).all()
    extra_adj = [w.word for w in extra if w.kind == "adj"]
    extra_nouns = [w.word for w in extra if w.kind == "noun"]
    default_adj = set(ADJECTIVES)
    default_nouns = set(NOUNS)
    all_adj = sorted(set(ADJECTIVES + extra_adj))
    all_nouns = sorted(set(NOUNS + extra_nouns))
    adjectives = [{"word": w, "builtin": w in default_adj} for w in all_adj]
    nouns = [{"word": w, "builtin": w in default_nouns} for w in all_nouns]
    return {"adjectives": adjectives, "nouns": nouns}


@router.post("/words")
def add_username_word(payload: Dict[str, str], db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Add a new adjective or noun to the username pools.
    Body: {"kind": "adj"|"noun", "word": "bright"}
    """
    kind = (payload.get("kind") or "").strip().lower()
    word = (payload.get("word") or "").strip().lower()
    if kind not in {"adj", "noun"}:
        raise HTTPException(status_code=400, detail="kind must be 'adj' or 'noun'")
    if not word or " " in word:
        raise HTTPException(status_code=400, detail="Word must be a single non-empty token")

    # Prevent duplicates across defaults + extras
    default_pool = ADJECTIVES if kind == "adj" else NOUNS
    if word in default_pool:
        raise HTTPException(status_code=400, detail="Word already in defaults")
    exists = db.query(models.UsernameWord).filter_by(kind=kind, word=word).first()
    if exists:
        raise HTTPException(status_code=400, detail="Word already added")

    w = models.UsernameWord(kind=kind, word=word)
    db.add(w)
    db.commit()
    return {"ok": True, "kind": kind, "word": word}


@router.delete("/words")
def delete_username_word(kind: str, word: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Delete a custom adjective or noun from the username pools.
    Does not allow removing built-in defaults.
    Query params: kind=adj|noun&word=...
    """
    kind = (kind or "").strip().lower()
    word = (word or "").strip().lower()
    if kind not in {"adj", "noun"}:
        raise HTTPException(status_code=400, detail="kind must be 'adj' or 'noun'")
    if not word:
        raise HTTPException(status_code=400, detail="Word is required")

    default_pool = ADJECTIVES if kind == "adj" else NOUNS
    if word in default_pool:
        raise HTTPException(status_code=400, detail="Cannot delete built-in word")

    row = db.query(models.UsernameWord).filter_by(kind=kind, word=word).first()
    if not row:
        raise HTTPException(status_code=404, detail="Word not found")

    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/blocked_words")
def list_blocked_words() -> Dict[str, Any]:
    """
    Return the current in-memory blocked words list (admin/dev use only).
    """
    return {
        "words": sorted(blocked_words_store),
        "default": sorted(OFFENSIVE_WORDS),
    }


@router.post("/blocked_words")
def add_blocked_word(payload: Dict[str, str]) -> Dict[str, Any]:
    word = (payload.get("word") or "").strip().lower()
    if not word or " " in word:
        raise HTTPException(status_code=400, detail="Word must be a single non-empty token")
    blocked_words_store.add(word)
    return {"ok": True, "word": word}


@router.delete("/blocked_words")
def remove_blocked_word(word: str) -> Dict[str, Any]:
    w = (word or "").strip().lower()
    if not w:
        raise HTTPException(status_code=400, detail="Word is required")
    if w in OFFENSIVE_WORDS:
        raise HTTPException(status_code=400, detail="Cannot remove default blocked words")
    if w in blocked_words_store:
        blocked_words_store.remove(w)
    return {"ok": True, "word": w}


@router.post("", response_model=PlayerOut)
def create_player(data: PlayerCreate, db: Session = Depends(get_db)):
    name = data.name.strip() if data.name else None
    _validate_display_name(name)
    username = data.username or _generate_username(db)
    if db.query(models.Player).filter(models.Player.username == username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    avatar_fname = _random_avatar_filename()
    p = models.Player(
        email_enc=enc(data.email) if data.email else None,
        name=name,
        username=username,
        avatar_path=os.path.join(AVATAR_DIR, avatar_fname) if avatar_fname else None,
    )
    db.add(p)
    db.flush()
    if data.rfid_uid:
        existing = db.query(models.RFIDTag).filter_by(uid=data.rfid_uid).first()
        if existing and existing.player_id != p.id:
            raise HTTPException(status_code=400, detail="Tag already assigned")
        tag = existing or models.RFIDTag(uid=data.rfid_uid, player_id=p.id)
        db.add(tag)
    db.commit()
    return PlayerOut(
        id=p.id,
        email=dec(p.email_enc) if p.email_enc else None,
        name=p.name,
        username=p.username,
        avatar_url=f"/static/avatars/{os.path.basename(p.avatar_path)}" if p.avatar_path else None,
    )

@router.get("/{player_id}", response_model=PlayerOut)
def get_player(player_id: int, db: Session = Depends(get_db)):
    p = db.get(models.Player, player_id)
    if not p:
        raise HTTPException(status_code=404, detail="Player not found")
    return PlayerOut(
        id=p.id,
        email=dec(p.email_enc) if p.email_enc else None,
        name=p.name,
        username=p.username,
        avatar_url=f"/static/avatars/{os.path.basename(p.avatar_path)}" if p.avatar_path else None,
    )


@router.patch("/{player_id}", response_model=PlayerOut)
def update_player(player_id: int, data: PlayerUpdate, db: Session = Depends(get_db)):
    p = db.get(models.Player, player_id)
    if not p:
        raise HTTPException(status_code=404, detail="Player not found")

    if data.name is not None:
        cleaned_name = data.name.strip()
        _validate_display_name(cleaned_name)
        p.name = cleaned_name

    # Assign a random avatar if requested
    if data.random_avatar:
        fname = _random_avatar_filename()
        if fname:
            p.avatar_path = os.path.join(AVATAR_DIR, fname)

    db.commit()
    return PlayerOut(
        id=p.id,
        email=dec(p.email_enc) if p.email_enc else None,
        name=p.name,
        username=p.username,
        avatar_url=f"/static/avatars/{os.path.basename(p.avatar_path)}" if p.avatar_path else None,
    )

@router.post("/{player_id}/avatar", response_model=PlayerOut)
def upload_avatar(player_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    p = db.get(models.Player, player_id)
    if not p:
        raise HTTPException(status_code=404, detail="Player not found")
    ext = os.path.splitext(file.filename)[1].lower()
    fname = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(AVATAR_DIR, fname)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    p.avatar_path = dest
    db.commit()
    return PlayerOut(
        id=p.id,
        email=dec(p.email_enc) if p.email_enc else None,
        name=p.name,
        username=p.username,
        avatar_url=f"/static/avatars/{fname}",
    )


@router.delete("/{player_id}")
def delete_player(player_id: int, db: Session = Depends(get_db)):
    """
    Development helper to remove a player and related data.
    Clears RFID tags, queue entries, and session player rows before deleting.
    """
    player = db.get(models.Player, player_id)
    if not player:
      raise HTTPException(status_code=404, detail="Player not found")

    # Clear queue entries for this player across kiosks
    db.query(models.QueueEntry).filter_by(player_id=player.id).delete(synchronize_session=False)

    # Clear per-session player records
    db.query(models.SessionPlayer).filter_by(player_id=player.id).delete(synchronize_session=False)

    # RFID tags are configured with cascade delete via relationship
    db.delete(player)
    db.commit()
    return {"ok": True}


@router.get("/{player_id}/history")
def player_history(player_id: int, limit: int = 100, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Return recent game sessions for a given player, grouped by sessions.
    Intended for use by kiosk UIs when a player taps their profile.
    """
    player = db.get(models.Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    limit = max(1, min(int(limit), 200))
    rows = (
        db.query(models.SessionPlayer, models.GameSession, models.Game, models.Kiosk)
        .join(models.GameSession, models.SessionPlayer.session_id == models.GameSession.id)
        .join(models.Game, models.GameSession.game_id == models.Game.id)
        .join(models.Kiosk, models.GameSession.kiosk_id == models.Kiosk.id)
        .filter(models.SessionPlayer.player_id == player_id)
        .order_by(models.GameSession.started_at.desc())
        .limit(limit)
        .all()
    )

    sessions: List[Dict[str, Any]] = []
    for sp, sess, game, kiosk in rows:
        sess_meta = sess.meta or {}
        sp_metrics = sp.metrics or {}
        # Prefer explicit session.meta["mode"]; fall back to per-player metrics.kiosk_mode.
        mode = sess_meta.get("mode") or sp_metrics.get("kiosk_mode") or "default"
        sessions.append(
            {
                "session_id": sess.id,
                "game_id": game.game_id if game else None,
                "game_name": game.name if game else None,
                "kiosk_id": kiosk.kiosk_id if kiosk else None,
                "location": kiosk.location if kiosk else None,
                "started_at": sess.started_at.isoformat() if sess.started_at else None,
                "ended_at": sess.ended_at.isoformat() if sess.ended_at else None,
                "status": sess.status,
                "mode": mode,
                "score": sp.score,
                "play_time_sec": sp.play_time_sec,
                "metrics": sp_metrics,
            }
        )
    return {"player_id": player_id, "sessions": sessions}
