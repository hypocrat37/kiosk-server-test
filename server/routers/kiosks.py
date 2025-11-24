
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from ..deps import get_db
from .. import models
from ..schemas import KioskCreate, KioskUpdate, QueueLeaveIn
from ..security import verify_kiosk_key
from ..services.queue_manager import hub
from datetime import datetime
import os

router = APIRouter(prefix="/kiosks", tags=["kiosks"])

@router.post("")
def create_kiosk(data: KioskCreate, db: Session = Depends(get_db)):
    game = db.query(models.Game).filter_by(game_id=data.game_id).first()
    if not game:
        raise HTTPException(status_code=400, detail="Unknown game_id")
    if db.query(models.Kiosk).filter_by(kiosk_id=data.kiosk_id).first():
        raise HTTPException(status_code=400, detail="Kiosk exists")
    k = models.Kiosk(
        kiosk_id=data.kiosk_id,
        location=data.location,
        game_id=game.id,
        api_key_hash=None,
        modes=data.modes or {"list": ["default"]},
        objectives=data.objectives or [],
        traits=data.traits or {},
    )
    db.add(k)
    db.commit()
    return {"ok": True}

@router.post("/{kiosk_id}/config")
def update_kiosk_config(kiosk_id: str, data: KioskUpdate, db: Session = Depends(get_db)):
    """
    Lightweight config update for dev tooling: supports updating
    location, modes JSON, and objectives for an existing kiosk.
    """
    kiosk = db.query(models.Kiosk).filter_by(kiosk_id=kiosk_id).first()
    if not kiosk:
        raise HTTPException(status_code=404, detail="Kiosk not found")
    if data.location is not None:
        kiosk.location = data.location
    if data.modes is not None:
        kiosk.modes = data.modes
    if data.objectives is not None:
        kiosk.objectives = data.objectives
    if data.traits is not None:
        kiosk.traits = data.traits
    db.commit()
    return {"ok": True}

@router.get("/{kiosk_id}")
def get_kiosk(kiosk_id: str, db: Session = Depends(get_db)):
    kiosk = db.query(models.Kiosk).filter_by(kiosk_id=kiosk_id).first()
    if not kiosk:
        raise HTTPException(status_code=404, detail="Kiosk not found")
    game = db.get(models.Game, kiosk.game_id)
    return {
        "kiosk_id": kiosk.kiosk_id,
        "location": kiosk.location,
        "game_id": game.game_id if game else None,
        "game_name": game.name if game else None,
        "modes": kiosk.modes or {},
        "objectives": kiosk.objectives or [],
        "traits": kiosk.traits or {},
    }


@router.get("/{kiosk_id}/queue")
def get_queue(kiosk_id: str, db: Session = Depends(get_db)):
    kiosk = db.query(models.Kiosk).filter_by(kiosk_id=kiosk_id).first()
    if not kiosk:
        raise HTTPException(status_code=404, detail="Kiosk not found")
    q = (
        db.query(models.QueueEntry, models.Player)
        .join(models.Player, models.Player.id == models.QueueEntry.player_id)
        .filter(models.QueueEntry.kiosk_id == kiosk.id)
        .order_by(models.QueueEntry.created_at.asc())
        .all()
    )
    items = []
    from ..services.encryption import dec
    for qe, p in q:
        items.append({
            "player": {
                "id": p.id,
                "email": dec(p.email_enc) if p.email_enc else None,
                "name": p.name,
                "username": p.username,
                "avatar_url": f"/static/avatars/{os.path.basename(p.avatar_path)}" if p.avatar_path else None,
            }
        })
    return {"kiosk_id": kiosk_id, "queue": items}

@router.get("/{kiosk_id}/status")
def kiosk_status(kiosk_id: str, db: Session = Depends(get_db)):
    kiosk = db.query(models.Kiosk).filter_by(kiosk_id=kiosk_id).first()
    if not kiosk:
        raise HTTPException(status_code=404, detail="Kiosk not found")
    running = db.query(models.GameSession).filter_by(kiosk_id=kiosk.id, status="running").first()
    modes = (kiosk.modes or {}).get("list", [])
    objectives = kiosk.objectives or []
    traits = kiosk.traits or {}
    return {
        "kiosk_id": kiosk_id,
        "status": "running" if running else "idle",
        "session_id": running.id if running else None,
        "modes": modes,
        "objectives": objectives,
        "traits": traits,
    }


