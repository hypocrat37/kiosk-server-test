# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI-based kiosk management system for game rooms with RFID wristband authentication. The system consists of:

- **Central Server** (FastAPI): Manages players, RFID tags, kiosks, game sessions, and queues
- **Kiosk Agent** (Python): Runs on Linux kiosks to bridge serial RFID readers (`/dev/ttyUSB*`) to WebSocket at `ws://127.0.0.1:8765`
- **Game Client** (Reference): Example WebSocket client that receives session events and posts metrics

Key architectural decisions:
- **Profile Kiosk** (`/kiosk/profile`) is dedicated for player creation. Game kiosks do NOT create profiles.
- **API keys** are enforced on all kiosk and game endpoints via `X-API-Key` header
- **PII encryption**: Player emails are encrypted with Fernet (requires `FERNET_KEY` in `.env`)
- **WebSocket hub**: Broadcasts events to kiosk and game clients (in-memory, single-instance; extend with Redis for multi-instance)

## Development Commands

### Initial Setup
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Generate Fernet key for PII encryption
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Configure environment
cp .env.sample .env
# Edit .env and set FERNET_KEY, KIOSK_KEYS, GAME_KEYS

# Initialize database (creates SQLite by default)
python scripts/init_db.py
```

### Running the Server
```bash
# Development server with auto-reload
uvicorn server.app:app --reload

# Production
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

### Running Components

**Kiosk Agent** (on physical kiosk with RFID reader):
```bash
cd kiosk_agent
pip install -r requirements.txt
python agent.py
# Reads from /dev/ttyUSB0 at 9600 baud (configurable in config.yaml)
```

**Game Client** (reference implementation):
```bash
cd game_client
pip install websockets requests
python client.py --server http://127.0.0.1:8000 --game_id laser_tag --api_key laser-secret
```

### Docker Compose (Postgres)
```bash
cd docker
docker-compose up
# Server runs at http://localhost:8000
# Uses Postgres instead of SQLite
```

## Architecture

### Data Flow

1. **RFID Scan Flow**:
   - Kiosk agent reads UID from serial port → sends to browser via WebSocket (`ws://127.0.0.1:8765`)
   - Browser sends UID to server (`POST /rfid/scan`)
   - Server looks up player by UID → adds to queue OR prompts "Visit Profile Kiosk"
   - Server broadcasts queue update via WebSocket hub

2. **Session Start Flow**:
   - Kiosk staff selects mode and clicks "Start Game" → `POST /sessions/start`
   - Server pulls queue entries into a `GameSession`, clears queue
   - Server broadcasts `session_started` to both kiosk and game WebSocket clients
   - Game client receives event with player list

3. **Session End Flow**:
   - Game client posts metrics → `POST /sessions/end`
   - Server updates `SessionPlayer` records with scores/metrics
   - Server broadcasts `session_ended`

### Key Components

**server/app.py**: Main FastAPI application
- Mounts static files and templates
- Routes: `/kiosk`, `/kiosk/profile`, `/`
- Includes routers: players, rfid, kiosks, games, sessions, ws

**server/models.py**: SQLAlchemy ORM models
- `Player`: Stores encrypted email, name, username, avatar path
- `RFIDTag`: Links UID to player
- `Game`: Represents a game type (e.g., "laser_tag")
- `Kiosk`: Physical kiosk with location, API key, modes
- `QueueEntry`: Per-kiosk queue of players waiting to play
- `GameSession`: Tracks session lifecycle (pending/running/ended)
- `SessionPlayer`: Per-player metrics within a session

**server/services/queue_manager.py**: WebSocket hub
- `WebSocketHub`: In-memory pub/sub for "kiosk" and "game" groups
- `hub.register()`, `hub.broadcast()`, `hub.unregister()`
- Note: Single-instance only; use Redis for horizontal scaling

**server/routers/sessions.py**: Session lifecycle
- `POST /sessions/start`: Pulls queue into running session
- `POST /sessions/end`: Updates metrics, marks session ended

**server/routers/games.py**: Game endpoints
- `POST /games/ready`: Game announces reset, server broadcasts queue count

**server/security.py**: API key verification
- `verify_kiosk_key()`, `verify_game_key()`: Check `X-API-Key` header against settings

**kiosk_agent/agent.py**: Serial RFID bridge
- Reads lines from serial device (`config.yaml`)
- Serves WebSocket on `ws://127.0.0.1:8765`
- Sends each UID line to connected browser

### Environment Configuration

Required variables in `.env`:
- `DATABASE_URL`: Default `sqlite:///./kiosk.db`, use `postgresql+psycopg2://...` for Postgres
- `FERNET_KEY`: Symmetric key for email encryption (generate with `Fernet.generate_key()`)
- `KIOSK_KEYS`: Comma-separated `kiosk_id:api_key` pairs (e.g., `alpha1:alpha-secret,profile1:profile-secret`)
- `GAME_KEYS`: Comma-separated `game_id:api_key` pairs (e.g., `laser_tag:laser-secret`)
- `SERVER_HOST`: Full URL for WebSocket URLs (default `http://127.0.0.1:8000`)

### Security Model

- **API Key Authentication**: All kiosk and game endpoints require `X-API-Key` header
- **Kiosk keys** are injected into HTML templates at render time (treats kiosk device as trusted)
- **PII Encryption**: Player emails encrypted via Fernet before database storage
- **Future enhancements**: mTLS, device-bound tokens, reverse proxy with TLS, rate limiting

### Database Migration Path

- **SQLite** (default): Single-file database for development/small deployments
- **Postgres** (Docker Compose): Local multi-kiosk testing
- **AWS RDS** (production): Set `DATABASE_URL` to RDS endpoint, move avatars to S3

### WebSocket Endpoints

- `/ws/kiosk/{kiosk_id}`: Kiosk UI receives queue updates, session events
- `/ws/game/{game_id}`: Game client receives `session_started`, `session_ended`, `game_ready` events

### RFID Reader Configuration

Default: Serial device at `/dev/ttyUSB0`, 9600 baud. Modify `kiosk_agent/config.yaml`:
```yaml
serial_device: /dev/ttyUSB0
baudrate: 9600
```

Assumptions: RFID reader emits one UID per line over serial.
