
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from server.database import SessionLocal, Base, engine
from server import models

Base.metadata.create_all(bind=engine)
db = SessionLocal()

def ensure_game(game_id, name):
    g = db.query(models.Game).filter_by(game_id=game_id).first()
    if not g:
        g = models.Game(game_id=game_id, name=name)
        db.add(g); db.commit()
    return g

def ensure_kiosk(kiosk_id, game_id, location=None, modes=None):
    g = db.query(models.Game).filter_by(game_id=game_id).first() or ensure_game(game_id, game_id)
    k = db.query(models.Kiosk).filter_by(kiosk_id=kiosk_id).first()
    if not k:
        k = models.Kiosk(kiosk_id=kiosk_id, game_id=g.id, location=location, modes=modes or {"list":["solo","team","hardcore"]})
        db.add(k); db.commit()
    return k

if __name__ == "__main__":
    ensure_game("laser_tag", "Laser Tag")
    ensure_kiosk("alpha1", "laser_tag", "North Gate", {"list":["solo","team","hardcore"]})
    print("Initialized games and kiosks.")
