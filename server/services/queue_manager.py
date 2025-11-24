
from typing import Dict, Set
from starlette.websockets import WebSocket
from asyncio import Lock
import json

class WebSocketHub:
    def __init__(self):
        self.kiosk_clients: Dict[str, Set[WebSocket]] = {}
        self.game_clients: Dict[str, Set[WebSocket]] = {}
        self._lock = Lock()

    async def register(self, group: str, key: str, ws: WebSocket):
        async with self._lock:
            target = self.kiosk_clients if group == "kiosk" else self.game_clients
            target.setdefault(key, set()).add(ws)

    async def unregister(self, group: str, key: str, ws: WebSocket):
        async with self._lock:
            target = self.kiosk_clients if group == "kiosk" else self.game_clients
            conns = target.get(key, set())
            if ws in conns:
                conns.remove(ws)
            if not conns:
                target.pop(key, None)

    async def broadcast(self, group: str, key: str, message: dict):
        target = self.kiosk_clients if group == "kiosk" else self.game_clients
        for ws in list(target.get(key, set())):
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                try: await ws.close()
                except Exception: pass
                await self.unregister(group, key, ws)

hub = WebSocketHub()