@router.post("/{kiosk_id}/queue/dev_add")
async def dev_add_to_queue(kiosk_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Convenience endpoint to enqueue a development/test player for this kiosk.
    Protected by the kiosk API key so it can be triggered from the kiosk UI only.
    """
    verify_kiosk_key(request, kiosk_id)

    kiosk = db.query(models.Kiosk).filter_by(kiosk_id=kiosk_id).first()
    if not kiosk:
        raise HTTPException(status_code=404, detail="Kiosk not found")

    # Allow up to three shared dev players across kiosks: dev_player_1..3
    # This makes it easy to demo cross-room history, since the same dev
    # players can be queued at multiple kiosks and accumulate sessions.
    player = None
    for idx in range(1, 4):
        username = f"dev_player_{idx}"
        candidate = db.query(models.Player).filter_by(username=username).first()
        if not candidate:
            candidate = models.Player(
                username=username,
                name=f"Dev Player {idx}"
            )
            db.add(candidate)
            db.flush()

        exists = db.query(models.QueueEntry).filter_by(
            kiosk_id=kiosk.id, player_id=candidate.id
        ).first()
        if not exists:
            qe = models.QueueEntry(kiosk_id=kiosk.id, player_id=candidate.id)
            db.add(qe)
            player = candidate
            break

    if not player:
        # All dev players already queued
        db.commit()
        return {"ok": False, "detail": "All dev players already queued."}

    db.commit()
    await hub.broadcast("kiosk", kiosk_id, {"type": "queue_update"})
    return {"ok": True, "player_id": player.id}


@router.post("/{kiosk_id}/queue/remove")
async def remove_from_queue(kiosk_id: str, data: QueueLeaveIn, request: Request, db: Session = Depends(get_db)):
    """
    Allow a queued player to leave the line from the kiosk UI.
    Protected by the kiosk API key.
    """
    verify_kiosk_key(request, kiosk_id)

    kiosk = db.query(models.Kiosk).filter_by(kiosk_id=kiosk_id).first()
    if not kiosk:
        raise HTTPException(status_code=404, detail="Kiosk not found")

    qe = db.query(models.QueueEntry).filter_by(
        kiosk_id=kiosk.id, player_id=data.player_id
    ).first()
    if not qe:
        # Not an error; nothing to do if they already left.
        return {"ok": False, "detail": "Player not in queue."}

    db.delete(qe)
    db.commit()

    await hub.broadcast("kiosk", kiosk_id, {"type": "queue_update"})
    return {"ok": True}


def _clear_queue_and_end_sessions(kiosk: models.Kiosk, db: Session):
    """
    Helper to clear queue entries and mark any running sessions as ended.
    Returns (cleared_count, ended_session_ids).
    """
    q_items = db.query(models.QueueEntry).filter_by(kiosk_id=kiosk.id).all()
    cleared = len(q_items)
    for qe in q_items:
        db.delete(qe)

    active_sessions = db.query(models.GameSession).filter_by(kiosk_id=kiosk.id, status="running").all()
    ended_ids = []
    for session in active_sessions:
        session.status = "ended"
        session.ended_at = datetime.utcnow()
        ended_ids.append(session.id)

    db.commit()
    return cleared, ended_ids


@router.post("/{kiosk_id}/queue/reset")
async def reset_queue(kiosk_id: str, db: Session = Depends(get_db)):
    """
    Clear the entire queue for a kiosk and forcibly end any running session.
    Notifies kiosk and game clients so UIs can return to their idle screens.
    """
    kiosk = db.query(models.Kiosk).filter_by(kiosk_id=kiosk_id).first()
    if not kiosk:
        raise HTTPException(status_code=404, detail="Kiosk not found")

    cleared, ended_ids = _clear_queue_and_end_sessions(kiosk, db)

    await hub.broadcast("kiosk", kiosk_id, {"type": "queue_update"})
    game = db.get(models.Game, kiosk.game_id)
    for sid in ended_ids:
        await hub.broadcast("kiosk", kiosk_id, {"type": "session_ended", "session_id": sid})
        if game:
            await hub.broadcast("game", game.game_id, {"type": "session_ended", "session_id": sid})
    if game:
        await hub.broadcast("game", game.game_id, {"type": "admin_reset", "kiosk_id": kiosk_id})

    return {"ok": True, "cleared": cleared, "ended_sessions": len(ended_ids)}


@router.post("/{kiosk_id}/reset")
async def reset_kiosk(kiosk_id: str, db: Session = Depends(get_db)):
    """
    Clear queue and forcibly end any running session for this kiosk.
    Broadcasts session_ended so game/kiosk listeners can clean up.
    """
    kiosk = db.query(models.Kiosk).filter_by(kiosk_id=kiosk_id).first()
    if not kiosk:
        raise HTTPException(status_code=404, detail="Kiosk not found")

    cleared, ended_ids = _clear_queue_and_end_sessions(kiosk, db)

    # Notify kiosk/game clients
    await hub.broadcast("kiosk", kiosk_id, {"type": "queue_update"})
    game = db.get(models.Game, kiosk.game_id)
    for sid in ended_ids:
        await hub.broadcast("kiosk", kiosk_id, {"type": "session_ended", "session_id": sid})
        if game:
            await hub.broadcast("game", game.game_id, {"type": "session_ended", "session_id": sid})
    if game:
        await hub.broadcast("game", game.game_id, {"type": "admin_reset", "kiosk_id": kiosk_id})

    return {"ok": True, "cleared": cleared, "ended_sessions": len(ended_ids)}


@router.delete("/{kiosk_id}")
async def delete_kiosk(kiosk_id: str, db: Session = Depends(get_db)):
    """
    Development helper to remove a kiosk row entirely.
    Clears its queue and ends any running sessions, then deletes the kiosk.
    Broadcasts updates so UIs can reset.
    """
    kiosk = db.query(models.Kiosk).filter_by(kiosk_id=kiosk_id).first()
    if not kiosk:
        raise HTTPException(status_code=404, detail="Kiosk not found")

    cleared, ended_ids = _clear_queue_and_end_sessions(kiosk, db)

    # Notify kiosk/game clients about the reset before deletion
    await hub.broadcast("kiosk", kiosk_id, {"type": "queue_update"})
    game = db.get(models.Game, kiosk.game_id)
    for sid in ended_ids:
        await hub.broadcast("kiosk", kiosk_id, {"type": "session_ended", "session_id": sid})
        if game:
            await hub.broadcast("game", game.game_id, {"type": "session_ended", "session_id": sid})
    if game:
        await hub.broadcast("game", game.game_id, {"type": "admin_reset", "kiosk_id": kiosk_id})

    db.delete(kiosk)
    db.commit()
    return {"ok": True, "cleared": cleared, "ended_sessions": len(ended_ids)}
