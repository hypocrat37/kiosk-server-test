
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from ..deps import get_db
from .. import models
from ..schemas import RFIDScanIn
from ..services.queue_manager import hub
from ..security import verify_kiosk_key

router = APIRouter(prefix="/rfid", tags=["rfid"])

@router.post("/scan")
async def scan(data: RFIDScanIn, request: Request, db: Session = Depends(get_db)):
    verify_kiosk_key(request, data.kiosk_id)

    tag = db.query(models.RFIDTag).filter_by(uid=data.rfid_uid).first()
    if not tag:
        return {"known": False, "message": "Unknown tag. Please visit the Profile Kiosk."}

    kiosk = db.query(models.Kiosk).filter_by(kiosk_id=data.kiosk_id).first()
    if not kiosk:
        raise HTTPException(status_code=400, detail="Unknown kiosk")

    exists = db.query(models.QueueEntry).filter_by(kiosk_id=kiosk.id, player_id=tag.player_id).first()
    if not exists:
        qe = models.QueueEntry(kiosk_id=kiosk.id, player_id=tag.player_id)
        db.add(qe)
        db.commit()

    await hub.broadcast("kiosk", data.kiosk_id, {"type": "queue_update"})
    return {"known": True, "player_id": tag.player_id}
