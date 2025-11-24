
from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os

from .database import Base, engine
from .deps import get_db
from . import models
from .security import verify_admin
from .routers import players, rfid, kiosks, games, sessions, ws
from .schemas import PlayerCreate

app = FastAPI(title="Kiosk System v2")
Base.metadata.create_all(bind=engine)

static_dir = os.path.join(os.path.dirname(__file__), "static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

app.include_router(players.router)
app.include_router(rfid.router)
app.include_router(kiosks.router)
app.include_router(games.router)
app.include_router(sessions.router)
app.include_router(ws.router)

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/kiosk", response_class=HTMLResponse)
def kiosk_ui(request: Request, kiosk_id: str, game_id: str, db: Session = Depends(get_db)):
    from .settings import settings
    api_key = settings.kiosk_keys.get(kiosk_id, "")
    game = db.query(models.Game).filter_by(game_id=game_id).first()
    game_name = game.name if game else game_id
    return templates.TemplateResponse(
        "kiosk.html",
        {
            "request": request,
            "kiosk_id": kiosk_id,
            "game_id": game_id,
            "game_name": game_name,
            "api_key": api_key,
        },
    )

@app.get("/kiosk/profile", response_class=HTMLResponse)
def profile_kiosk(request: Request):
    return templates.TemplateResponse("profile_kiosk.html", {"request": request})

@app.get("/ui/profile/new", response_class=HTMLResponse)
def profile_new(request: Request, rfid_uid: str, kiosk_id: str, game_id: str):
    # legacy form (not used by game kiosks)
    return templates.TemplateResponse("profile_create.html", {"request": request, "rfid_uid": rfid_uid})

@app.post("/ui/profile/create")
def profile_create(request: Request, email: str = Form(...), name: str = Form(...), username: str = Form(...), rfid_uid: str = Form(...), db: Session = Depends(get_db)):
    data = PlayerCreate(email=email, name=name, username=username, rfid_uid=rfid_uid)
    from .routers.players import create_player as _create
    player = _create(data, db)
    return RedirectResponse(url="/", status_code=303)



@app.get("/ui/kiosks/details")
def kiosk_details(db: Session = Depends(get_db)):
    from .services.queue_manager import hub
    items = []
    kiosks = db.query(models.Kiosk).all()
    for k in kiosks:
        g = db.get(models.Game, k.game_id)
        running = db.query(models.GameSession).filter_by(kiosk_id=k.id, status="running").first()
        connected = bool((hub.kiosk_clients.get(k.kiosk_id) or []))
        items.append({
            "game_name": g.name if g else None,
            "kiosk_id": k.kiosk_id,
            "game_id": g.game_id if g else None,
            "location": k.location,
            "connected": connected,
            "status": "running" if running else "idle"
        })
    return {"kiosks": items}


@app.get("/ui/kiosks")
def list_kiosk_ids(db: Session = Depends(get_db)):
    ids = [k.kiosk_id for k in db.query(models.Kiosk).all()]
    return {"kiosks": ids}


@app.get("/ui/games/history", response_class=HTMLResponse)
def game_history_page(request: Request, game_id: str):
    return templates.TemplateResponse("game_history.html", {"request": request, "game_id": game_id})


@app.get("/ui/dev", response_class=HTMLResponse)
def dev_page(request: Request, admin: bool = Depends(verify_admin)):
    return templates.TemplateResponse("dev.html", {"request": request})


@app.get("/ui/players/dev", response_class=HTMLResponse)
def dev_players_page(request: Request, admin: bool = Depends(verify_admin)):
    return templates.TemplateResponse("players_dev.html", {"request": request})
