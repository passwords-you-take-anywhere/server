# Server

FastAPI backend for the project.

## Requirements

- Python 3.14 (see `server/.python-version`)
- One of:
  - `uv` (recommended) or
  - `pip` with `venv`
- PostgreSQL 16 (Docker Compose included)

## Setup

From `server/`:

1) Create the environment file

PowerShell:
```powershell
Copy-Item example.env .env
```
Bash:
```bash
cp example.env .env
```

2) Start PostgreSQL (Docker)

PowerShell:
```powershell
docker compose up -d
```

Bash:
```bash
docker compose up -d
```

3) Install dependencies

Using `uv`:

PowerShell:
```powershell
uv sync
```

Bash:
```bash
uv sync
```

Using `pip`:
PowerShell:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e .
```
Bash:
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e .
```

## Run the server

PowerShell:
```powershell
python src/main.py
```
Bash:
```bash
python src/main.py
```

The API starts on `http://localhost:8000` by default.

## Environment variables

All variables are read from `server/.env` (see `server/example.env`).

- `POSTGRES_CONTAINER_NAME`: docker container name
- `POSTGRES_PORT`: host port for PostgreSQL
- `POSTGRES_INTERNAL_PORT`: container port for PostgreSQL
- `POSTGRES_DB`: database name
- `POSTGRES_USER`: database user
- `POSTGRES_PASSWORD`: database password
- `SEED_DB`: set to `1` to seed demo data on startup
- `DB_HOST`: override the database host (default: `localhost`)
- `PORT`: override API port (default: `8000`)
- `DEBUG`: set to `1` or `true` to enable reload and SQL echo

## Seeding demo data

Set `SEED_DB=1` in `server/.env` and start the server. It will add demo users:

- `alice@example.com` / `Alice!234`
- `bob@example.com` / `Bob!2345`
- `carol@example.com` / `Carol!23`

## Adminer (optional)

`docker compose up -d` also starts Adminer at `http://localhost:8080`.
