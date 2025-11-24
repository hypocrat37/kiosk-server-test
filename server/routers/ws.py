
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..services.queue_manager import hub

router = APIRouter()

@router.websocket("/ws/kiosk/{kiosk_id}")
async def ws_kiosk(ws: WebSocket, kiosk_id: str):
    await ws.accept()
    await hub.register("kiosk", kiosk_id, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await hub.unregister("kiosk", kiosk_id, ws)

@router.websocket("/ws/game/{game_id}")
async def ws_game(ws: WebSocket, game_id: str):
    await ws.accept()
    await hub.register("game", game_id, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await hub.unregister("game", game_id, ws)
