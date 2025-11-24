
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from ..deps import get_db
from .. import models
from ..schemas import GameCreate
from ..security import verify_game_key
from ..services.queue_manager import hub

router = APIRouter(prefix="/games", tags=["games"])

@router.post("")
def create_game(data: GameCreate, db: Session = Depends(get_db)):
    if db.query(models.Game).filter_by(game_id=data.game_id).first():
        raise HTTPException(status_code=400, detail="Game exists")
    g = models.Game(game_id=data.game_id, name=data.name)
    db.add(g); db.commit()
    return {"ok": True}

@router.post("/ready")
async def game_ready(game_id: str, kiosk_id: str, request: Request, db: Session = Depends(get_db)):
    verify_game_key(request, game_id)
    kiosk = db.query(models.Kiosk).filter_by(kiosk_id=kiosk_id).first()
    game = db.query(models.Game).filter_by(game_id=game_id).first()
    if not kiosk or not game or kiosk.game_id != game.id:
        raise HTTPException(status_code=400, detail="Invalid kiosk/game mapping")
    q_count = db.query(models.QueueEntry).filter_by(kiosk_id=kiosk.id).count()
    await hub.broadcast("game", game_id, {"type": "game_ready", "kiosk_id": kiosk_id, "queue_count": q_count})
    return {"kiosk_id": kiosk_id, "queue_count": q_count}


@router.get("/{game_id}/history")
def game_history(game_id: str, limit: int = 20, db: Session = Depends(get_db)):
    """
    Return recent sessions and per-player scores for a given game_id.
    Intended for use by the admin UI.
    """
    game = db.query(models.Game).filter_by(game_id=game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    limit = max(1, min(int(limit), 100))
    sessions = (
        db.query(models.GameSession)
        .filter_by(game_id=game.id)
        .order_by(models.GameSession.started_at.desc())
        .limit(limit)
        .all()
    )

    out = []
    for s in sessions:
        kiosk = db.get(models.Kiosk, s.kiosk_id)
        players = []
        for sp in s.players:
            player = db.get(models.Player, sp.player_id)
            players.append(
                {
                    "player_id": sp.player_id,
                    "username": player.username if player else None,
                    "score": sp.score,
                }
            )
        out.append(
            {
                "session_id": s.id,
                "kiosk_id": kiosk.kiosk_id if kiosk else None,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "status": s.status,
                "players": players,
            }
        )

    return {"game_id": game_id, "sessions": out}
