# Repository Guidelines

## Project Structure & Module Organization
- `server/` hosts the FastAPI app: `app.py` wires routers; `routers/` cover players, RFID scans, kiosks, games, sessions, and WebSockets; `services/` (encryption, queue_manager) contain reusable logic; HTML/JS lives under `templates/` and `static/`.
- `kiosk_agent/` is the serial-to-WebSocket bridge configured through `config.yaml`.
- `game_client/` is a reference WebSocket consumer for games.
- `scripts/` holds helper utilities (`init_db.py`, `gen_keys.py`); `docker/` contains the Postgres Compose stack.
- Development data persists in `kiosk.db` (SQLite). Keep generated assets out of source control.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` — create/enter the virtual environment.
- `pip install -r requirements.txt` — install FastAPI, SQLAlchemy, and related deps.
- `python scripts/init_db.py` — create/seed the schema for the active `DATABASE_URL`.
- `uvicorn server.app:app --reload` — run the API plus kiosk UI locally.
- `python kiosk_agent/agent.py` — start the RFID bridge (adjust device/baud in `config.yaml`).
- `python game_client/client.py --server http://127.0.0.1:8000 --game_id laser_tag --api_key laser-secret` — smoke-test the broadcast pipeline.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indents, explicit type hints on routers/services, and descriptive snake_case filenames.
- Favor FastAPI dependency injection via `Depends` over globals, and keep template IDs/classes kebab-case.
- No formatter is enforced; run `python -m black server kiosk_agent` before committing to keep diffs predictable.

## Testing Guidelines
- Automated tests are not yet checked in; add `pytest` suites under `server/tests/` mirroring router names (e.g., `test_sessions.py`).
- Drive async routes via FastAPI’s `TestClient` and seed fixtures with `scripts/init_db.py`.
- Target >80% coverage for touched modules and include at least one RFID scan/session start integration test per change.

## Commit & Pull Request Guidelines
- This export lacks `.git`, but upstream history uses short, imperative summaries with optional Conventional Commit prefixes (`feat: queue broadcast includes kiosk slug`). Keep body lines ≤72 chars and reference issue IDs in the footer.
- PRs should describe the scenario, list local test commands, and call out schema/UI impacts. Attach screenshots or curl traces for kiosk/game flows and link deployment notes when API keys or configs change.

## Security & Configuration Tips
- Copy `.env.sample` → `.env`, then set `FERNET_KEY`, `KIOSK_KEYS`, `GAME_KEYS`, `DATABASE_URL`. Never commit `.env` or `kiosk.db`.
- API keys are mandatory on kiosk/game endpoints; verify headers using `scripts/gen_keys.py`.
- For Postgres, run `docker compose up` inside `docker/` and ensure `DATABASE_URL` matches the Compose service before launching the app.
