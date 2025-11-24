
# Kiosk System Template — v2 (FastAPI, Serial RFID, API-key enforced)

A starter to link multiple game-room kiosks to a central server with **RFID wristbands**.
It now reflects your requirements:

- **Serial RFID** readers on Linux kiosks (`/dev/ttyUSB*`) via a local **kiosk agent** that bridges UIDs to `ws://127.0.0.1:8765`.
- **Dedicated Profile Kiosk** at `/kiosk/profile`. Game kiosks will **not** create profiles.
- **API keys enforced** by default for kiosk and game endpoints.
- **Kiosk flow:** scan → **animated avatar splash** → appear in queue → choose **mode** → **Start Game**.
- **Waiting overlay** if a game is already running at that kiosk.
- **Game Ready** endpoint to let the game logic announce reset; server broadcasts current queue count.
- **Session end** supports game server pushing metrics, with a clear hook to add "pull" mode later.
- **SQLite default**, Docker Compose for **Postgres**; ready to move DB to **AWS RDS** later.

> Assumptions: RFID readers emit UID lines over serial at 9600 baud. If yours differs, change `kiosk_agent/config.yaml`.

---

## Quick Start

```bash
cd kiosk-system-v2
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
cp .env.sample .env
# edit .env → set FERNET_KEY and your kiosk/game keys
python scripts/init_db.py
uvicorn server.app:app --reload
```

Open a kiosk in your browser:
```
http://127.0.0.1:8000/kiosk?kiosk_id=alpha1&game_id=laser_tag
```

Run the **kiosk agent** on the kiosk box (for `/dev/ttyUSB*`):
```bash
cd kiosk_agent
pip install -r requirements.txt
python agent.py
```

(Optional) Reference **game client**:
```bash
cd game_client
pip install websockets requests
python client.py --server http://127.0.0.1:8000 --game_id laser_tag --api_key laser-secret
```

**Profile Kiosk** (for player creation):
```
http://127.0.0.1:8000/kiosk/profile
```

---

## Security

- **API keys required** (`X-API-Key`) on kiosk and game endpoints. Configure in `.env`:
  - `KIOSK_KEYS=alpha1:alpha-secret,profile1:profile-secret`
  - `GAME_KEYS=laser_tag:laser-secret`
- The kiosk page injects its own key at render time (device treated as trusted). For higher assurance, add **mTLS** and/or device-bound tokens, reverse proxy with **TLS**, and rate‑limit.
- **PII** (email) encrypted with **Fernet**; set `FERNET_KEY` in `.env`.
- Ready for **AWS RDS** and S3 (add S3 upload to `players.py` when you move avatars off box).

---

## Data Model (summary)

- `Player(id, email_enc, name, username, avatar_path)`  
- `RFIDTag(id, uid, player_id)`  
- `Game(id, game_id, name)`  
- `Kiosk(id, kiosk_id, location, game_id, modes JSON)`  
- `QueueEntry(id, kiosk_id, player_id, created_at)`  
- `GameSession(id, kiosk_id, game_id, status, started_at, ended_at, meta)`  
- `SessionPlayer(id, session_id, player_id, score, play_time_sec, metrics)`

---

## Game flow

1. Players **scan** at kiosk. Known tags queue and show an animated **avatar splash**. Unknown tags prompt: “Please visit the **Profile Kiosk**.”  
2. Staff selects **mode** and hits **Start Game**. The queue is pulled into a **session**; the server broadcasts `session_started` with `player_count` and list.  
3. Game logic runs. When reset/ready, it calls `POST /games/ready` → server broadcasts `queue_count`.  
4. When finished, it posts to `/sessions/end` with per‑player metrics. (Alternatively, add a pull/importer job later.)

---

## Multi‑location (later)

- Move `DATABASE_URL` to **AWS RDS** Postgres; place the app behind ALB with TLS.  
- Move avatars to **S3**. Consider Cognito/SSO for admin.  
- Add **Redis pub/sub** for WebSocket fan‑out if you run multiple app instances.

# kiosk-server-test
