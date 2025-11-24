
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime
from ..deps import get_db
from .. import models
from ..schemas import SessionStartIn, SessionEndIn, SessionOut
from ..services.queue_manager import hub
from ..security import verify_kiosk_key, verify_game_key

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.post("/start", response_model=SessionOut)
async def start_session(data: SessionStartIn, request: Request, db: Session = Depends(get_db)):
    verify_kiosk_key(request, data.kiosk_id)
    kiosk = db.query(models.Kiosk).filter_by(kiosk_id=data.kiosk_id).first()
    if not kiosk:
        raise HTTPException(status_code=400, detail="Unknown kiosk")
    active = db.query(models.GameSession).filter_by(kiosk_id=kiosk.id, status="running").first()
    if active:
        return SessionOut(id=active.id, status=active.status, game_id=active.game_id)

    q_items = db.query(models.QueueEntry).filter_by(kiosk_id=kiosk.id).order_by(models.QueueEntry.created_at.asc()).all()
    if not q_items:
        raise HTTPException(status_code=400, detail="Queue is empty")

    session = models.GameSession(kiosk_id=kiosk.id, game_id=kiosk.game_id, status="running", started_at=datetime.utcnow())
    session.meta = {"mode": data.mode} if data.mode else {}
    db.add(session); db.flush()
    for qi in q_items:
        sp = models.SessionPlayer(session_id=session.id, player_id=qi.player_id)
        db.add(sp)
        db.delete(qi)
    db.commit()

    players_payload = [{"player_id": sp.player_id} for sp in session.players]
    await hub.broadcast("kiosk", data.kiosk_id, {"type": "session_started", "session_id": session.id})
    game = db.get(models.Game, kiosk.game_id)
    await hub.broadcast("game", game.game_id, {
        "type": "session_started",
        "session_id": session.id,
        "kiosk_id": data.kiosk_id,
        "player_count": len(players_payload),
        "players": players_payload,
        "mode": session.meta.get("mode")
    })
    return SessionOut(id=session.id, status=session.status, game_id=session.game_id)

@router.post("/end")
async def end_session(data: SessionEndIn, request: Request, db: Session = Depends(get_db)):
    session = db.get(models.GameSession, data.session_id)
    if not session or session.status != "running":
        raise HTTPException(status_code=400, detail="Invalid session")
    game = db.get(models.Game, session.game_id)
    verify_game_key(request, game.game_id)

    sp_map = {sp.player_id: sp for sp in session.players}
    for p in data.players:
        pid = int(p.get("player_id"))
        if pid in sp_map:
            sp_map[pid].score = int(p.get("score", 0))
            sp_map[pid].play_time_sec = int(p.get("play_time_sec", 0))
            sp_map[pid].metrics = p.get("metrics", {})
    session.status = "ended"
    session.ended_at = datetime.utcnow()
    session.meta = data.game_metrics or {}
    db.commit()

    kiosk = db.get(models.Kiosk, session.kiosk_id)
    await hub.broadcast("kiosk", kiosk.kiosk_id, {"type": "session_ended", "session_id": session.id})
    await hub.broadcast("game", game.game_id, {"type": "session_ended", "session_id": session.id})
    return {"ok": True}
